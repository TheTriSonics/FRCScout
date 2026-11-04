"""Read-only tools the chat agent can call.

Every tool gets a Session (who's asking, which secret key and event); the
model never chooses the secret key. Results are plain dicts, which the agent
sends back to the model as JSON.
"""
import statistics
import time
import re
from dataclasses import dataclass, replace

import season_2026 as season
from scout_data import (Event, match_label, match_sort_key, match_start,
                        team_num, voter_key)


@dataclass
class Session:
    secret_key: str
    event_key: str
    scouter_name: str = ''
    team_number: int = 0

    @property
    def event(self):
        return Event(self.secret_key, self.event_key)


def _r(x, n=2):
    return None if x is None else round(x, n)


def _played(m):
    score = m['alliances']['red'].get('score')
    return score is not None and score >= 0 and bool(m.get('actual_time') or m.get('post_result_time'))


def _mean(v):
    return statistics.fmean(v) if v else None


# --- aggregation (same rules as the app's TeamStats) ---

def _team_rows(ev):
    by_team = {}
    for row in ev.scouted():
        by_team.setdefault(int(row['team_number']), []).append(row)
    return by_team


def _team_means(rows):
    vals = {}
    for row in rows:
        for k, v in season.row_stats(row).items():
            vals.setdefault(k, []).append(v)
    return {k: _mean(v) for k, v in vals.items()}, vals


def _all_means(ev):
    return {tn: _team_means(rows)[0] for tn, rows in _team_rows(ev).items()}


def _rank_table(ev):
    data = ev.rankings()
    names = [s['name'] for s in data.get('sort_order_info') or []]
    out = {}
    for r in data.get('rankings') or []:
        rec = r.get('record') or {}
        out[team_num(r['team_key'])] = {
            'rank': r.get('rank'),
            'record': f"{rec.get('wins', 0)}-{rec.get('losses', 0)}-{rec.get('ties', 0)}",
            'matches_played': r.get('matches_played'),
            **{n: v for n, v in zip(names, r.get('sort_orders') or []) if n},
        }
    return out


def _match_summary(ev, m, sb=None, breakdown=False, team=None):
    red, blue = m['alliances']['red'], m['alliances']['blue']
    played = _played(m)
    out = {
        'match': match_label(m),
        'key': m['key'],
        'time': ev.fmt_time(match_start(m)),
        'red': [team_num(t) for t in red['team_keys']],
        'blue': [team_num(t) for t in blue['team_keys']],
        'played': played,
    }
    if played:
        out.update(red_score=red.get('score'), blue_score=blue.get('score'),
                   winner=m.get('winning_alliance') or 'tie')
        bd = m.get('score_breakdown') or {}
        for side in ('red', 'blue'):
            b = bd.get(side) or {}
            if b:
                out[f'{side}_rp'] = b.get('rp')
                out[f'{side}_hub_fuel'] = (b.get('hubScore') or {}).get('totalCount')
        if breakdown:
            out['score_breakdown'] = bd
        if team:
            side = 'red' if f'frc{team}' in red['team_keys'] else 'blue'
            us, them = (red, blue) if side == 'red' else (blue, red)
            wa = m.get('winning_alliance') or ''
            res = 'T' if not wa else ('W' if wa == side else 'L')
            out['result_for_team'] = f"{res} {us.get('score')}-{them.get('score')} ({side})"
    if sb and sb.get('pred'):
        p = sb['pred']
        out['statbotics_prediction'] = {
            'red_win_prob': p.get('red_win_prob'), 'red_score': _r(p.get('red_score'), 0),
            'blue_score': _r(p.get('blue_score'), 0)}
    return out


# --- tools ---

def event_info(s: Session):
    ev = s.event
    info = ev.info()
    matches = sorted(ev.matches(), key=match_sort_key)
    quals = [m for m in matches if m['comp_level'] == 'qm']
    played = [m for m in quals if _played(m)]
    nxt = next((m for m in matches if not _played(m)), None)
    return {
        'now': ev.now_str(),
        'event': {**{k: info.get(k) for k in ('key', 'name', 'city', 'state_prov',
                                              'start_date', 'end_date', 'timezone')},
                  'week': None if info.get('week') is None else int(info['week']) + 1},
        'teams': len(ev.teams()),
        'qual_matches': len(quals),
        'qual_matches_played': len(played),
        'next_unplayed_match': _match_summary(ev, nxt) if nxt else None,
        'scouted_rows': len(ev.scouted()),
        'pit_records': len(ev.pit()),
    }


def list_teams(s: Session):
    ranks = _rank_table(s.event)
    return [{'team': t['number'], 'name': t.get('name'),
             'rank': (ranks.get(t['number']) or {}).get('rank')}
            for t in sorted(s.event.teams(), key=lambda t: t['number'])]


def team_info(s: Session, team: int):
    ev = s.event
    names = ev.team_names()
    if team not in names:
        return {'error': f'Team {team} is not at {s.event_key}.'}
    rows = _team_rows(ev).get(team, [])
    means, vals = _team_means(rows)
    all_means = _all_means(ev)
    scouted = {}
    for key, label, section, binary in season.STATS:
        if means.get(key) is None:
            continue
        others = [m[key] for m in all_means.values() if m.get(key) is not None]
        entry = {'label': label, 'section': section,
                 'mean': _r(means[key]), 'event_avg': _r(_mean(others)),
                 'rank_of': f"{1 + sum(o > means[key] for o in others)}/{len(others)}"}
        if binary:
            entry['note'] = 'share of scouted matches (0-1)'
        elif len(vals[key]) > 1:
            entry['stdev'] = _r(statistics.stdev(vals[key]))
            entry['max'] = max(vals[key])
        scouted[key] = entry
    opr = ev.opr().get(team) or {}
    pits = [p for p in ev.pit() if int(p.get('team_number', 0)) == team]
    matches = [m for m in sorted(ev.matches(), key=match_sort_key)
               if f'frc{team}' in m['alliances']['red']['team_keys'] + m['alliances']['blue']['team_keys']]
    sb = ev.statbotics()
    return {
        'team': team, 'name': names[team],
        'ranking': _rank_table(ev).get(team),
        'opr': {label: _r(opr.get(col)) for col, label in season.OPR_COLUMNS.items() if col in opr},
        'scouted_rows': len(rows),
        'scouted_matches': sorted({r['match_number'] for r in rows}),
        'scouted_averages': scouted,
        'scout_notes': [f"Q{r['match_number']} ({r.get('scouter_name')}): {r.get('match_notes').strip()}"
                        for r in sorted(rows, key=lambda r: r['match_number'])
                        if (r.get('match_notes') or '').strip()],
        'pit_records': [{k: v for k, v in p.items()
                         if k not in season.PIT_SKIP and v not in (None, '', [])} for p in pits],
        'pit_photo_count': sum(len(p.get('image_names') or []) for p in pits),
        'matches': [_match_summary(ev, m, sb.get(m['key']), team=team) for m in matches],
        'record': _record(ev, matches, team),
    }


def _record(ev, ms, team):
    out = {}
    for m in ms:
        if not _played(m):
            continue
        s = _match_summary(ev, m, team=team)['result_for_team'][0]
        part = 'quals' if m['comp_level'] == 'qm' else 'playoffs'
        w, l, t = out.get(part, (0, 0, 0))
        out[part] = (w + (s == 'W'), l + (s == 'L'), t + (s == 'T'))
    return {k: f'{w}-{l}-{t}' for k, (w, l, t) in out.items()}


def leaderboard(s: Session, metric: str, top_n: int = 10, lowest_first: bool = False):
    ev = s.event
    names = ev.team_names()
    counts = {}
    if metric in season.STAT_LABEL:
        values = {tn: m.get(metric) for tn, m in _all_means(ev).items()}
        counts = {tn: len({r['match_number'] for r in rows}) for tn, rows in _team_rows(ev).items()}
        label, source = season.STAT_LABEL[metric], 'scouted average'
    elif metric in season.OPR_COLUMNS:
        values = {tn: r.get(metric) for tn, r in ev.opr().items()}
        label, source = season.OPR_COLUMNS[metric], 'OPR'
    else:
        ranks = _rank_table(ev)
        fields = {k for r in ranks.values() for k in r} - {'record'}
        if metric not in fields:
            return {'error': f'Unknown metric {metric!r}.',
                    'scouted_metrics': season.STAT_KEYS,
                    'opr_metrics': list(season.OPR_COLUMNS),
                    'ranking_metrics': sorted(fields)}
        values = {tn: r.get(metric) for tn, r in ranks.items()}
        label, source = metric, 'official rankings'
        if metric == 'rank':
            lowest_first = not lowest_first
    ranked = sorted(((tn, v) for tn, v in values.items() if v is not None),
                    key=lambda x: x[1], reverse=not lowest_first)
    return {'metric': label, 'source': source,
            'teams_with_data': len(ranked),
            'rows': [{'place': i + 1, 'team': tn, 'name': names.get(tn), 'value': _r(v),
                      **({'scouted_matches': counts[tn]} if tn in counts else {})}
                     for i, (tn, v) in enumerate(ranked[:max(1, min(top_n, 80))])]}


def scouted_rows(s: Session, team: int = None, match_number: int = None):
    rows = s.event.scouted()
    if team:
        rows = [r for r in rows if int(r['team_number']) == team]
    if match_number:
        rows = [r for r in rows if int(r['match_number']) == match_number]
    rows = sorted(rows, key=lambda r: (r['match_number'], r['team_number']))
    if len(rows) > 60:
        return {'error': f'{len(rows)} rows match; narrow it with team or match_number, '
                         'or use team_info / leaderboard for averages.'}
    out = []
    for r in rows:
        d = {'match': r['match_number'], 'team': r['team_number'], 'scouter': r.get('scouter_name')}
        d.update({k: _r(v) for k, v in season.row_stats(r).items()})
        d.update({k: r.get(k) for k in season.TEXT_FIELDS
                  if r.get(k) not in (None, '', 'N/A')})
        out.append(d)
    return {'rows': out}


def pit_data(s: Session, team: int = None, fields: list = None):
    recs = s.event.pit()
    if team:
        recs = [p for p in recs if int(p.get('team_number', 0)) == team]
        if not recs:
            return {'error': f'No pit scouting for team {team} yet.'}
    out = []
    for p in sorted(recs, key=lambda p: p.get('team_number', 0)):
        d = {k: v for k, v in p.items() if k not in season.PIT_SKIP and v not in (None, '', [])}
        if fields:
            d = {k: v for k, v in d.items() if k in fields or k == 'team_number'}
        d['photo_count'] = len(p.get('image_names') or [])
        out.append(d)
    return {'records': out}


def matches(s: Session, team: int = None, match: str = None, include_breakdown: bool = False):
    ev = s.event
    ms = sorted(ev.matches(), key=match_sort_key)
    if team:
        tk = f'frc{team}'
        ms = [m for m in ms if tk in m['alliances']['red']['team_keys'] + m['alliances']['blue']['team_keys']]
    if match:
        q = str(match).lower().strip()
        if q.isdigit():
            q = f'qm{q}'
        ms = [m for m in ms if m['key'].lower().endswith('_' + q)]
    sb = ev.statbotics()
    detail = include_breakdown and len(ms) <= 2
    return {'now': ev.now_str(),
            'matches': [_match_summary(ev, m, sb.get(m['key']), detail, team) for m in ms]}


def rankings(s: Session):
    ranks = _rank_table(s.event)
    names = s.event.team_names()
    return {'rankings': [{'team': tn, 'name': names.get(tn), **r}
                         for tn, r in sorted(ranks.items(), key=lambda x: x[1]['rank'] or 999)]}


def scouting_status(s: Session):
    ev = s.event
    by_match = {}
    for r in ev.scouted():
        by_match.setdefault(int(r['match_number']), set()).add(int(r['team_number']))
    quals = [m for m in sorted(ev.matches(), key=match_sort_key) if m['comp_level'] == 'qm']
    missing, complete, played = [], 0, 0
    for m in quals:
        if not _played(m):
            continue
        played += 1
        teams = [team_num(t) for t in m['alliances']['red']['team_keys'] + m['alliances']['blue']['team_keys']]
        gaps = [t for t in teams if t not in by_match.get(m['match_number'], set())]
        if gaps:
            missing.append({'match': m['match_number'], 'unscouted_teams': gaps})
        else:
            complete += 1
    pitted = {int(p.get('team_number', 0)) for p in ev.pit()}
    names = ev.team_names()
    return {
        'qual_matches_played': played,
        'fully_scouted': complete,
        'matches_with_gaps': missing,
        'pit_scouted': len(pitted & set(names)),
        'teams': len(names),
        'teams_without_pit_scouting': sorted(set(names) - pitted),
    }


def scout_schedule(s: Session, person: str = None):
    ev = s.event
    sched = ev.schedule()
    if not sched:
        return {'error': 'No scouting schedule has been published for this event.'}
    offset = int(sched.get('time_offset') or 0)
    times = {m['match_number']: match_start(m) for m in ev.matches() if m['comp_level'] == 'qm'}

    shifts = sched.get('shifts') or []
    if person:
        want = voter_key(person)
        mine = [sh for sh in shifts if voter_key(sh['scouter_name']) == want]
        if not mine:
            close = sorted({sh['scouter_name'] for sh in shifts
                            if want.split('-')[0] in voter_key(sh['scouter_name'])})
            return {'error': f'{person!r} has no shifts.', 'similar_names': close}
        shifts = mine
    now = time.time()
    # A shift runs from its first match's start to about 7 minutes after its
    # last match starts.
    rows = []
    for sh in sorted(shifts, key=lambda x: (x['first_match'], x['station'])):
        start = times.get(sh['first_match'])
        end = times.get(sh['last_match'])
        start = start + offset if start else None
        end = end + offset + 420 if end else None
        if start is None:
            status = 'unknown time'
        elif now < start:
            mins = round((start - now) / 60)
            status = f'upcoming, starts in {mins // 60}h {mins % 60}m' if mins >= 60 else f'upcoming, starts in {mins}m'
        elif end and now <= end:
            status = 'in progress'
        else:
            status = 'done'
        rows.append({'scouter': sh['scouter_name'], 'station': sh['station'],
                     'matches': f"{sh['first_match']}-{sh['last_match']}",
                     'starts': ev.fmt_time(start), 'status': status})
    upcoming = [r for r in rows if r['status'].startswith(('upcoming', 'in progress'))]
    return {
        'now': ev.now_str(),
        'published_by': sched.get('published_by'),
        'published_at': sched.get('published_at'),
        'practice_run': bool(offset),
        'next_or_current_shift': upcoming[0] if person and upcoming else None,
        'shifts': rows,
    }


LEVELS = {'f': 'the finals', 'sf': 'the semifinals', 'qf': 'the quarterfinals', 'ef': 'the eighthfinals'}


def team_events(s: Session, team: int, year: int = None):
    from scout_data import get
    out = get('GetTeamEvents', team_number=team, year=year or int(s.event_key[:4]))
    for e in (out or {}).get('events', []):
        p = e.get('playoff')
        if p:
            # Double-elim brackets label every match 'sf'; the round is what counts.
            stage = p.pop('bracket_round', None) or LEVELS.get(p.get('level'), p.get('level'))
            p.pop('level', None)
            p['result'] = 'won the event' if p.get('status') == 'won' else f"{p.get('status')} in {stage}"
    return out


def find_event(s: Session, query: str, year: int = None):
    from scout_data import get
    year = year or int(s.event_key[:4])
    q = query.lower().strip()
    words = [w for w in re.split(r'[^a-z0-9]+', q) if w]
    events = get('GetEvents', year=year) or []
    home = s.event.info().get('state_prov')  # rank our own state's events first
    hits = []
    for e in events:
        name = e.get('name') or ''
        initials = ''.join(w[0] for w in re.split(r'[^A-Za-z0-9]+', name) if w and w[0].isupper()).lower()
        hay = ' '.join(str(e.get(k) or '') for k in (
            'key', 'event_code', 'name', 'short_name', 'city', 'state_prov', 'location_name')).lower()
        if q == e.get('key') or q == (e.get('event_code') or '').lower():
            score = 100
        elif words and all(w in hay or w in initials for w in words):
            score = 10 + sum(w in (e.get('short_name') or '').lower() for w in words) \
                + (5 if home and e.get('state_prov') == home else 0)
        else:
            continue
        hits.append((score, e.get('start_date') or '', e))
    hits.sort(key=lambda h: (-h[0], h[1]))
    return {'year': year, 'matches': [
        {'event_key': e['key'], 'name': e.get('name'), 'type': e.get('event_type_string'),
         'start_date': e.get('start_date'), 'city': e.get('city'), 'state_prov': e.get('state_prov')}
        for _, _, e in hits[:8]]}


# --- clusters (same settings resolution as the app's ClusterProvider, minus
# per-device custom configs: the team default, else the API's defaults) ---

def _feature_label(name, source):
    """Same as the app's ClusterFeature.label: hubScore_teleopCount ->
    OPR Hub Score Teleop Count."""
    words = ' '.join(w[:1].upper() + w[1:] for w in
                     re.split(r'[_\s]+', re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)) if w)
    return f'OPR {words}' if source == 'opr' and not words.startswith('Opr') else words


def _clustering(s: Session):
    from scout_data import get
    year = int(s.event_key[:4])
    cfg = get('GetClusterConfig', secret_key=s.secret_key, year=year)
    params = {'event_key': s.event_key, 'secret_team_key': s.secret_key, 'k': 4}
    if cfg and cfg.get('features'):
        params['features'] = ','.join(cfg['features'])
        params['k'] = int(cfg.get('k') or 4)
        if cfg.get('weights'):
            params['weights'] = ','.join(f'{f}:{w}' for f, w in cfg['weights'].items())
        source = f"team default published by {cfg.get('updated_by')} ({(cfg.get('updated_at') or '')[:10]})"
    else:
        source = 'built-in defaults (no team default published)'
    result = get('GetClusters', **params)
    src = {f['name']: f.get('source') for f in result.get('available_features') or []}
    labels = {f: _feature_label(f, src.get(f)) for f in src}
    return result, source, labels


def clusters(s: Session):
    result, source, labels = _clustering(s)
    if not result.get('groups'):
        return {'error': 'Not enough data to cluster this event yet.', 'settings': source}
    names = s.event.team_names()
    metric = result.get('strength_metric')
    weights = result.get('weights') or {}
    return {
        'settings': source,
        'dimensions': [labels.get(f, f) + (f' (x{weights[f]} weight)' if f in weights else '')
                       for f in result.get('features') or []],
        'groups_strongest_first': [{
            'group': g['group'],
            'teams': [f'{t} {names.get(t) or ""}'.strip() for t in g['teams']],
            'strength': f"avg {labels.get(metric, metric)} {g.get('strength')}" if metric else None,
            'stands_out_on': [f"{labels.get(p['feature'], p['feature'])}: {p['mean']} vs event "
                              f"{p['event_mean']} ({(p['z'] or 0):+.1f} SD)" for p in g['profile'][:4]],
        } for g in result['groups']],
        'not_clustered': {'excluded': result.get('excluded'), 'no_opr_yet': result.get('dropped')},
    }


def similar_teams(s: Session, team: int, count: int = 5):
    from cluster_similarity import ClusterSpace
    result, source, labels = _clustering(s)
    space = ClusterSpace(result)
    if team not in space.coords:
        return {'error': f'Team {team} is not in the clustering (no scouting or OPR data).',
                'settings': source}
    names = s.event.team_names()
    near = space.neighbors(team, max(1, min(count, 10)))
    for n in near:
        n['name'] = names.get(n['team'])
    dist = space.distinctions(team, [n['team'] for n in near])
    return {
        'settings': source,
        'team': team, 'name': names.get(team), 'group': space.group.get(team),
        'group_mates': [t for t, g in space.group.items() if g == space.group.get(team) and t != team],
        'nearest': near,
        'what_sets_it_apart': [{
            'dimension': labels.get(d['feature'], d['feature']),
            'share_of_difference_pct': d['share_pct'],
            'value': d['value'], 'event_mean': d['event_mean'], 'z': d['z'],
            'neighbors': d['neighbor_values'],
        } for d in dist[:6] if d['share_pct'] >= 1],
        'note': 'Similarity = closeness across all clustering dimensions (z-scored, weighted). '
                'closer_than_pct_of_pairs = share of team pairs at the event that are farther apart.',
    }


import ast
import math
import operator

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS_MATH = {name: getattr(math, name) for name in (
    'sqrt', 'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2', 'radians', 'degrees',
    'log', 'log10', 'exp', 'floor', 'ceil', 'hypot', 'comb', 'factorial')}
_FUNCS_MATH.update(abs=abs, round=round, min=min, max=max, sum=sum,
                   mean=statistics.fmean, median=statistics.median, stdev=statistics.stdev)
_CONSTS = {'pi': math.pi, 'e': math.e}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e) for e in node.elts]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError('exponent too large')
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS_MATH \
            and not node.keywords:
        return _FUNCS_MATH[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError(f'not allowed: {ast.dump(node)[:60]}')


def calculate(s: Session, expressions: list):
    """Evaluate arithmetic safely (numbers, + - * / // % **, math functions)."""
    out = []
    for expr in expressions[:20]:
        try:
            if len(expr) > 300:
                raise ValueError('expression too long')
            val = _eval(ast.parse(expr, mode='eval').body)
            out.append({'expression': expr, 'result': round(val, 6) if isinstance(val, float) else val})
        except Exception as e:
            out.append({'expression': expr, 'error': str(e)})
    return {'results': out}


def scouters(s: Session):
    return {'scouters': [{'name': x.get('scouter_name'), 'last_seen': x.get('last_seen'),
                          'slack_linked': x.get('slack_linked')}
                         for x in s.event.scouters()]}


def pick_board(s: Session):
    """Port of PickBoard.rows (lib/models/pick_board.dart), minVotes = 1."""
    ev = s.event
    data = ev.pick_votes()
    taken = set((data.get('taken') or {}).get('teams') or [])
    voters = []
    for b in data.get('lists') or []:
        teams = b.get('teams') or []
        if any(t.get('ranking') or t.get('dnp') for t in teams):
            voters.append(b)
    ranks, dnp = {}, {}
    for b in voters:
        vk = voter_key(b.get('voter'))
        for t in b['teams']:
            if t.get('ranking'):
                ranks.setdefault(t['team_number'], {})[vk] = t['ranking']
            elif t.get('dnp'):
                dnp.setdefault(t['team_number'], []).append(b.get('voter'))
    longest = max((sum(1 for t in b['teams'] if t.get('ranking')) for b in voters), default=0)
    n = max(len(ev.teams()), longest)

    def votes_at(tn, k):
        return sum(1 for r in ranks[tn].values() if r == k)

    def mean_rank(tn):
        return sum(ranks.get(tn, {}).get(voter_key(b.get('voter')), n + 1) for b in voters) / max(1, len(voters))

    def order(tn):
        return (-len(ranks[tn]), mean_rank(tn), tn)

    names = ev.team_names()

    def row(tn, spot=None):
        d = {'team': tn, 'name': names.get(tn), 'spot': spot,
             'on_lists': len(ranks[tn]), 'taken': tn in taken}
        if spot and len(voters) >= 2:
            d['agreement'] = f'{votes_at(tn, spot)}/{len(voters)} put it at #{spot}'
        if dnp.get(tn):
            d['dnp_by'] = dnp[tn]
        return d

    open_ = set(ranks)
    rows = []
    for k in range(1, longest + 1):
        if not open_:
            break
        most = max(votes_at(tn, k) for tn in open_)
        if most == 0:
            continue
        winners = sorted((tn for tn in open_ if votes_at(tn, k) == most), key=order)
        open_ -= set(winners)
        rows += [row(tn, k) for tn in winners]
    rows += [row(tn) for tn in sorted(open_, key=order)]
    notes = [{'voter': b.get('voter'), 'team': t['team_number'], 'note': t['notes']}
             for b in voters for t in b['teams'] if (t.get('notes') or '').strip()]
    return {
        'voters': [b.get('voter') for b in voters],
        'board': rows,
        'taken_by_other_alliances': sorted(taken),
        'dnp_only_teams': sorted(set(dnp) - set(ranks)),
        'ballots': {b.get('voter'): [t['team_number'] for t in sorted(
            (t for t in b['teams'] if t.get('ranking')), key=lambda t: t['ranking'])] for b in voters},
        'notes': notes,
    }


# --- tool definitions for the API ---

def _schema(props=None, required=()):
    return {'type': 'object', 'properties': props or {}, 'required': list(required),
            'additionalProperties': False}


TEAM = {'type': 'integer', 'description': 'FRC team number, e.g. 4003'}

TOOLS = [
    (event_info, 'event_info',
     'Event name, dates, current local time, how many qual matches exist and have been '
     'played, the next unplayed match, and how much scouting data exists. Call this first '
     'when a question depends on "now", "next" or "so far".', _schema()),
    (list_teams, 'list_teams', 'Every team at the event with name and current rank.', _schema()),
    (team_info, 'team_info',
     'Everything about one team: qual rank, W-L record for quals and playoffs separately, OPR, scouted averages (with event '
     'average and rank for each stat), every scout note, pit scouting answers, and all its '
     'matches (played results and upcoming with Statbotics predictions).',
     _schema({'team': TEAM}, ['team'])),
    (leaderboard, 'leaderboard',
     'Rank all teams by one metric. Metrics: scouted averages ('
     + ', '.join(season.STAT_KEYS) + '); OPR columns (' + ', '.join(season.OPR_COLUMNS)
     + '); or official ranking fields (rank, matches_played, or a ranking sort-order name '
     'like "Ranking Score"). An unknown metric returns the valid list.',
     _schema({'metric': {'type': 'string'},
              'top_n': {'type': 'integer', 'description': 'How many teams (default 10, max 80)'},
              'lowest_first': {'type': 'boolean', 'description': 'Sort ascending instead'}},
             ['metric'])),
    (scouted_rows, 'scouted_rows',
     'Individual match-scouting records (one per team per match per scout) with every stat '
     'and the notes. Filter by team and/or qual match number; max 60 rows.',
     _schema({'team': TEAM, 'match_number': {'type': 'integer', 'description': 'Qual match number'}})),
    (pit_data, 'pit_data',
     'Pit scouting answers (drive train, capacity, auto starts, hanging, plans, notes). One '
     'team, or every team; use fields to limit columns when asking about all teams.',
     _schema({'team': TEAM, 'fields': {'type': 'array', 'items': {'type': 'string'},
                                       'description': 'Pit field names to keep, e.g. ["drive_train","fuel_capacity"]'}})),
    (matches, 'matches',
     'Official match schedule and results (teams, times, scores, RP, hub fuel) with '
     'Statbotics predictions. Filter by team, or by match ("12" or "qm12" for quals, '
     '"sf3m1", "f1m2"). include_breakdown adds the full official score breakdown when '
     'one or two matches are selected.',
     _schema({'team': TEAM, 'match': {'type': 'string'}, 'include_breakdown': {'type': 'boolean'}})),
    (rankings, 'rankings',
     'The official qualification rankings table (quals only: no playoff results). For a '
     "team's playoff record or how far its alliance went, use team_info or matches.", _schema()),
    (scouting_status, 'scouting_status',
     'Which played qual matches are missing scouting for which teams, and which teams have '
     'no pit scouting yet.', _schema()),
    (scout_schedule, 'scout_schedule',
     "The team's published match-scouting schedule (who scouts which station for which "
     'matches, with start times). Give person to get one scout\'s shifts.',
     _schema({'person': {'type': 'string', 'description': 'Scout name as registered'}})),
    (team_events, 'team_events',
     "Any team's whole season from TBA: every event it attended (official, district "
     'championship and offseason), with qual rank and record, alliance, playoff result and '
     'awards at each. Use for which events/competitions a team went to, how it did elsewhere, '
     'or its season so far. year defaults to this season.',
     _schema({'team': TEAM, 'year': {'type': 'integer'}}, ['team'])),
    (clusters, 'clusters',
     "KMeans groups of the event's teams over the team's default clustering dimensions "
     '(scouted averages and OPR), strongest group first, with what each group stands out on. '
     'Use for "what kinds of robots are here", tiers, or groupings.', _schema()),
    (similar_teams, 'similar_teams',
     "A team's nearest teams in the same clustering space (the same math as Team Details in "
     'the app), its cluster group, and which dimensions set it apart from the average robot. '
     'Use for "who is like X", alternatives to a pick, or what makes a team distinctive.',
     _schema({'team': TEAM, 'count': {'type': 'integer', 'description': 'How many (default 5, max 10)'}},
             ['team'])),
    (calculate, 'calculate',
     'Exact arithmetic. Use it for every calculation you report (robot speeds, gear ratios, '
     'sums, averages, percentages, probabilities) instead of doing math in your head. Python '
     'syntax: + - * / // % **, pi, e, sqrt, sin/cos/tan, log, exp, hypot, comb, round, min, max, '
     'sum, mean, median, stdev (lists like [1,2,3]).',
     _schema({'expressions': {'type': 'array', 'items': {'type': 'string'},
                              'description': 'One or more expressions, e.g. ["6000/6.12*pi*4/720"]'}},
             ['expressions'])),
    (find_event, 'find_event',
     'Look up event keys by name, nickname, place or acronym (e.g. "GVSU", "Ferris State", '
     '"state championship", "Traverse City"). year defaults to this season.',
     _schema({'query': {'type': 'string'}, 'year': {'type': 'integer'}}, ['query'])),
    (scouters, 'scouters', 'Registered scouts for this event.', _schema()),
    (pick_board, 'pick_board',
     "The team's live pick list board: everyone's personal rankings combined spot by spot "
     '(spot #k = the team most people put at #k), each ballot, DNP marks, teams already '
     'taken by other alliances, and notes.', _schema()),
]

# Tools that work on any event: they take an optional event key (default: the
# asker's current event). Schedule, scouts and pick board stay on the current one.
ANY_EVENT = {'event_info', 'list_teams', 'team_info', 'leaderboard', 'scouted_rows', 'pit_data',
             'matches', 'rankings', 'scouting_status', 'clusters', 'similar_teams'}
EVENT_PARAM = {'type': 'string', 'description': "Event key like 2026mibig (from find_event). "
                                                "Leave out for the asker's current event."}
for _fn, _name, _desc, _schema_ in TOOLS:
    if _name in ANY_EVENT:
        _schema_['properties']['event'] = EVENT_PARAM

TOOL_DEFS = [{'name': name, 'description': desc, 'input_schema': schema, 'strict': True}
             for _, name, desc, schema in TOOLS]
_FUNCS = {name: fn for fn, name, _, _ in TOOLS}


def run_tool(session: Session, name: str, args: dict):
    fn = _FUNCS.get(name)
    if not fn:
        return {'error': f'unknown tool {name}'}
    args = dict(args or {})
    event = str(args.pop('event', '') or '').strip().lower()
    if event and name in ANY_EVENT and event != session.event_key:
        if not re.fullmatch(r'\d{4}[a-z0-9]+', event):
            return {'error': f'{event!r} is not an event key; use find_event to get one.'}
        session = replace(session, event_key=event)
    return fn(session, **args)
