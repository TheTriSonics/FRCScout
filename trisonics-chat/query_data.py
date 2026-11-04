"""query_data: ad-hoc filters, group-bys, aggregates and correlations.

The model sends a structured spec (never code). Tables are built from the same
loaders as the other tools; everything is plain Python, no pandas. Errors come
back as {'error': ...} with the valid names, never as exceptions.
"""
import json
import logging
import math
import re
import statistics

import season_2026 as season
from scout_data import team_num

TABLES = ['scouted', 'team_matches', 'opr', 'pit', 'rankings']
JOINS = {'opr': 'opr_', 'rankings': 'rank_', 'pit': 'pit_'}
MAX_LIMIT = 100
OPS = ['=', '!=', '<', '<=', '>', '>=', 'in', 'not_in', 'contains']
FNS = ['mean', 'median', 'sum', 'count', 'min', 'max', 'stdev', 'count_rows']

# Ratings where "vs other scouts" (this record minus the mean of the other
# scouts' records of the same team) is added, for calibrating scouts.
CALIBRATED = ['auto_fuel_accuracy', 'teleop_fuel_accuracy', 'teleop_volley_accuracy',
              'endgame_fuel_accuracy', 'teleop_volleys', 'hopper_size']

# Pit answers that are free text; left out of the pit table.
PIT_TEXT = {'drive_train_other', 'auto_notes', 'hanging_how', 'hanging_time', 'teleop_active_plan',
            'teleop_inactive_plan', 'fun_question', 'notes', 'scouter_name'}


def _num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    return float(v) if isinstance(v, (int, float)) else None


def _clean(v):
    """Bools -> 0/1, long text truncated; everything else as-is."""
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, str):
        v = v.strip()
        return v[:60] if v else None
    if isinstance(v, (int, float)) or v is None:
        return v
    return None  # lists, dicts


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')


def _played(m):
    score = m['alliances']['red'].get('score')
    return score is not None and score >= 0 and bool(m.get('actual_time') or m.get('post_result_time'))


# --- tables: each returns a list of dicts ---

def _scouted(ev):
    rows = []
    for r in ev.scouted():
        d = {'match_number': r.get('match_number'), 'team_number': int(r['team_number']),
             'scouter_name': r.get('scouter_name')}
        d.update(season.row_stats(r))
        for f in ('teleop_active_defense_quality', 'teleop_inactive_defense_quality'):
            d[f] = _clean(r.get(f))
        rows.append(d)
    by_team = {}
    for d in rows:
        by_team.setdefault(d['team_number'], []).append(d)
    for team_rows in by_team.values():
        for d in team_rows:
            others = [o for o in team_rows if o['scouter_name'] != d['scouter_name']]
            for k in CALIBRATED:
                vals = [o[k] for o in others if o.get(k) is not None]
                d[k + '_vs_other_scouts'] = d[k] - statistics.fmean(vals) if d.get(k) is not None and vals else None
    return rows


def _team_matches(ev):
    rows = []
    for m in ev.matches():
        if not _played(m):
            continue
        bd = m.get('score_breakdown') or {}
        win = m.get('winning_alliance') or ''
        for side, opp in (('red', 'blue'), ('blue', 'red')):
            a, o = m['alliances'][side], m['alliances'][opp]
            b, ob = bd.get(side) or {}, bd.get(opp) or {}
            teams = [team_num(t) for t in a['team_keys']]
            hub = (b.get('hubScore') or {}).get('totalCount')
            ohub = (ob.get('hubScore') or {}).get('totalCount')
            for tn in teams:
                rows.append({
                    'event_key': m['event_key'], 'match_key': m['key'], 'comp_level': m['comp_level'],
                    'set_number': m.get('set_number'), 'match_number': m.get('match_number'),
                    'team_number': tn, 'alliance': side,
                    'partners': ','.join(str(t) for t in teams if t != tn),
                    'alliance_score': a.get('score'), 'opponent_score': o.get('score'),
                    'won': 0.5 if not win else (1 if win == side else 0),
                    'margin': (a.get('score') or 0) - (o.get('score') or 0),
                    'rp': b.get('rp') if m['comp_level'] == 'qm' else None,
                    'alliance_hub_fuel': hub, 'opponent_hub_fuel': ohub,
                    'hub_fuel_margin': hub - ohub if hub is not None and ohub is not None else None,
                    'alliance_auto_tower_points': b.get('autoTowerPoints'),
                    'alliance_endgame_tower_points': b.get('endGameTowerPoints'),
                    'alliance_tower_points': b.get('totalTowerPoints'),
                    'alliance_foul_points': b.get('foulPoints'),
                })
    return rows


def _opr(ev):
    rows = []
    for tn, r in sorted(ev.opr().items()):
        d = {'team_number': tn}
        d.update({k: v for k, v in r.items() if k != 'teamNumber' and isinstance(v, (int, float))})
        d['teamNumber'] = tn
        rows.append(d)
    return rows


def _pit(ev):
    rows = []
    for p in sorted(ev.pit(), key=lambda p: (p.get('team_number', 0), p.get('timestamp') or '')):
        d = {'team_number': int(p['team_number'])}
        for k, v in p.items():
            if k in season.PIT_SKIP or k in PIT_TEXT or k == 'team_number' or k.startswith('auto_notes'):
                continue
            v = _clean(v)
            if v is not None:
                d[k] = v
        rows.append(d)
    return rows


def _rankings(ev):
    data = ev.rankings()
    names = [_slug(s['name']) for s in data.get('sort_order_info') or []]
    rows = []
    for r in data.get('rankings') or []:
        rec = r.get('record') or {}
        d = {'team_number': team_num(r['team_key']), 'rank': r.get('rank'),
             'wins': rec.get('wins'), 'losses': rec.get('losses'), 'ties': rec.get('ties'),
             'matches_played': r.get('matches_played'), 'dq': r.get('dq')}
        for n, v in zip(names, r.get('sort_orders') or []):
            if n:
                d[n] = v
        rows.append(d)
    return rows


_BUILDERS = {'scouted': _scouted, 'team_matches': _team_matches, 'opr': _opr, 'pit': _pit,
             'rankings': _rankings}


def _columns(rows):
    cols = {}
    for r in rows:
        for k in r:
            cols.setdefault(k, None)
    return list(cols)


def _with_joins(ev, table, rows, joins):
    for j in joins:
        if j == table:
            raise ValueError(f'cannot join {j} onto itself')
        other = {}
        for r in _BUILDERS[j](ev):  # later rows win (newest pit record)
            other[r['team_number']] = r
        pre = JOINS[j]
        for r in rows:
            o = other.get(r.get('team_number')) or {}
            for k, v in o.items():
                if k != 'team_number':
                    r[pre + k] = v
    return rows


# --- evaluation ---

class SpecError(Exception):
    pass


def _check_col(col, valid, what='column'):
    if col not in valid:
        raise SpecError(f'unknown {what} {col!r}. Valid columns: {", ".join(valid)}')


def _match(cell, op, val):
    if cell is None:
        return False
    if isinstance(cell, str):
        cell = cell.lower()
    def norm(v):
        if isinstance(v, bool):
            return 1 if v else 0
        return v.lower() if isinstance(v, str) else v
    if op in ('in', 'not_in'):
        if not isinstance(val, list):
            raise SpecError(f'{op} needs a list value')
        hit = cell in [norm(v) for v in val]
        return hit if op == 'in' else not hit
    val = norm(val)
    if isinstance(cell, (int, float)) and isinstance(val, str):
        try:
            val = float(val)
        except ValueError:
            raise SpecError(f'column is numeric but value {val!r} is not')
    if op == 'contains':
        return str(val) in str(cell)
    try:
        return {'=': cell == val, '!=': cell != val, '<': cell < val, '<=': cell <= val,
                '>': cell > val, '>=': cell >= val}[op]
    except TypeError:
        raise SpecError(f'cannot compare {cell!r} with {val!r}')
    except KeyError:
        raise SpecError(f'unknown op {op!r}. Valid: {", ".join(OPS)}')


def _agg(fn, vals, col):
    if fn == 'count':
        return sum(1 for v in vals if v is not None)
    vals = [v for v in vals if v is not None]
    if fn in ('min', 'max'):
        try:
            return (min if fn == 'min' else max)(vals) if vals else None
        except TypeError:
            raise SpecError(f'cannot take {fn} of mixed values in {col}')
    nums = [v for v in vals if isinstance(v, (int, float))]
    if vals and not nums:
        raise SpecError(f'column {col} is text; {fn} needs a numeric column (use count, min or max)')
    if not nums:
        return None
    if fn == 'mean':
        return statistics.fmean(nums)
    if fn == 'median':
        return statistics.median(nums)
    if fn == 'sum':
        return sum(nums)
    if fn == 'stdev':
        return statistics.stdev(nums) if len(nums) > 1 else None
    raise SpecError(f'unknown fn {fn!r}. Valid: {", ".join(FNS)}')


def _round(v):
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 3)
    return v


def _sort_rows(rows, cols, sort):
    for s in reversed(sort):
        col = s.get('column')
        _check_col(col, cols, 'sort column')
        i = cols.index(col)
        have = [r for r in rows if r[i] is not None]
        none = [r for r in rows if r[i] is None]
        try:
            have.sort(key=lambda r: r[i], reverse=bool(s.get('desc')))
        except TypeError:
            raise SpecError(f'cannot sort {col}: mixed values')
        rows = have + none
    return rows


def _reading(r, n, slope):
    a = abs(r)
    strength = ('no real' if a < 0.1 else 'very weak' if a < 0.2 else 'weak' if a < 0.4
                else 'moderate' if a < 0.6 else 'strong' if a < 0.8 else 'very strong')
    direction = 'positive' if r > 0 else 'negative'
    text = (f'{strength.capitalize()} relationship' if strength == 'no real'
            else f'{strength.capitalize()} {direction} relationship')
    text += f' (r={r:.2f}, r²={r * r:.2f}, n={n}): '
    text += ('x explains about {:.0f}% of the variation in y. '.format(r * r * 100))
    if n > 2 and abs(r) < 1:
        t = r * math.sqrt((n - 2) / (1 - r * r))
        if abs(t) < 2:
            text += 'at this sample size that could easily be chance. '
    if n < 10:
        text += 'Very few points, treat as shaky. '
    text += 'Correlation is not causation.'
    return text


def _correlate(rows, valid, spec):
    x, y, per = spec.get('x'), spec.get('y'), spec.get('per')
    _check_col(x, valid, 'x column')
    _check_col(y, valid, 'y column')
    if per:
        _check_col(per, valid, 'per column')
    pairs = []
    for r in rows:
        a, b = _num(r.get(x)), _num(r.get(y))
        if a is not None and b is not None:
            pairs.append((r.get(per) if per else None, a, b))
    out = {'x': x, 'y': y}
    if per:
        groups = {}
        for k, a, b in pairs:
            groups.setdefault(k, []).append((a, b))
        pts = [(k, statistics.fmean(p[0] for p in v), statistics.fmean(p[1] for p in v))
               for k, v in groups.items() if k is not None]
        out['per'] = per
        out['rows_used'] = len(pairs)
    else:
        pts = [(None, a, b) for _, a, b in pairs]
    n = len(pts)
    out['n'] = n
    if n < 3:
        out['error'] = f'only {n} usable points (need at least 3 with both {x} and {y})'
        return out
    xs, ys = [p[1] for p in pts], [p[2] for p in pts]
    try:
        r = statistics.correlation(xs, ys)
        rho = statistics.correlation(xs, ys, method='ranked')
        slope, icpt = statistics.linear_regression(xs, ys)
    except statistics.StatisticsError:
        out['error'] = f'{x} or {y} is constant in these rows, so no correlation exists'
        return out
    out.update(pearson_r=r, spearman_r=rho, slope=slope, intercept=icpt, r_squared=r * r,
               reading=_reading(r, n, slope))
    if per:
        res = sorted(((y_ - (slope * x_ + icpt), k, x_, y_) for k, x_, y_ in pts), key=lambda t: t[0])
        def item(t):
            return {per: t[1], 'x': t[2], 'y': t[3], 'expected_y': t[3] - t[0], 'residual': t[0]}
        out['y_most_below_line'] = [item(t) for t in res[:5]]
        out['y_most_above_line'] = [item(t) for t in reversed(res[-5:])]
    return out


def _run(s, spec):
    table = spec.get('table')
    if table not in TABLES:
        raise SpecError(f'unknown table {table!r}. Valid tables: {", ".join(TABLES)}')
    joins = list(spec.get('join') or [])
    for j in joins:
        if j not in JOINS:
            raise SpecError(f'unknown join {j!r}. Valid joins: {", ".join(JOINS)}')
    ev = s.event
    rows = _with_joins(ev, table, _BUILDERS[table](ev), joins)
    valid = _columns(rows)
    if not rows:
        return {'table': table, 'rows_in_table': 0, 'columns': [], 'rows': [],
                'note': 'The table is empty for this event (no data yet).'}

    for f in spec.get('filters') or []:
        _check_col(f.get('column'), valid, 'filter column')
        if f.get('op') not in OPS:
            raise SpecError(f'unknown op {f.get("op")!r}. Valid: {", ".join(OPS)}')
    for f in spec.get('filters') or []:
        rows = [r for r in rows if _match(r.get(f['column']), f['op'], f.get('value'))]
    after_filters = len(rows)

    if spec.get('correlate'):
        out = {'table': table, 'rows_after_filters': after_filters,
               'correlation': _correlate(rows, valid, spec['correlate'])}
        if spec.get('group_by') or spec.get('aggregates'):
            out['note'] = 'group_by/aggregates ignored: correlate works on filtered rows (use correlate.per to average by group first).'
        return out

    group_by, aggs = list(spec.get('group_by') or []), list(spec.get('aggregates') or [])
    for c in group_by:
        _check_col(c, valid, 'group_by column')
    for a in aggs:
        if a.get('fn') not in FNS:
            raise SpecError(f'unknown fn {a.get("fn")!r}. Valid: {", ".join(FNS)}')
        if a['fn'] != 'count_rows':
            _check_col(a.get('column'), valid, 'aggregate column')
    if group_by or aggs:
        if not aggs:
            aggs = [{'fn': 'count_rows', 'as': 'rows'}]
        names = [a.get('as') or (a['fn'] if a['fn'] == 'count_rows' else f'{a["fn"]}_{a["column"]}') for a in aggs]
        groups = {}
        for r in rows:
            groups.setdefault(tuple(r.get(c) for c in group_by), []).append(r)
        if not group_by and not groups:
            groups[()] = []
        cols = group_by + names
        out_rows = []
        for key, grp in groups.items():
            out_rows.append(list(key) + [
                len(grp) if a['fn'] == 'count_rows' else _agg(a['fn'], [r.get(a['column']) for r in grp], a['column'])
                for a in aggs])
    else:
        cols = list(spec.get('columns') or valid)
        for c in cols:
            _check_col(c, valid)
        out_rows = [[r.get(c) for c in cols] for r in rows]

    out_rows = _sort_rows(out_rows, cols, spec.get('sort') or [])
    try:
        limit = int(spec.get('limit') or 25)
    except (TypeError, ValueError):
        limit = 25
    limit = max(1, min(limit, MAX_LIMIT))
    return {'table': table, 'rows_after_filters': after_filters, 'rows_before_limit': len(out_rows),
            'columns': cols, 'rows': [[_round(v) for v in r] for r in out_rows[:limit]],
            **({'truncated_to': limit} if len(out_rows) > limit else {})}


def _rounded(x):
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_rounded(v) for v in x]
    return _round(x)


def query_data(s, table=None, filters=None, group_by=None, aggregates=None, columns=None,
               sort=None, limit=25, correlate=None, join=None, **extra):
    spec = {k: v for k, v in dict(table=table, filters=filters, group_by=group_by, aggregates=aggregates,
                                  columns=columns, sort=sort, limit=limit, correlate=correlate,
                                  join=join, **extra).items() if v not in (None, [], {})}
    logging.info('query_data %s', json.dumps({**spec, 'event': s.event_key}, default=str))
    try:
        return _rounded(_run(s, spec))
    except SpecError as e:
        return {'error': str(e)}
    except Exception as e:  # never raise to the model
        logging.exception('query_data failed')
        return {'error': f'query failed: {type(e).__name__}: {e}'}
