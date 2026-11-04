import unittest

import team_events


class SeasonTest(unittest.TestCase):
    def test_shapes_events_statuses_and_awards(self):
        events = [
            {'key': '2026miwmi', 'name': 'West Michigan', 'event_type': 1, 'week': 3,
             'start_date': '2026-03-26', 'end_date': '2026-03-28', 'city': 'Allendale',
             'state_prov': 'MI', 'country': 'USA'},
            {'key': '2026mibig', 'name': 'Big Rapids', 'event_type': 1, 'week': 1,
             'start_date': '2026-03-12', 'end_date': '2026-03-14'},
        ]
        statuses = {
            '2026miwmi': {
                'qual': {'num_teams': 40, 'ranking': {'rank': 3, 'record': {'wins': 9, 'losses': 3, 'ties': 0}}},
                'alliance': {'number': 2, 'pick': 0},
                'alliance_status_str': '<b>Captain</b> of <b>Alliance 2</b>',
                'playoff': {'status': 'eliminated', 'level': 'sf', 'double_elim_round': 'Round 3',
                            'record': {'wins': 4, 'losses': 2, 'ties': 0}},
                'overall_status_str': 'Team 1918 was <b>Rank 3/40</b>.',
            },
            '2026mibig': None,  # TBA has no status yet
        }
        awards = [{'name': 'District Event Winner', 'event_key': '2026mibig'}]
        out = team_events.season(1918, events, statuses, awards)
        self.assertEqual([e['event_key'] for e in out['events']], ['2026mibig', '2026miwmi'])
        big, wmi = out['events']
        self.assertEqual(big['awards'], ['District Event Winner'])
        self.assertIsNone(big['qual_rank'])
        self.assertEqual(big['week'], 2)
        self.assertEqual(wmi['type'], 'District')
        self.assertEqual(wmi['qual_record'], '9-3-0')
        self.assertEqual(wmi['alliance'], 'Captain of Alliance 2')
        self.assertEqual(wmi['playoff'], {'status': 'eliminated', 'level': 'sf',
                                          'bracket_round': 'Round 3', 'record': '4-2-0'})
        self.assertEqual(wmi['summary'], 'Team 1918 was Rank 3/40.')


if __name__ == '__main__':
    unittest.main()
