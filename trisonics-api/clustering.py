"""KMeans clustering of teams on scouted averages and OPR components.

Ported from data-streamlit/views/clusters.py (minus PCA) so the Flutter
scouting app can render clusters without doing the math client-side.
"""

import math

import numpy as np
import pandas as pd

SKIP_COLS = {'team_number', 'match_number', 'robot_no_show'}

# Detail columns are available but off by default -- fuel_made columns are
# the key metrics.
DETAIL_SUFFIXES = ('_missed', '_accuracy', '_scored', '_shot')
DETAIL_PREFIXES = ('total_',)
DETAIL_EXACT = {'win_auto'}


def _is_detail(name):
    return (name.endswith(DETAIL_SUFFIXES) or name.startswith(DETAIL_PREFIXES)
            or name in DETAIL_EXACT)


def _num(v, digits=3):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, digits)


def prepare_scouted(df, event_key):
    """Normalise raw MatchResults rows into numeric per-match records."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={'scouting_team': 'team_number',
                            'match_key': 'match_number'})
    for c in df.columns:
        s = df[c]
        if s.dtype == bool:
            df[c] = s.astype(int)
        elif s.dtype == object and s.map(
                lambda v: isinstance(v, (bool, int, float, np.number))).all():
            # Fields added mid-season show up as a mix of bools and the
            # 0 that get_scouting_data fills in for older records.
            df[c] = s.astype(float)
    if event_key.startswith('2026'):
        for phase in ('auto', 'teleop', 'endgame'):
            shot, acc = f'{phase}_fuel_scored', f'{phase}_fuel_accuracy'
            if shot in df.columns and acc in df.columns:
                made = (df[shot] * df[acc] / 100).round()
                df[f'{phase}_fuel_made'] = made
                df[f'{phase}_fuel_missed'] = df[shot] - made
        made_cols = [c for c in df.columns if c.endswith('_fuel_made')]
        shot_cols = [c for c in ('auto_fuel_scored', 'teleop_fuel_scored',
                                 'endgame_fuel_scored') if c in df.columns]
        df['total_fuel_made'] = df[made_cols].sum(axis=1)
        df['total_fuel_shot'] = df[shot_cols].sum(axis=1)
        df['total_fuel_missed'] = df['total_fuel_shot'] - df['total_fuel_made']
    # A no-show says nothing about what the robot can do.
    if 'robot_no_show' in df.columns:
        df = df[df['robot_no_show'] == 0]
    return df


def team_averages(df):
    if df.empty:
        return pd.DataFrame()
    cols = [c for c in df.select_dtypes(include='number').columns
            if c not in SKIP_COLS]
    avgs = df.groupby('team_number')[cols].mean()
    avgs.index = avgs.index.astype(int)
    return avgs


def opr_averages(opr, scouted_cols=()):
    """Per-team OPR components, renamed if they collide with scouted names."""
    if opr is None or opr.empty or 'teamNumber' not in opr.columns:
        return pd.DataFrame()
    opr = opr.copy()
    opr['teamNumber'] = opr['teamNumber'].astype(int)
    out = opr.groupby('teamNumber').mean(numeric_only=True)
    return out.rename(columns={c: f'opr_{c}' for c in out.columns
                               if c in scouted_cols})


def available_features(scouted, opr):
    feats = []
    for source, frame in (('scouted', scouted), ('opr', opr)):
        rows = []
        for name in frame.columns:
            var = float(np.var(frame[name].to_numpy(dtype=float)))
            if source == 'scouted':
                default = not _is_detail(name)
            else:
                # Justin's preference: skip point-level cOPR columns.
                default = not name.endswith('Points')
            rows.append({'name': name, 'source': source,
                         'variance': _num(var), 'default': default and var > 0})
        rows.sort(key=lambda r: r['variance'] or 0, reverse=True)
        feats += rows
    return feats


def _kmeanspp_init(data, k, rng):
    centers = [data[rng.integers(len(data))]]
    for _ in range(1, k):
        d2 = ((data[:, None] - np.array(centers)[None]) ** 2).sum(axis=2)
        d2 = d2.min(axis=1)
        total = d2.sum()
        idx = (rng.integers(len(data)) if total == 0
               else rng.choice(len(data), p=d2 / total))
        centers.append(data[idx])
    return np.array(centers, dtype=float)


def kmeans(data, k, n_init=10, max_iter=100, seed=1):
    """Pure numpy KMeans with k-means++ seeding. Returns (labels, centers)."""
    rng = np.random.default_rng(seed)
    best_labels, best_centers, best_inertia = None, None, np.inf
    for _ in range(n_init):
        centers = _kmeanspp_init(data, k, rng)
        for _ in range(max_iter):
            dists = ((data[:, None] - centers[None]) ** 2).sum(axis=2)
            labels = dists.argmin(axis=1)
            new_centers = np.array([
                data[labels == i].mean(axis=0) if np.any(labels == i)
                else centers[i]
                for i in range(k)
            ])
            converged = np.allclose(centers, new_centers)
            centers = new_centers
            if converged:
                break
        labels = ((data[:, None] - centers[None]) ** 2).sum(axis=2).argmin(axis=1)
        inertia = ((data - centers[labels]) ** 2).sum()
        if inertia < best_inertia:
            best_labels, best_centers, best_inertia = labels, centers, inertia
    return best_labels, best_centers


def cluster_teams(scouted, opr, features=None, k=4, scale=True, exclude=()):
    """Cluster teams and describe each group.

    scouted/opr are per-team frames from team_averages/opr_averages.
    features defaults to the 'default' set from available_features.
    """
    available = available_features(scouted, opr)
    if not features:
        features = [f['name'] for f in available if f['default']]
    sc_feats = [f for f in features if f in scouted.columns]
    opr_feats = [f for f in features if f in opr.columns]
    used = sc_feats + opr_feats

    excluded = sorted(int(t) for t in exclude if int(t) in scouted.index)
    table = scouted.drop(index=excluded)
    dropped = []
    if not opr.empty:
        if opr_feats:
            # Teams without OPR yet (no quals played) can't be placed.
            dropped = sorted(int(t) for t in table.index
                             if t not in opr.index)
            table = table.join(opr, how='inner')
        else:
            table = table.join(opr, how='left')

    result = {
        'k': 0, 'scaled': bool(scale), 'has_opr': not opr.empty,
        'features': used, 'available_features': available,
        'strength_metric': None, 'groups': [], 'teams': [],
        'excluded': excluded, 'dropped': dropped,
    }
    if not used or table.empty:
        return result

    X = table[used].to_numpy(dtype=float)
    X = np.nan_to_num(X)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    safe_std = np.where(std > 0, std, 1.0)
    data = (X - mean) / safe_std if scale else X

    k = max(1, min(int(k), len(table)))
    labels, _ = kmeans(data, k)

    if 'totalPoints' in table.columns and table['totalPoints'].notna().any():
        metric = 'totalPoints'
    elif 'total_fuel_made' in table.columns:
        metric = 'total_fuel_made'
    else:
        metric = None

    raw_groups = []
    for label in sorted(set(labels.tolist())):
        members = np.where(labels == label)[0]
        strength = (float(table[metric].iloc[members].mean())
                    if metric else float(np.linalg.norm(X[members].mean(axis=0))))
        profile = []
        for j, name in enumerate(used):
            cmean = X[members, j].mean()
            z = (cmean - mean[j]) / std[j] if std[j] > 0 else 0.0
            profile.append({'feature': name, 'mean': _num(cmean),
                            'event_mean': _num(mean[j]), 'z': _num(z)})
        profile.sort(key=lambda p: abs(p['z'] or 0), reverse=True)
        raw_groups.append((strength, label, members, profile))

    raw_groups.sort(key=lambda g: -g[0] if not math.isnan(g[0]) else math.inf)
    group_of = {}
    for group_num, (strength, label, members, profile) in enumerate(
            raw_groups, start=1):
        teams = sorted(int(table.index[i]) for i in members)
        for t in teams:
            group_of[t] = group_num
        result['groups'].append({
            'group': group_num, 'teams': teams, 'strength': _num(strength),
            'profile': profile,
        })

    value_cols = [f['name'] for f in available if f['name'] in table.columns]
    for team in table.index:
        row = table.loc[team]
        result['teams'].append({
            'team_number': int(team), 'group': group_of[int(team)],
            'values': {c: _num(row[c]) for c in value_cols},
        })
    result['k'] = len(result['groups'])
    result['strength_metric'] = metric
    return result
