"""Shaping TBA and Statbotics responses into the history tables, shared by
build.py (whole lake from the raw cache) and refresh.py (a few live events).

Each *_rows function takes one API response and yields table rows (dicts).
"""
import json
import os
import re
import tempfile

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


def create_table(con, name, rows):
    """CREATE TABLE [name] from row dicts, types inferred. Returns the row count."""
    path, n = _ndjson(rows)
    try:
        src = f"read_json('{path}', format='newline_delimited', sample_size=-1)"
        cols = [c for c, *_ in con.execute(f'DESCRIBE SELECT * FROM {src}').fetchall()]
        casts = ', '.join(f'"{c}"::JSON AS "{c}"' if c in JSON_COLS else f'"{c}"' for c in cols)
        con.execute(f'CREATE TABLE {name} AS SELECT {casts} FROM {src}')
    finally:
        os.unlink(path)
    return n


def insert_rows(con, name, rows):
    """INSERT row dicts into an existing table, using its column types."""
    path, n = _ndjson(rows)
    try:
        if n:
            types = con.execute(f'DESCRIBE {name}').fetchall()
            cols = ', '.join(f"'{c}': '{'VARCHAR' if c in JSON_COLS else t}'" for c, t, *_ in types)
            casts = ', '.join(f'"{c}"::JSON' if c in JSON_COLS else f'"{c}"' for c, *_ in types)
            con.execute(f"INSERT INTO {name} SELECT {casts} FROM read_json('{path}', "
                        f"format='newline_delimited', columns={{{cols}}})")
    finally:
        os.unlink(path)
    return n


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
