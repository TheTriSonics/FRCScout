"""Offline checks for the sql tool on fake live rows: python test_live_sql.py

Uses the local history database if there is one (history/data/history.duckdb).
"""
import live_sql
from tools import Session

FAKE = {
    'k1': {'scouted': [{'match_number': 1, 'team_number': 4003, 'scouter_name': 'a', 'teleop_volleys': 2.0},
                       {'match_number': 2, 'team_number': 4003, 'scouter_name': 'b', 'teleop_volleys': 4.0},
                       {'match_number': 1, 'team_number': 254, 'scouter_name': 'a', 'teleop_volleys': None}],
           'pit': [{'team_number': 4003, 'drive_train': 'Tank'}, {'team_number': 4003, 'drive_train': 'Swerve'}]},
    'k2': {'scouted': [{'match_number': 9, 'team_number': 1, 'scouter_name': 'z', 'teleop_volleys': 9.0}]},
}


class FakeSession(Session):
    @property
    def event(self):
        return self.secret_key


live_sql.LOADERS = {name: (lambda key, name=name: [dict(r) for r in FAKE[key].get(name, [])])
                    for name in ('scouted', 'team_results', 'opr', 'pit', 'rankings', 'event_teams')}

s1, s2 = FakeSession('k1', '2026test'), FakeSession('k2', '2026test')


def q(s, sql):
    return live_sql.run(s, sql)


r = q(s1, 'select team_number, avg(teleop_volleys) v from live.scouted group by 1 order by 1')
assert r['rows'] == [[254, None], [4003, 3.0]], r
assert q(s1, 'select drive_train from live.pit_latest')['rows'] == [['Swerve']]
assert q(s1, 'select count(*) from live.pit')['rows'] == [[2]]
# Another secret key never sees k1's rows.
assert q(s2, 'select team_number from live.scouted')['rows'] == [[1]]
assert q(s1, 'select count(*) from live.rankings')['empty_live_tables'] == ['rankings']
for bad in ['delete from live.scouted', 'select 1; select 2', "attach 'x.db' as x",
            "select * from read_csv('/etc/passwd')", "copy live.scouted to '/tmp/x.csv'",
            'set enable_external_access = true', 'create table live.x (a int)']:
    assert 'error' in q(s1, bad), bad
assert 'error' in q(s1, 'select nope from live.scouted')
if live_sql._connection(s1)['history']:
    r = q(s1, 'select s.team_number, count(*) from live.scouted s join teams t using (team_number) '
              'group by 1 order by 1')
    assert r['rows'] == [[254, 1], [4003, 2]], r
print('ok')
