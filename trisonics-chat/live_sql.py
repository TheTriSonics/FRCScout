"""sql: one read-only SQL tool over the FRC history lake and this event's live data.

Each Session gets its own in-memory DuckDB per event. The history database is
attached read-only and made the default catalog, so history tables are used
unqualified (teams, matches, ...). The event's live data (the asker's own
scouting and pit records, official results, OPR, rankings) is loaded by us
into the `live` catalog before the connection is locked: no file, network or
extension access and the configuration locked. The model sends one SELECT per
call, with a time limit, a memory limit and a row cap.

Live tables are built with the same loaders as query_data, so the numbers
match the other tools. Scouting data is loaded only for the session's own
secret key, and connections are never shared between sessions.
"""
import logging
import math
import os
import re
import threading

from history import store  # before duckdb, see history/__init__.py

import duckdb

import history_sql
import query_data as qd
import season_2026 as season

TIMEOUT_S = 15
MAX_ROWS = 200

LIVE_SCHEMA = """\
Live tables: ONE event only (default the asker's current event; pass event for another), always
prefixed live. For anything across events or seasons use the history tables instead:
- live.scouted: one row per scouting record by our scouts: match_number (qual), team_number,
  scouter_name, """ + ', '.join(season.STAT_KEYS) + """,
  teleop_active_defense_quality, teleop_inactive_defense_quality (text), match_notes, auto_notes,
  and <rating>_vs_other_scouts for """ + ', '.join(qd.CALIBRATED) + """ (this record minus
  the mean of other scouts' records of the same team, for calibrating scouts). Binary stats are
  0/1; their mean is the share of matches. Accuracy ratings are %.
- live.team_results: one row per team per played official match at this event (quals and playoffs): event_key,
  match_key, comp_level ('qm','sf','f'), set_number, match_number, team_number, alliance,
  partners (text '254,1678'), alliance_score, opponent_score, won (1/0, tie 0.5), margin, rp (quals),
  alliance_hub_fuel, opponent_hub_fuel, hub_fuel_margin, alliance_auto_tower_points,
  alliance_endgame_tower_points, alliance_tower_points, alliance_foul_points.
- live.opr: one row per team: team_number and OPR columns (""" + ', '.join(season.OPR_COLUMNS) + """,
  and more breakdown fields, e.g. hubScore_shift1Count).
- live.pit: every pit scouting record (team_number, drive_train, fuel_capacity, hanging_level, ...;
  several per team possible); live.pit_latest: the newest record per team. For "can it hang/climb"
  use hanging_works (1 = the team says its hang works, 0 = not yet); hanging_level is the level it
  is built for, not proof it works.
- live.rankings: rank, team_number, wins, losses, ties, matches_played, dq, and the ranking sort
  fields (e.g. ranking_score).
- live.event_teams: team_number, name for every team at the event.
Live column lists vary with what was scouted: SELECT * FROM live.pit LIMIT 1 shows them, and an
unknown column error lists the valid ones. History tables (below) cover every event since 1992 (matches since 2002)
from TBA/Statbotics; join them to live tables on team_number (e.g. past seasons' epa_norm).
"""


def _sql_type(vals):
    vals = [v for v in vals if v is not None]
    if vals and all(isinstance(v, bool) for v in vals):
        return 'BOOLEAN'
    if vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        return 'BIGINT'
    if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return 'DOUBLE'
    return 'VARCHAR'


def _load(con, name, rows):
    cols = qd._columns(rows) or ['team_number']
    types = {c: _sql_type([r.get(c) for r in rows]) for c in cols}
    con.execute(f'CREATE TABLE live.{name} (' + ', '.join(f'"{c}" {types[c]}' for c in cols) + ')')
    if rows:
        def cell(v, t):
            if v is None:
                return None
            if t == 'VARCHAR' and not isinstance(v, str):
                return str(v)
            if t == 'DOUBLE' and isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v
        con.executemany(f'INSERT INTO live.{name} VALUES (' + ', '.join('?' * len(cols)) + ')',
                        [[cell(r.get(c), types[c]) for c in cols] for r in rows])
    return len(rows)


def _scouted_with_notes(ev):
    rows = qd._scouted(ev)
    raw = list(ev.scouted())
    for d, r in zip(rows, raw):  # _scouted keeps ev.scouted() order
        for f in ('match_notes', 'auto_notes'):
            d[f] = (r.get(f) or '').strip()[:500] or None
    return rows


def _teams(ev):
    return [{'team_number': int(t['number']), 'name': t.get('name')} for t in ev.teams()]


LOADERS = {
    'scouted': _scouted_with_notes,
    'team_results': qd._team_matches,
    'opr': qd._opr,
    'pit': qd._pit,
    'rankings': qd._rankings,
    'event_teams': _teams,
}


def _connection(session):
    """The session's connection for its event, made on first use. Live tables
    are loaded lazily by _ensure_tables."""
    cache = session.sql_cache
    key = (session.secret_key, session.event_key)
    if key not in cache:
        con = duckdb.connect(':memory:', config={
            'autoload_known_extensions': False,
            'autoinstall_known_extensions': False,
            'allow_community_extensions': False,
            'memory_limit': os.environ.get('HISTORY_MEMORY', '256MB'),
            'threads': 2,
        })
        path = store.db_path()
        if path:
            con.execute(f"ATTACH '{path}' AS h (READ_ONLY)")
            con.execute('USE h')
        con.execute("ATTACH ':memory:' AS live")
        con.execute('SET enable_external_access = false')
        con.execute('SET lock_configuration = true')
        cache[key] = {'con': con, 'loaded': set(), 'empty': set(), 'history': bool(path)}
    return cache[key]


_LIVE_REF = re.compile(r'\blive\s*\.\s*"?(\w+)', re.I)


def _ensure_tables(session, c, sql):
    """Load the live tables the query names (all of them for live.* lookups
    of the catalog itself, e.g. information_schema)."""
    wanted = {m.lower() for m in _LIVE_REF.findall(sql)}
    if 'pit_latest' in wanted:
        wanted.add('pit')
    if wanted - set(LOADERS) - {'pit_latest'} or re.search(r'information_schema|duckdb_', sql, re.I):
        wanted |= set(LOADERS)  # unknown name or a catalog lookup: load all
    ev = session.event
    con = c['con']
    for name in [n for n in LOADERS if n in wanted and n not in c['loaded']]:
        try:
            n = _load(con, name, LOADERS[name](ev))
        except Exception:
            logging.exception('live_sql: loading %s failed', name)
            con.execute(f'CREATE TABLE IF NOT EXISTS live.{name} (team_number BIGINT)')
            n = 0
        c['loaded'].add(name)
        if not n:
            c['empty'].add(name)
        if name == 'pit':
            con.execute('CREATE TABLE live.pit_latest AS SELECT * FROM live.pit QUALIFY '
                        'row_number() OVER (PARTITION BY team_number ORDER BY rowid DESC) = 1')


def _round(v):
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 3)
    return v


def run(session, sql: str):
    logging.info('sql %s %s', session.event_key, sql)
    c = _connection(session)
    con = c['con']
    try:
        stmts = con.extract_statements(sql)
        if len(stmts) != 1 or stmts[0].type != duckdb.StatementType.SELECT:
            return {'error': 'Send exactly one SELECT (or WITH ... SELECT) statement.'}
        _ensure_tables(session, c, sql)
        timer = threading.Timer(TIMEOUT_S, con.interrupt)
        timer.start()
        try:
            cur = con.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
        finally:
            timer.cancel()
    except duckdb.InterruptException:
        return {'error': f'Query took over {TIMEOUT_S}s; narrow it (filter by year/event first).'}
    except duckdb.Error as e:
        out = {'error': f'{type(e).__name__}: {str(e)[:800]}'}
        if not c['history']:
            out['note'] = 'The history database is not available; only live.* tables work.'
        return out
    out = {'columns': cols, 'rows': [[_round(v) for v in r] for r in rows[:MAX_ROWS]]}
    if len(rows) > MAX_ROWS:
        out['truncated'] = f'only the first {MAX_ROWS} rows; aggregate or add LIMIT'
    empty = sorted(c['empty'] & {m.lower() for m in _LIVE_REF.findall(sql)})
    if empty:
        out['empty_live_tables'] = empty
    return out


DESCRIPTION = (
    'Read-only SQL (DuckDB) over two kinds of data at once. 1) This event\'s live data in the live '
    'catalog: our scouting records, pit records, official match results, OPR and rankings. Use it '
    'for ad-hoc cuts the fixed tools can\'t do: filters, group-bys, before/after a match number, '
    'comparing alliances or comp levels, correlations (corr(x, y), regr_slope), calibrating scouts. '
    '2) FRC history from TBA and Statbotics since 1992 (matches since 2002): results, rankings, alliances, awards, '
    'district points, EPA, for questions across seasons or events. The two join on team_number. '
    'Scope: a question about a team\'s partners, opponents, record, wins or "most often/ever" that '
    'names no event is about its whole history (history tables, not live.*); use live.* only when '
    'the question is about this event (or another named event). '
    'Prefer the fixed tools for common questions (team_info, leaderboard, matches, rankings, '
    'pit_data). One SELECT; max 200 rows, so aggregate; floats rounded to 3 decimals.\n'
    + LIVE_SCHEMA + '\nHistory tables (unqualified):\n' + history_sql.SCHEMA)
