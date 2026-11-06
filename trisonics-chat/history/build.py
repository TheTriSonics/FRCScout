"""Build the history lake from the raw cache sync.py downloaded, layer by layer
(see lake.py): raw -> history/data/lake/<table>.parquet -> history/data/history.duckdb
(what the bot queries, read-only). --db-only remakes the database from the
Parquet files alone. --upload puts the Parquet files in history-source and the
database in history (needs AzureWebJobsStorage, the chat app's storage
connection string). The raw cache can come from the history-source
container instead of sync.py (see README).

  python -m history.build [--db-only] [--upload]
"""
import argparse
import glob
import gzip
import json
from pathlib import Path

from history import lake, store

DATA = Path(__file__).with_name('data')
RAW, LAKE, DB = DATA / 'raw', DATA / 'lake', DATA / 'history.duckdb'


def load(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def raw(pattern):
    """Raw files matching [pattern] (relative to history/data/raw/, see sync.name)."""
    return sorted(glob.glob(str(RAW / pattern)))


def _key(path):
    """tba/matches/2026/2026miwmi.json.gz -> '2026miwmi'."""
    return Path(path).name.removesuffix('.json.gz')


def _each(pattern, fn):
    for p in raw(pattern):
        yield from fn(load(p))


def _teams():
    """TBA's team pages, plus teams only seen in event team lists refresh.py saved (rookies
    registered after the pages were pulled)."""
    seen = set()
    for r in _each('tba/teams/*.json.gz', lake.team_rows):
        seen.add(r['team_number'])
        yield r
    for r in _each('tba/event_teams/*/*.json.gz', lake.team_rows):
        if r['team_number'] not in seen:
            seen.add(r['team_number'])
            yield r


SOURCES = {
    'teams': _teams,
    'events': lambda: _each('tba/events/*/*.json.gz', lake.event_rows),
    'matches': lambda: _each('tba/matches/*/*.json.gz', lake.match_rows),
    'awards': lambda: _each('tba/awards/*/*.json.gz', lake.award_rows),
    'team_events': lambda: (r for p in raw('tba/team_statuses/*/*.json.gz')
                            for r in lake.team_event_rows(_key(p), load(p))),
    'district_rankings': lambda: (r for p in raw('tba/district_rankings/*/*.json.gz')
                                  for r in lake.district_rows(_key(p), load(p))),
    'epa_team_years': lambda: _each('sb/team_years/*/*.json.gz', lake.epa_year_rows),
    'epa_team_events': lambda: _each('sb/team_events/*/*.json.gz', lake.epa_event_rows),
}


def build_lake(memory='1GB'):
    """raw -> lake/<table>.parquet, plus team_matches derived from matches."""
    LAKE.mkdir(parents=True, exist_ok=True)
    con = lake.connect(memory)
    for name in lake.TABLES:
        print(f'{name}: {lake.write_parquet(con, SOURCES[name](), LAKE / f"{name}.parquet")} rows', flush=True)
    lake.matches_view(con, LAKE)
    con.execute(f"COPY ({lake.TEAM_MATCHES.format(where='')}) TO '{LAKE / 'team_matches.parquet'}' {lake.PARQUET}")
    print('team_matches:', con.execute(f"SELECT count(*) FROM '{LAKE / 'team_matches.parquet'}'").fetchone()[0])
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db-only', action='store_true', help='skip raw -> lake; only lake -> history.duckdb')
    ap.add_argument('--upload', action='store_true',
                    help='put lake/*.parquet in history-source and the database in history')
    args = ap.parse_args()
    if not args.db_only:
        build_lake()
    lake.make_db(LAKE, DB, memory='1GB')
    print(f'{DB}: {DB.stat().st_size / 1e6:.0f} MB')
    if args.upload:
        store.put_source(('lake/' + f.name, f) for f in sorted(LAKE.glob('*.parquet')))
        store.upload(DB)
        print('uploaded')


if __name__ == '__main__':
    main()
