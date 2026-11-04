import json
import unittest
from unittest import mock

import azure.functions as func

import function_app


def _call(params):
    req = func.HttpRequest(method='GET', url='/api/GetPitResults', params=params,
                           body=b'')
    return function_app.get_pit_results.build().get_user_function()(req)


class GetPitResultsKeyTest(unittest.TestCase):
    def test_missing_or_blank_key_is_400_and_never_queries(self):
        for params in ({'event_key': '2026miwmi'},
                       {'event_key': '2026miwmi', 'secret_team_key': ''},
                       {'event_key': '2026miwmi', 'secret_team_key': '  '}):
            with mock.patch.object(function_app, 'get_pit_data') as q:
                resp = _call(params)
            self.assertEqual(resp.status_code, 400)
            self.assertIn('error', json.loads(resp.get_body()))
            q.assert_not_called()

    def test_key_is_passed_to_the_query(self):
        with mock.patch.object(function_app, 'get_pit_data',
                               return_value=None) as q:
            resp = _call({'event_key': '2026miwmi', 'secret_team_key': 'k'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(q.call_args.kwargs['secret_team_key'], 'k')


if __name__ == '__main__':
    unittest.main()
