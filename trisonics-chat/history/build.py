"""Build the history lake from the raw cache sync.py downloaded.

Writes history/data/lake/<table>.parquet (the lake) and
history/data/history.duckdb (what the bot queries, read-only).
Upload the .duckdb with --upload (needs AzureWebJobsStorage, the chat app's
storage connection string). The raw cache can come from the history-source
container instead of sync.py (see README).

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
