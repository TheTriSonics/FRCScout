"""Download raw TBA and Statbotics data for the history lake.

Every response is cached as gzipped JSON under history/data/raw/, so a rerun
only fetches what's missing. --refresh YEAR re-downloads one year (the
current season changes; older ones don't).

  source ../trisonics-api/setenv && python history/sync.py 1992 2026
"""
import argparse
import gzip
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAW = Path(__file__).with_name('data') / 'raw'
TBA = 'https://www.thebluealliance.com/api/v3'
SB = 'https://api.statbotics.io/v3'
SB_PAGE = 1000


def name(source, route):
    """'tba', '/event/2026miwmi/matches' -> 'tba/event__2026miwmi__matches.json.gz': the file
    under history/data/raw/ and, with 'raw/' in front, the blob in history-source."""
    return f"{source}/" + route.strip('/').replace('/', '__').replace('?', '__') + '.json.gz'


def _path(source, route):
    return RAW / name(source, route)


def fetch(source, route, refresh=False):
    """Cached GET; returns parsed JSON (None for 404)."""
    path = _path(source, route)
    if path.exists() and not refresh:
        with gzip.open(path, 'rt') as f:
            return json.load(f)
    url = (TBA if source == 'tba' else SB) + route
    headers = {'User-Agent': 'trisonics-scout-history'}
    if source == 'tba':
        headers['X-TBA-Auth-Key'] = os.environ['TBA_KEY']
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            # 404: nothing there; 422: Statbotics has no such year (it starts in 2002)
            if e.code == 404 or (e.code == 422 and source == 'sb'):
                data = None
                break
            if attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(2 ** attempt)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt') as f:
        json.dump(data, f)
    return data


def sync_year(year, refresh, pool):
    events = fetch('tba', f'/events/{year}', refresh) or []
    jobs = []
    for e in events:
        for what in ('matches', 'awards', 'teams/statuses', 'alliances'):
            jobs.append(('tba', f"/event/{e['key']}/{what}"))
    for d in fetch('tba', f'/districts/{year}', refresh) or []:
        jobs.append(('tba', f"/district/{d['key']}/rankings"))
    list(pool.map(lambda j: fetch(*j, refresh=refresh), jobs))
    for table in ('team_years', 'team_events'):
        offset = 0
        while True:
            page = fetch('sb', f'/{table}?year={year}&limit={SB_PAGE}&offset={offset}', refresh) or []
            if len(page) < SB_PAGE:
                break
            offset += SB_PAGE
    print(f'{year}: {len(events)} events, {len(jobs)} event/district calls', flush=True)


def sync_teams(refresh):
    page = 0
    while fetch('tba', f'/teams/{page}', refresh):
        page += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('first', type=int)
    ap.add_argument('last', type=int)
    ap.add_argument('--refresh', type=int, action='append', default=[],
                    help='year to download again (repeatable)')
    args = ap.parse_args()
    sync_teams(bool(args.refresh))
    with ThreadPoolExecutor(8) as pool:
        for year in range(args.first, args.last + 1):
            sync_year(year, year in args.refresh, pool)


if __name__ == '__main__':
    main()
