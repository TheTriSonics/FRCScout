"""Refresh the history database for events happening now.

Pulls only events that are on (start - 1 day through end + days_after) plus
the season's event list and EPA, replaces those rows in a copy of the
database, and uploads it. Meant to run hourly in competition season; older
seasons don't change and come from build.py.

Every response it fetched is also saved to the history-source container under
the same name sync.py caches it as (raw/tba/..., raw/sb/...), and the updated
tables as lake/<table>.parquet, so history-source stays a complete source:
download raw/ into history/data/raw/ and build.py makes the same database.

Calls per run: 1 event list, 4 per active event (matches, awards, statuses,
teams), 1 per active district, ~4 Statbotics team_years pages and ~4
team_events pages for the season.
"""
import datetime as dt
import gc
import gzip
import json
import logging
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

from history import lake, store, sync

TBA = 'https://www.thebluealliance.com/api/v3'
SB = 'https://api.statbotics.io/v3'


_fetched = threading.local()


def _record(source, route, data):
    log = getattr(_fetched, 'log', None)
    if log is not None:
        log.append((source, route, data))
    return data


def _get(url, headers=None):
    """GET JSON; None for 404. Retries 5xx, 429 and network errors with backoff."""
    req = urllib.request.Request(url, headers={'User-Agent': 'trisonics-scout-history', **(headers or {})})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == 4 or (e.code < 500 and e.code != 429):
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(2 ** attempt)


def tba(route):
    return _record('tba', route, _get(TBA + route, {'X-TBA-Auth-Key': os.environ['TBA_KEY']}))


def sb(route):
    return _record('sb', route, _get(SB + route))


def sb_pages(route):
    out, offset = [], 0
    while True:
        page = sb(f'{route}&limit=1000&offset={offset}') or []
        out += page
        if len(page) < 1000:
            return out
        offset += 1000


def active(events, today, days_after=1):
    out = []
    for e in events:
        try:
            start = dt.date.fromisoformat(e['start_date']) - dt.timedelta(days=1)
            end = dt.date.fromisoformat(e['end_date']) + dt.timedelta(days=days_after)
        except (KeyError, TypeError, ValueError):
            continue
        if start <= today <= end:
            out.append(e)
    return out


def refresh(year=None, today=None, days_after=1, db=None, upload=True):
    """Returns a summary dict. db: work on this local file instead of the blob."""
    today = today or dt.date.today()
    year = year or today.year
    log = _fetched.log = []
    events = tba(f'/events/{year}') or []
    now = active(events, today, days_after)
    keys = [e['key'] for e in now]
    summary = {'year': year, 'today': str(today), 'active_events': keys}
    if not keys:
        logging.info('history refresh: no active events')
        _fetched.log = None
        return summary

    def per_event(key):
        _fetched.log = log
        return key, {w: tba(f'/event/{key}/{w}') for w in ('matches', 'awards', 'teams/statuses', 'teams')}

    def district(d):
        _fetched.log = log
        return tba(f'/district/{d}/rankings')

    with ThreadPoolExecutor(8) as pool:
        fetched = list(pool.map(per_event, keys))
        districts = sorted({f"{year}{e['district']['abbreviation']}" for e in now if e.get('district')})
        dranks = dict(zip(districts, pool.map(district, districts)))
    team_years = sb_pages(f'/team_years?year={year}')
    sb_events = [t for t in sb_pages(f'/team_events?year={year}') if t.get('event') in keys]
    if upload:  # the source first: a failed database update is redone next run
        raw = {sync.name(s, r): d for s, r, d in log}  # last fetch of a route wins
        summary['source_raw'] = store.put_source(
            ('raw/' + n, gzip.compress(json.dumps(d).encode())) for n, d in raw.items())
        del raw
    log.clear()
    _fetched.log = None

    if db:
        path = Path(db)
    else:
        fd, tmp = tempfile.mkstemp(prefix='history-refresh-', suffix='.duckdb')
        os.close(fd)
        path = Path(tmp)
        store.download(path)
    con = duckdb.connect(str(path), config={'memory_limit': '200MB', 'threads': 2})
    try:
        con.execute('BEGIN')
        in_keys = '(' + ','.join(f"'{k}'" for k in keys) + ')'
        teams = [t for _, d in fetched for t in d['teams'] or []]
        numbers = sorted({t['team_number'] for t in teams})
        if numbers:
            con.execute(f"DELETE FROM teams WHERE team_number IN ({','.join(map(str, numbers))})")
            lake.insert_rows(con, 'teams', {t['team_number']: r for t, r in
                                            zip(teams, lake.team_rows(teams))}.values())
        con.execute('DELETE FROM events WHERE year = ?', [year])
        lake.insert_rows(con, 'events', lake.event_rows(events))
        for table in ('matches', 'awards', 'team_events', 'epa_team_events', 'team_matches'):
            con.execute(f'DELETE FROM {table} WHERE event_key IN {in_keys}')
        for key, d in fetched:
            lake.insert_rows(con, 'matches', lake.match_rows(d['matches']))
            lake.insert_rows(con, 'awards', lake.award_rows(d['awards']))
            lake.insert_rows(con, 'team_events', lake.team_event_rows(key, d['teams/statuses']))
        lake.insert_rows(con, 'epa_team_events', lake.epa_event_rows(sb_events))
        con.execute('INSERT INTO team_matches ' + lake.TEAM_MATCHES.format(where=f'WHERE event_key IN {in_keys}'))
        for dk, ranks in dranks.items():
            con.execute('DELETE FROM district_rankings WHERE district_key = ?', [dk])
            lake.insert_rows(con, 'district_rankings', lake.district_rows(dk, ranks))
        if team_years:
            con.execute('DELETE FROM epa_team_years WHERE year = ?', [year])
            lake.insert_rows(con, 'epa_team_years', lake.epa_year_rows(team_years))
        con.execute('COMMIT')
        con.execute('CHECKPOINT')
        del fetched, sb_events, team_years, teams, dranks, events
        gc.collect()  # the responses are in the database now; keep the instance's 512 MB for COPY
        summary['matches'] = con.execute(f'SELECT count(*) FROM matches WHERE event_key IN {in_keys}').fetchone()[0]
        # COPY uses all the memory it may; the instance has 512 MB shared with chat requests.
        con.execute("SET memory_limit = '100MB'")
        con.execute('SET threads = 1')
        con.execute('SET preserve_insertion_order = false')
        lake_dir = Path(tempfile.mkdtemp(prefix='history-lake-'))
        for (name,) in con.execute('SHOW TABLES').fetchall():
            con.execute(f"COPY {name} TO '{lake_dir / name}.parquet' "
                        "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 10000)")
    finally:
        con.close()
    parquet = sorted(lake_dir.glob('*.parquet'))
    if upload:
        store.upload(path)
        summary['uploaded'] = True
        summary['source_lake'] = store.put_source(('lake/' + f.name, f) for f in parquet)
    for f in parquet:
        f.unlink()
    lake_dir.rmdir()
    if not db:
        path.unlink(missing_ok=True)
    logging.info('history refresh %s', summary)
    return summary
