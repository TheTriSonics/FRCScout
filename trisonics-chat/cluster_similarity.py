"""Nearest teams in clustering space: a port of RebuiltScouting
lib/analytics/cluster_similarity.dart (ClusterSpace), so the bot's
"similar teams" match Team Details in the app.

Rebuilds the space the API clustered in from a GetClusters result: each
dimension z-scored over the clustered teams (population std, missing values
count as the event average) and multiplied by sqrt(weight).
"""
import bisect
import math


class ClusterSpace:
    def __init__(self, result):
        self.result = result
        self.features = list(result.get('features') or [])
        weights = result.get('weights') or {}
        teams = result.get('teams') or []
        self.group = {t['team_number']: t.get('group') for t in teams}
        self.values = {t['team_number']: t.get('values') or {} for t in teams}
        self.mean, self.std = [], []
        for f in self.features:
            vs = [v[f] for v in self.values.values() if v.get(f) is not None]
            m = sum(vs) / len(vs) if vs else 0.0
            var = sum((x - m) ** 2 for x in vs) / len(vs) if vs else 0.0
            self.mean.append(m)
            self.std.append(math.sqrt(var))
        self.raw, self.coords = {}, {}
        for tn, vals in self.values.items():
            row = [vals.get(f) if vals.get(f) is not None else self.mean[j]
                   for j, f in enumerate(self.features)]
            self.raw[tn] = row
            self.coords[tn] = [
                (row[j] - self.mean[j]) / (self.std[j] or 1) * math.sqrt(float(weights.get(f, 1.0)))
                for j, f in enumerate(self.features)]
        cs = list(self.coords.values())
        self._pairs = sorted(_dist(cs[i], cs[j]) for i in range(len(cs)) for j in range(i + 1, len(cs)))

    def similarity(self, d):
        """Share (0-100) of all team pairs at the event farther apart than d."""
        if not self._pairs:
            return 100.0
        return 100.0 * (len(self._pairs) - bisect.bisect_right(self._pairs, d)) / len(self._pairs)

    def neighbors(self, team, count=5):
        me = self.coords.get(team)
        if me is None:
            return []
        near = sorted(((tn, _dist(me, c)) for tn, c in self.coords.items() if tn != team),
                      key=lambda x: x[1])
        return [{'team': tn, 'group': self.group.get(tn), 'distance': round(d, 3),
                 'closer_than_pct_of_pairs': round(self.similarity(d))}
                for tn, d in near[:count]]

    def distinctions(self, team, neighbor_teams):
        """Each dimension's share of what sets [team] apart from the average
        robot (its share of squared distance from the event mean), biggest first."""
        me, raw = self.coords.get(team), self.raw.get(team)
        if me is None:
            return []
        total = sum(c * c for c in me)
        mates = [self.raw[t] for t, g in self.group.items() if g == self.group.get(team)]
        out = []
        for j, f in enumerate(self.features):
            out.append({
                'feature': f,
                'value': self.values[team].get(f),
                'event_mean': round(self.mean[j], 3),
                'z': round((raw[j] - self.mean[j]) / self.std[j], 2) if self.std[j] else 0.0,
                'share_pct': round(100 * me[j] * me[j] / total, 1) if total else 0.0,
                'group_mean': round(sum(m[j] for m in mates) / len(mates), 3) if mates else None,
                'neighbor_values': {n: self.values.get(n, {}).get(f) for n in neighbor_teams},
            })
        out.sort(key=lambda d: -d['share_pct'])
        return out


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
