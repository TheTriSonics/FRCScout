import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import shift_reminders as sr  # noqa: E402

NOW = 1_800_000_000
TIMES = {1: NOW + 10 * 60, 2: NOW + 18 * 60, 3: NOW + 26 * 60,
         4: NOW + 34 * 60}


def shift(name, station, a, b):
    return {'scouter_name': name, 'station': station,
            'first_match': a, 'last_match': b}


SCHED = {'shifts': [shift('Ann', 'red1', 1, 2), shift('Ben', 'blue3', 1, 2),
                    shift('Cy', 'red1', 3, 4), shift('No Slack', 'red2', 1, 4)]}
USERS = {'ann': 'UANN', 'ben': 'UBEN', 'cy': 'UCY'}


def due(sched=SCHED, sent=(), now=NOW, times=TIMES, users=USERS):
    return sr.due_reminders(secret_key='k', event_key='e', schedule=sched,
                            times=times, slack_users=users, sent=set(sent),
                            now=now)


class ShiftReminderTests(unittest.TestCase):
    def test_window_and_linked_only(self):
        got = due()
        # Ann and Ben start in 10 min; Cy's Q3 is 26 min out; No Slack isn't
        # linked.
        self.assertEqual([r['user'] for r in got], ['UANN', 'UBEN'])
        self.assertIn('in about 10 min', got[0]['text'])
        self.assertIn('*Red 1*, Q1–Q2', got[0]['text'])
        self.assertIn('With: Ben, No Slack.', got[0]['text'])
        self.assertNotIn('Practice', got[0]['text'])
        # 12 minutes later Cy is due, and Ann/Ben are still in grace.
        later = due(now=NOW + 12 * 60)
        self.assertIn('UCY', [r['user'] for r in later])
        # Well after the start: nothing for Ann.
        self.assertNotIn('UANN', [r['user'] for r in due(now=NOW + 20 * 60)])

    def test_sent_once(self):
        first = due()
        again = due(sent=[r['key'] for r in first])
        self.assertEqual(again, [])
        # A changed shift is a new reminder.
        moved = {'shifts': [shift('Ann', 'red2', 1, 2)] + SCHED['shifts'][1:]}
        self.assertEqual([r['user'] for r in due(moved, sent=[r['key'] for r in first])],
                         ['UANN'])

    def test_practice_offset(self):
        old = {m: t - 200 * 86400 for m, t in TIMES.items()}
        self.assertEqual(due(times=old), [])
        practice = {**SCHED, 'time_offset': 200 * 86400}
        got = due(practice, times=old)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0]['text'].startswith('Practice run: '))
        # A different offset is a different run, so it reminds again.
        self.assertNotEqual(got[0]['key'], due(times=TIMES)[0]['key'])

    def test_clean_offset(self):
        self.assertEqual(sr.clean_offset('3600'), 3600)
        self.assertEqual(sr.clean_offset(None), 0)
        self.assertEqual(sr.clean_offset('x'), 0)
        self.assertEqual(sr.clean_offset(10 ** 12), 0)

    def test_newest_by_event(self):
        docs = [{'event_key': 'a', 'published_at': '2026-01-01T00:00:00Z', 'n': 1},
                {'event_key': 'a', 'published_at': '2026-02-01T00:00:00Z', 'n': 2},
                {'event_key': 'b', 'published_at': '2026-01-01T00:00:00Z', 'n': 3}]
        got = sr.newest_by_event(docs)
        self.assertEqual((got['a']['n'], got['b']['n']), (2, 3))

    def test_anything_soon(self):
        self.assertTrue(sr.anything_soon(TIMES, NOW))
        self.assertFalse(sr.anything_soon(TIMES, NOW - 3600))


if __name__ == '__main__':
    unittest.main()
