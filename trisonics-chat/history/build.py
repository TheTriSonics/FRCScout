"""Build the history lake from the raw cache sync.py downloaded.

Writes history/data/lake/<table>.parquet (the lake) and
history/data/history.duckdb (what the bot queries, read-only).
Upload the .duckdb with --upload (needs AzureWebJobsStorage, the chat app's
storage connection string).

  python -m history.build [--upload]
"""
import argparse
import glob
import gzip
import json
from pathlib import Path

import duckdb

from history import lake, store

DATA = Path(__file__).with_name('data')
RAW, LAKE, DB = DATA / 'raw', DATA / 'lake', DATA / 'history.duckdb'


def load(path):
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def raw(source, pattern):
    return sorted(glob.glob(str(RAW / source / pattern)))


def _name(path, prefix, suffix):
    return Path(path).name.removeprefix(prefix).removesuffix(suffix)


def _each(pattern, fn, source='tba'):
    for p in raw(source, pattern):
        yield from fn(load(p))


SOURCES = {
    'teams': lambda: _each('teams__*.json.gz', lake.team_rows),
    'events': lambda: _each('events__*.json.gz', lake.event_rows),
    'matches': lambda: _each('event__*__matches.json.gz', lake.match_rows),
    'awards': lambda: _each('event__*__awards.json.gz', lake.award_rows),
    'team_events': lambda: (r for p in raw('tba', 'event__*__teams__statuses.json.gz')
                            for r in lake.team_event_rows(
                                _name(p, 'event__', '__teams__statuses.json.gz'), load(p))),
    'district_rankings': lambda: (r for p in raw('tba', 'district__*__rankings.json.gz')
                                  for r in lake.district_rows(
                                      _name(p, 'district__', '__rankings.json.gz'), load(p))),
    'epa_team_years': lambda: _each('team_years__*.json.gz', lake.epa_year_rows, 'sb'),
    'epa_team_events': lambda: _each('team_events__*.json.gz', lake.epa_event_rows, 'sb'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upload', action='store_true')
    args = ap.parse_args()
    LAKE.mkdir(parents=True, exist_ok=True)
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    for name in lake.TABLES:
        print(f'{name}: {lake.create_table(con, name, SOURCES[name]())} rows', flush=True)
    con.execute('CREATE TABLE team_matches AS ' + lake.TEAM_MATCHES.format(where=''))
    print('team_matches:', con.execute('SELECT count(*) FROM team_matches').fetchone()[0])
    for (name,) in con.execute('SHOW TABLES').fetchall():
        con.execute(f"COPY {name} TO '{LAKE / name}.parquet' (FORMAT parquet, COMPRESSION zstd)")
    con.execute('CHECKPOINT')
    con.close()
    print(f'{DB}: {DB.stat().st_size / 1e6:.0f} MB')
    if args.upload:
        store.upload(DB)
        print('uploaded')


if __name__ == '__main__':
    main()
