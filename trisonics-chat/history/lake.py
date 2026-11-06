"""Shaping TBA and Statbotics responses into the history tables, shared by
build.py (whole lake from the raw cache) and refresh.py (a few live events).

Three layers, each made only from the one before, by format changes:
  raw (bronze): API responses as gzipped JSON, history/data/raw/ and history-source raw/
  lake (silver): one Parquet file per table, lake/<table>.parquet (team_matches is
    derived from matches here)
  history.duckdb (gold): the Parquet tables loaded as is; what the bot queries.

Each *_rows function takes one API response and yields table rows (dicts).
"""
import json
import os
import re
import tempfile
from pathlib import Path

import duckdb

TABLES = ['teams', 'events', 'matches', 'awards', 'team_events', 'district_rankings',
          'epa_team_years', 'epa_team_events']
JSON_COLS = {'red_breakdown', 'blue_breakdown', 'event_points', 'epa_breakdown'}


def tn(key):
    """'frc254' -> 254 ('frc254B' style keys from old events -> 254)."""
    m = re.match(r'frc(\d+)', key or '')
    return int(m.group(1)) if m else None


# TBA mixes full names and postal codes ('Michigan' vs 'MI'); store codes.
STATES = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA',
    'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT',
    'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM',
    'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC', 'Puerto Rico': 'PR', 'Alberta': 'AB', 'British Columbia': 'BC',
    'Manitoba': 'MB', 'New Brunswick': 'NB', 'Newfoundland and Labrador': 'NL', 'Nova Scotia': 'NS',
    'Ontario': 'ON', 'Prince Edward Island': 'PE', 'Quebec': 'QC', 'Québec': 'QC', 'Saskatchewan': 'SK'}


def _state(row):
    if row.get('country') in ('USA', 'Canada') and row.get('state_prov'):
        s = row['state_prov'].strip()
        row['state_prov'] = STATES.get(s, s)
    return row


def team_rows(teams):
    for t in teams or []:
        yield _state({k: t.get(k) for k in ('team_number', 'nickname', 'name', 'school_name', 'city',
                                            'state_prov', 'country', 'rookie_year', 'website')})


def event_rows(events):
    for e in events or []:
        yield _state({'event_key': e['key'], 'year': e['year'], 'name': e.get('name'),
                      'short_name': e.get('short_name'), 'event_type': e.get('event_type_string'),
                      'district': (e.get('district') or {}).get('abbreviation'),
                      'week': None if e.get('week') is None else e['week'] + 1,
                      'start_date': e.get('start_date'), 'end_date': e.get('end_date'),
                      'city': e.get('city'), 'state_prov': e.get('state_prov'), 'country': e.get('country'),
                      'parent_event_key': e.get('parent_event_key'),
                      'playoff_type': e.get('playoff_type_string')})


def match_rows(matches):
    for m in matches or []:
        a, bd = m.get('alliances') or {}, m.get('score_breakdown') or {}
        row = {'match_key': m['key'], 'event_key': m['event_key'], 'year': int(m['event_key'][:4]),
               'comp_level': m.get('comp_level'), 'set_number': m.get('set_number'),
               'match_number': m.get('match_number'), 'time': m.get('actual_time') or m.get('time'),
               'winning_alliance': m.get('winning_alliance') or None}
        for side in ('red', 'blue'):
            s = a.get(side) or {}
            score = s.get('score')
            row[f'{side}_score'] = None if score is None or score < 0 else score
            row[f'{side}_teams'] = [tn(k) for k in s.get('team_keys') or []]
            row[f'{side}_surrogates'] = [tn(k) for k in s.get('surrogate_team_keys') or []]
            row[f'{side}_dqs'] = [tn(k) for k in s.get('dq_team_keys') or []]
            row[f'{side}_breakdown'] = json.dumps(bd[side]) if bd.get(side) else None
        yield row


def award_rows(awards):
    for a in awards or []:
        for r in a.get('recipient_list') or [{}]:
            yield {'event_key': a.get('event_key'), 'year': a.get('year'), 'award_type': a.get('award_type'),
                   'name': a.get('name'), 'team_number': tn(r.get('team_key')), 'awardee': r.get('awardee')}


def team_event_rows(event_key, statuses):
    """One row per team at the event: qual rank and record, alliance, playoff result."""
    for team_key, st in (statuses or {}).items():
        st = st or {}
        qual = st.get('qual') or {}
        rank = qual.get('ranking') or {}
        rec = rank.get('record') or {}
        al = st.get('alliance') or {}
        po = st.get('playoff') or {}
        prec = po.get('record') or {}
        yield {'event_key': event_key, 'year': int(event_key[:4]), 'team_number': tn(team_key),
               'qual_rank': rank.get('rank'), 'num_teams': qual.get('num_teams'),
               'qual_wins': rec.get('wins'), 'qual_losses': rec.get('losses'), 'qual_ties': rec.get('ties'),
               'qual_matches': rank.get('matches_played'),
               'alliance_number': al.get('number'),
               # 0 = captain, 1 = first pick, 2 = second pick, 3 = third pick; None = backup or not picked
               'alliance_pick': al.get('pick') if al.get('pick', -1) >= 0 else None,
               'alliance_backup': bool(al.get('backup')) if al else None,
               'playoff_level': po.get('level'), 'playoff_status': po.get('status'),
               'double_elim_round': po.get('double_elim_round'),
               'playoff_wins': prec.get('wins') if po else None,
               'playoff_losses': prec.get('losses') if po else None,
               'summary': re.sub(r'<[^>]+>', '', st.get('overall_status_str') or '') or None}


def district_rows(district_key, rankings):
    for r in rankings or []:
        yield {'district_key': district_key, 'year': int(district_key[:4]), 'district': district_key[4:],
               'team_number': tn(r.get('team_key')), 'rank': r.get('rank'),
               'point_total': r.get('point_total'), 'rookie_bonus': r.get('rookie_bonus'),
               'event_points': json.dumps(r.get('event_points') or [])}


def epa_year_rows(team_years):
    for t in team_years or []:
        epa, rec = t.get('epa') or {}, t.get('record') or {}
        ranks, stats = epa.get('ranks') or {}, epa.get('stats') or {}
        yield {'team_number': t['team'], 'year': t['year'], 'epa': epa.get('total_points'),
               'epa_norm': epa.get('norm'), 'epa_start': stats.get('start'),
               'epa_pre_champs': stats.get('pre_champs'), 'epa_max': stats.get('max'),
               'world_rank': (ranks.get('total') or {}).get('rank'),
               'world_percentile': (ranks.get('total') or {}).get('percentile'),
               'country_rank': (ranks.get('country') or {}).get('rank'),
               'state_rank': (ranks.get('state') or {}).get('rank'),
               'district_rank': (ranks.get('district') or {}).get('rank'),
               'wins': rec.get('wins'), 'losses': rec.get('losses'), 'ties': rec.get('ties'),
               'winrate': rec.get('winrate'), 'district': t.get('district'), 'state_prov': t.get('state'),
               'country': t.get('country'), 'epa_breakdown': json.dumps(epa.get('breakdown') or {})}


def epa_event_rows(team_events):
    for t in team_events or []:
        epa = t.get('epa') or {}
        stats = epa.get('stats') or {}
        q = (t.get('record') or {}).get('qual') or {}
        yield {'team_number': t['team'], 'year': t['year'], 'event_key': t['event'],
               'epa': epa.get('total_points'), 'epa_norm': epa.get('norm'),
               'epa_start': stats.get('start'), 'epa_pre_elim': stats.get('pre_elim'),
               'epa_mean': stats.get('mean'), 'epa_max': stats.get('max'),
               'qual_rps_per_match': q.get('rps_per_match'),
               'epa_breakdown': json.dumps(epa.get('breakdown') or {})}


def _ndjson(rows):
    f = tempfile.NamedTemporaryFile('w', suffix='.ndjson', delete=False)
    n = 0
    with f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
            n += 1
    return f.name, n


# Row groups capped by size too: a matches row carries ~2 KB of JSON breakdowns.
PARQUET = "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 10000, ROW_GROUP_SIZE_BYTES '8MB')"


def connect(memory='100MB'):
    """A scratch DuckDB for moving data between layers. The defaults fit the Function App's
    512 MB instance: one thread, insertion order not kept, spilling to temp disk."""
    return duckdb.connect(config={'memory_limit': memory, 'threads': 1,
                                  'preserve_insertion_order': False,
                                  'temp_directory': os.path.join(tempfile.gettempdir(), f'duckdb-spill-{os.getpid()}')})


def _typed(path, types):
    """SELECT over an ndjson file with the given (column, type) list; JSON columns cast."""
    cols = ', '.join(f"'{c}': '{'VARCHAR' if c in JSON_COLS else t}'" for c, t in types)
    casts = ', '.join(f'"{c}"::JSON AS "{c}"' if c in JSON_COLS else f'"{c}"' for c, _ in types)
    return f"SELECT {casts} FROM read_json('{path}', format='newline_delimited', columns={{{cols}}})"


def write_parquet(con, rows, out):
    """Silver from bronze: row dicts -> one Parquet file, types inferred. Returns the row count."""
    path, n = _ndjson(rows)
    try:
        src = f"read_json('{path}', format='newline_delimited', sample_size=-1)"
        # Parquet has no HUGEINT (it would become DOUBLE); unix times fit in BIGINT.
        types = [(c, 'BIGINT' if t == 'HUGEINT' else t)
                 for c, t, *_ in con.execute(f'DESCRIBE SELECT * FROM {src}').fetchall()]
        con.execute(f"COPY ({_typed(path, types)}) TO '{out}' {PARQUET}")
    finally:
        os.unlink(path)
    return n


def replace_rows(con, table, keep, rows=None, sql=None):
    """Rewrite one Parquet table in place: the old rows where [keep] (a SQL condition) plus
    the new [rows] (dicts, typed like the file) and/or the rows of [sql]."""
    table = str(table)
    types = [(c, t) for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM '{table}'").fetchall()]
    parts, tmp_json = [f"SELECT * FROM '{table}' WHERE {keep}"], None
    if rows is not None:
        tmp_json, n = _ndjson(rows)
        if n:
            parts.append(_typed(tmp_json, types))
    if sql:
        parts.append(f'SELECT * FROM ({sql})')
    try:
        con.execute(f"COPY ({' UNION ALL BY NAME '.join(parts)}) TO '{table}.new' {PARQUET}")
        os.replace(f'{table}.new', table)
    finally:
        if tmp_json:
            os.unlink(tmp_json)


def make_db(lake_dir, db_path, memory='100MB'):
    """Gold from silver: every lake/<table>.parquet loaded as is into a new DuckDB file."""
    db_path = Path(db_path)
    db_path.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path), config={'memory_limit': memory, 'threads': 1,
                                               'preserve_insertion_order': False})
    try:
        for f in sorted(Path(lake_dir).glob('*.parquet')):
            con.execute(f"CREATE TABLE {f.stem} AS SELECT * FROM '{f}'")
        con.execute('CHECKPOINT')
    finally:
        con.close()


def matches_view(con, lake_dir):
    """TEAM_MATCHES reads a table called matches; point it at the Parquet file."""
    con.execute(f"CREATE OR REPLACE VIEW matches AS SELECT * FROM '{Path(lake_dir) / 'matches.parquet'}'")


# Per team per match, derived from matches. {where} filters matches.
TEAM_MATCHES = """
WITH m AS (SELECT * FROM matches {where}),
sides AS (
  SELECT match_key, event_key, year, comp_level, set_number, match_number, time, 'red' AS alliance,
         red_teams AS teams, red_surrogates AS surrogates, red_dqs AS dqs,
         red_score AS score, blue_score AS opp_score, winning_alliance FROM m
  UNION ALL
  SELECT match_key, event_key, year, comp_level, set_number, match_number, time, 'blue',
         blue_teams, blue_surrogates, blue_dqs, blue_score, red_score, winning_alliance FROM m)
SELECT match_key, event_key, year, comp_level, set_number, match_number, time, alliance,
       u.team_number, u.station, score, opp_score,
       CASE WHEN score IS NULL OR opp_score IS NULL THEN NULL
            WHEN winning_alliance = alliance THEN 'win'
            WHEN winning_alliance IS NULL AND score = opp_score THEN 'tie'
            WHEN winning_alliance IS NULL THEN NULL ELSE 'loss' END AS result,
       list_contains(surrogates, u.team_number) AS surrogate,
       list_contains(dqs, u.team_number) AS dq
FROM sides, UNNEST(teams) WITH ORDINALITY AS u(team_number, station)
WHERE u.team_number IS NOT NULL
"""
