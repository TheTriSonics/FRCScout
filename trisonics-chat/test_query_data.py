"""Offline checks for query_data on fake in-memory rows: python test_query_data.py"""
import query_data as qd
from tools import Session

SCOUTED = [
    dict(match_number=m, team_number=t, scouter_name=s, teleop_fuel_accuracy=a, hopper_size=h)
    for m, t, s, a, h in [(1, 10, 'ann', 80, 20), (2, 10, 'bob', 60, 20), (1, 20, 'ann', 50, 30),
                          (2, 20, 'bob', 30, 30), (3, 30, 'ann', 90, 40), (3, 40, 'bob', 20, 10)]]
TEAM_MATCHES = [
    dict(comp_level='qm', team_number=t, won=w, margin=mg, alliance_hub_fuel=f)
    for t, w, mg, f in [(10, 1, 20, 60), (20, 1, 20, 60), (30, 0, -20, 40), (40, 0, -20, 40),
                        (10, 1, 5, 50), (30, 0, -5, 45)]
] + [dict(comp_level='sf', team_number=10, won=1, margin=40, alliance_hub_fuel=70)]
OPR = [dict(team_number=t, totalPoints=p) for t, p in [(10, 100.0), (20, 60.0), (30, 120.0), (40, 10.0)]]

TABLES = {'scouted': SCOUTED, 'team_matches': TEAM_MATCHES, 'opr': OPR, 'pit': [], 'rankings': []}
qd._BUILDERS.update({k: (lambda ev, k=k: [dict(r) for r in TABLES[k]]) for k in TABLES})


class FakeSession(Session):
    @property
    def event(self):
        return None


S = FakeSession('k', '2026test')


def q(**spec):
    return qd.query_data(S, **spec)


def test_filter_group_aggregate_sort():
    r = q(table='team_matches', filters=[{'column': 'won', 'op': '=', 'value': 1}],
          group_by=['comp_level'], aggregates=[{'fn': 'mean', 'column': 'margin', 'as': 'm'}, {'fn': 'count_rows'}],
          sort=[{'column': 'm', 'desc': True}])
    assert r['columns'] == ['comp_level', 'm', 'count_rows'], r
    assert r['rows'] == [['sf', 40.0, 1], ['qm', 15.0, 3]], r
    r = q(table='scouted', filters=[{'column': 'team_number', 'op': 'in', 'value': [10, 20]},
                                    {'column': 'match_number', 'op': '>=', 'value': 2}],
          columns=['team_number', 'teleop_fuel_accuracy'], sort=[{'column': 'teleop_fuel_accuracy'}], limit=1)
    assert r['rows'] == [[20, 30]] and r['rows_before_limit'] == 2, r


def test_join_and_correlation_per_team():
    r = q(table='scouted', join=['opr'], correlate={'x': 'teleop_fuel_accuracy', 'y': 'opr_totalPoints', 'per': 'team_number'})
    c = r['correlation']
    # per-team mean accuracy: 70, 40, 90, 20 vs OPR 100, 60, 120, 10 (perfectly linear? no, check against stdlib)
    import statistics
    assert c['n'] == 4
    assert abs(c['pearson_r'] - round(statistics.correlation([70, 40, 90, 20], [100, 60, 120, 10]), 3)) < 1e-9, c
    assert 'reading' in c and c['y_most_above_line'], c


def test_errors_never_raise():
    assert 'Valid tables' in q(table='nope')['error']
    e = q(table='scouted', filters=[{'column': 'nope', 'op': '=', 'value': 1}])['error']
    assert 'teleop_fuel_accuracy' in e, e
    assert 'text' in q(table='scouted', group_by=['team_number'], aggregates=[{'fn': 'mean', 'column': 'scouter_name'}])['error']
    assert 'error' in q(table='scouted', filters=[{'column': 'team_number', 'op': '=', 'value': 10}],
                        correlate={'x': 'hopper_size', 'y': 'match_number'})['correlation']  # only 2 points
    assert q(table='scouted', limit=5000, columns=['match_number'])['rows']  # limit clamps, no crash


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
