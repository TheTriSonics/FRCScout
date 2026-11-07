"""Refresh the history database for events happening now.

Pulls only events that are on (start - 1 day through end + days_after) plus
the season's event list and EPA, and updates each layer from the one before
(see lake.py): the responses go to history-source raw/, those rows are
replaced in the Parquet tables (history-source lake/), and the database is
made again from the Parquet tables and uploaded. Meant to run hourly in
competition season; older seasons don't change and come from build.py.

Raw files use the same paths as sync.py's cache (raw/tba/matches/2026/2026miwmi.json.gz,
...), so history-source stays a complete source: download raw/ into
history/data/raw/ and build.py makes the same lake and database.

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
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


def refresh(year=None, today=None, days_after=1, lake_dir=None, db=None, upload=True):
    """Bring every layer up to date for the events on now: raw responses, then the
    Parquet tables, then the database made from them. Returns a summary dict.
    lake_dir/db: patch this local lake folder and write this database (for testing)
    instead of starting from history-source; upload=False keeps everything local."""
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
    if upload:  # bronze first: a failed later step is redone next run
        raw = {sync.name(s, r): d for s, r, d in log}  # last fetch of a route wins
        summary['source_raw'] = store.put_source(
            ('raw/' + n, gzip.compress(json.dumps(d).encode())) for n, d in raw.items())
        del raw
    log.clear()
    _fetched.log = None

    work = Path(tempfile.mkdtemp(prefix='history-refresh-'))
    lake_dir = Path(lake_dir) if lake_dir else store.get_lake(work / 'lake')
    db = Path(db) if db else work / 'history.duckdb'
    con = lake.connect()
    try:
        t = {name: lake_dir / f'{name}.parquet' for name in lake.TABLES + ['team_matches']}
        in_keys = '(' + ','.join(f"'{k}'" for k in keys) + ')'
        teams = {t_['team_number']: r for t_, r in zip(
            (x for _, d in fetched for x in d['teams'] or []),
            lake.team_rows([x for _, d in fetched for x in d['teams'] or []]))}
        if teams:
            lake.replace_rows(con, t['teams'], f"team_number NOT IN ({','.join(map(str, teams))})",
                              teams.values())
        lake.replace_rows(con, t['events'], f'year <> {int(year)}', lake.event_rows(events))
        lake.replace_rows(con, t['matches'], f'event_key NOT IN {in_keys}',
                          (r for _, d in fetched for r in lake.match_rows(d['matches'])))
        lake.replace_rows(con, t['awards'], f'event_key NOT IN {in_keys}',
                          (r for _, d in fetched for r in lake.award_rows(d['awards'])))
        lake.replace_rows(con, t['team_events'], f'event_key NOT IN {in_keys}',
                          (r for k, d in fetched for r in lake.team_event_rows(k, d['teams/statuses'])))
        lake.replace_rows(con, t['epa_team_events'], f'event_key NOT IN {in_keys}',
                          lake.epa_event_rows(sb_events))
        if dranks:
            lake.replace_rows(con, t['district_rankings'],
                              'district_key NOT IN (' + ','.join(f"'{k}'" for k in dranks) + ')',
                              (r for dk, ranks in dranks.items() for r in lake.district_rows(dk, ranks)))
        if team_years:
            lake.replace_rows(con, t['epa_team_years'], f'year <> {int(year)}',
                              lake.epa_year_rows(team_years))
        del fetched, sb_events, team_years, teams, dranks, events
        gc.collect()  # the responses are in the lake now; keep the instance's 512 MB for DuckDB
        lake.matches_view(con, lake_dir)
        lake.replace_rows(con, t['team_matches'], f'event_key NOT IN {in_keys}',
                          sql=lake.TEAM_MATCHES.format(where=f'WHERE event_key IN {in_keys}'))
        summary['matches'] = con.execute(
            f"SELECT count(*) FROM '{t['matches']}' WHERE event_key IN {in_keys}").fetchone()[0]
    finally:
        con.close()
    if upload:  # silver
        summary['source_lake'] = store.put_source(('lake/' + f.name, f) for f in sorted(lake_dir.glob('*.parquet')))
    lake.make_db(lake_dir, db)  # gold
    if upload:
        store.upload(db)
        summary['uploaded'] = True
    shutil.rmtree(work, ignore_errors=True)
    logging.info('history refresh %s', summary)
    return summary
