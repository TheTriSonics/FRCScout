"""history_sql: read-only SQL over the FRC history lake (TBA + Statbotics,
1992 onward) in DuckDB.

Locked down: the database opens read-only, with no file, network or
extension access and the configuration locked, so a query can only read the
lake's tables. One SELECT per call, a time limit, a memory limit and a row cap.
"""
import os
import threading

from history import store  # before duckdb, see history/__init__.py

import duckdb

TIMEOUT_S = 15
MAX_ROWS = 200

SCHEMA = """\
Tables (team_number is an int; event_key like '2024micmp'; year = season):
- teams(team_number, nickname, name, school_name, city, state_prov, country, rookie_year, website)
- events(event_key, year, name, short_name, event_type, district, week, start_date, end_date, city,
  state_prov, country, parent_event_key, playoff_type)
  event_type: 'Regional', 'District', 'District Championship', 'District Championship Division',
  'Championship Division', 'Championship Finals', 'Festival of Champions', 'Remote', 'Offseason',
  'Preseason'. Leave out Offseason/Preseason/Remote/Festival of Champions unless asked. week counts from 1 (championships have none). district is the
  abbreviation ('fim', 'ne', 'fit', ...).
- matches(match_key, event_key, year, comp_level, set_number, match_number, time, winning_alliance,
  red_score, blue_score, red_teams INT[], blue_teams INT[], red_surrogates, blue_surrogates, red_dqs,
  blue_dqs, red_breakdown JSON, blue_breakdown JSON)
  comp_level: 'qm' qual, 'ef' eighths, 'qf', 'sf', 'f'. Double-elim brackets (2023+) put every
  bracket match under 'sf'. Breakdown keys differ every season (e.g. red_breakdown->>'foulPoints',
  'autoPoints', 'teleopPoints'); look at one row first. Scores are null for unplayed matches.
  time is unix seconds.
- team_matches(match_key, event_key, year, comp_level, set_number, match_number, time, alliance, team_number,
  station 1-3, score, opp_score, result 'win'/'loss'/'tie', surrogate, dq): one row per team per match.
- team_events(event_key, year, team_number, qual_rank, num_teams, qual_wins, qual_losses, qual_ties,
  qual_matches, alliance_number, alliance_pick (0 captain, 1 first pick, 2 second, 3 third; null if
  not picked or backup), alliance_backup, playoff_level, playoff_status ('won'/'eliminated'),
  double_elim_round, playoff_wins, playoff_losses, summary)
  playoff_level is the furthest level reached ('f' + playoff_status 'won' = event winner).
- awards(event_key, year, award_type, name, team_number, awardee): one row per recipient.
  award_type 0 Chairman's/Impact, 1 Winner, 2 Finalist, 9 Engineering Inspiration, 10 Rookie All
  Star, 3 Woodie Flowers, ... Use name ILIKE for others.
- district_rankings(district_key, year, district, team_number, rank, point_total, rookie_bonus,
  event_points JSON)
- epa_team_years(team_number, year, epa, epa_norm, epa_start, epa_pre_champs, epa_max, world_rank,
  world_percentile, country_rank, state_rank, district_rank, wins, losses, ties, winrate, district,
  state_prov, country, epa_breakdown JSON): Statbotics EPA (expected points added) per season.
  epa_norm (~1500 average, comparable across years) for comparing seasons; epa is in that
  season's points.
- epa_team_events(team_number, year, event_key, epa, epa_norm, epa_start, epa_pre_elim, epa_mean,
  epa_max, qual_rps_per_match, epa_breakdown JSON)
Coverage: events, teams and awards since 1992 (the first season). Matches from 2002 (2000 has one
event, 1992-2001 none), so records, partners and opponents start in 2002. Statbotics EPA from 2002.
Before 2007 team_events has no qual rank or record (use team_matches); before 2010 alliance picks are
mostly only at Championship and playoff_level is incomplete. Count event wins from awards
(award_type 1, Winner): complete for every year, while team_events playoff results have gaps (some
are stuck at status 'playing'). Alliances were 2 teams in quals through 2004
(red_teams has 2 entries). Say which years an answer covers when older data is thinner.
Season notes: 2015 quals had
no wins or losses (result is null; ranked by average score). 2020 stopped after week 2-3. 2021 had
no normal season (only 'Remote' at-home events, no matches): treat 2020 -> 2022 as consecutive
seasons for streaks. Some team_events rows are not real competition: 2021 "Season Participation"
placeholders (typed 'District') and cancelled 2020 events ("(Cancelled)" in the name), both with no
matches; count a team's events or seasons from team_matches or qual_matches > 0. A team's season
record means all its official events that year added together. Offseason events often have test or bad scores. state_prov is a postal code
for the USA and Canada ('MI', 'ON').
DuckDB SQL: list_contains(red_teams, 254), UNNEST, ->> for JSON fields, QUALIFY, FILTER.
"""


def _connect(path):
    con = duckdb.connect(str(path), read_only=True, config={
        'enable_external_access': False,
        'autoload_known_extensions': False,
        'autoinstall_known_extensions': False,
        'allow_community_extensions': False,
        'memory_limit': os.environ.get('HISTORY_MEMORY', '256MB'),
        'threads': 2,
    })
    con.execute('SET lock_configuration = true')
    return con


def run(sql: str):
    path = store.db_path()
    if not path:
        return {'error': 'The history database is not available.'}
    con = _connect(path)
    try:
        stmts = con.extract_statements(sql)
        if len(stmts) != 1 or stmts[0].type != duckdb.StatementType.SELECT:
            return {'error': 'Send exactly one SELECT (or WITH ... SELECT) statement.'}
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
        return {'error': f'{type(e).__name__}: {str(e)[:800]}'}
    finally:
        con.close()
    out = {'columns': cols, 'rows': [list(r) for r in rows[:MAX_ROWS]]}
    if len(rows) > MAX_ROWS:
        out['truncated'] = f'only the first {MAX_ROWS} rows; aggregate or add LIMIT'
    return out
