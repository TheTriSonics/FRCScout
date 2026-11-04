"""Refresh the history database for events happening now.

Pulls only events that are on (start - 1 day through end + days_after) plus
the season's event list and EPA, replaces those rows in a copy of the
database, and uploads it. Meant to run hourly in competition season; older
seasons don't change and come from build.py.

Calls per run: 1 event list, 4 per active event (matches, awards, statuses,
teams), 1 per active district, ~4 Statbotics team_years pages, 1 Statbotics
call per active event.
"""
import datetime as dt
import json
import logging
import os
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

from history import lake, store

TBA = 'https://www.thebluealliance.com/api/v3'
SB = 'https://api.statbotics.io/v3'


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'trisonics-scout-history', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def tba(route):
    return _get(TBA + route, {'X-TBA-Auth-Key': os.environ['TBA_KEY']})


def sb(route):
    return _get(SB + route)


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
    events = tba(f'/events/{year}') or []
    now = active(events, today, days_after)
    keys = [e['key'] for e in now]
    summary = {'year': year, 'today': str(today), 'active_events': keys}
    if not keys:
        logging.info('history refresh: no active events')
        return summary

    def per_event(key):
        return key, {w: tba(f'/event/{key}/{w}') for w in ('matches', 'awards', 'teams/statuses', 'teams')}, \
            sb(f'/team_events?event={key}&limit=1000') or []

    with ThreadPoolExecutor(8) as pool:
        fetched = list(pool.map(per_event, keys))
        districts = sorted({f"{year}{e['district']['abbreviation']}" for e in now if e.get('district')})
        dranks = dict(zip(districts, pool.map(lambda d: tba(f'/district/{d}/rankings'), districts)))
    team_years = sb_pages(f'/team_years?year={year}')

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
        teams = [t for _, d, _ in fetched for t in d['teams'] or []]
        numbers = sorted({t['team_number'] for t in teams})
        if numbers:
            con.execute(f"DELETE FROM teams WHERE team_number IN ({','.join(map(str, numbers))})")
            lake.insert_rows(con, 'teams', {t['team_number']: r for t, r in
                                            zip(teams, lake.team_rows(teams))}.values())
        con.execute('DELETE FROM events WHERE year = ?', [year])
        lake.insert_rows(con, 'events', lake.event_rows(events))
        for table in ('matches', 'awards', 'team_events', 'epa_team_events', 'team_matches'):
            con.execute(f'DELETE FROM {table} WHERE event_key IN {in_keys}')
        for key, d, sb_events in fetched:
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
        summary['matches'] = con.execute(f'SELECT count(*) FROM matches WHERE event_key IN {in_keys}').fetchone()[0]
    finally:
        con.close()
    if upload:
        store.upload(path)
        summary['uploaded'] = True
    if not db:
        path.unlink(missing_ok=True)
    logging.info('history refresh %s', summary)
    return summary
