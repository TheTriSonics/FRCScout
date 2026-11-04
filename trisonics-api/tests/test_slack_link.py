import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import slack_link as sl  # noqa: E402


def jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=')
    return 'h.' + body.decode() + '.s'


GOOD = {'iss': 'https://slack.com', 'aud': 'CID', 'nonce': 'N1',
        'sub': 'U1', sl.TEAM_CLAIM: 'T1', 'name': 'Ann', 'exp': 4102444800}
DOC = {'id': 'x', 'secret_key': 'club', 'team_number': 4003,
       'slack_team_id': 'T1', 'client_id': 'CID', 'client_secret': 'sec'}
URL = 'https://x.net/api/SlackLinkStart'


def cfg_for(doc=DOC, env=None, key='club', team=4003, url=URL):
    return sl.load_config(env or {}, url, key, team, doc)


class SlackLinkTests(unittest.TestCase):
    def test_claims_ok(self):
        u = sl.user_from_claims(sl.decode_jwt_payload(jwt(GOOD)), 'CID', 'N1')
        self.assertEqual(u, {'user_id': 'U1', 'team_id': 'T1', 'name': 'Ann'})

    def test_claims_rejects(self):
        for change in ({'nonce': 'x'}, {'aud': 'other'}, {'iss': 'evil'},
                       {'exp': 1}, {'sub': ''}):
            with self.assertRaises(sl.LinkError):
                sl.user_from_claims({**GOOD, **change}, 'CID', 'N1')

    def test_bad_jwt(self):
        for t in ('', 'a', 'a.!!.b', 'a.' + 'bnVsbA' + '.b'):
            with self.assertRaises(sl.LinkError):
                sl.decode_jwt_payload(t)

    def test_workspace_must_match(self):
        cfg = cfg_for()
        sl.check_workspace(cfg, 'T1')
        with self.assertRaises(sl.LinkError):
            sl.check_workspace(cfg, 'T2')

    def test_config_per_team_only(self):
        # No doc: nobody gets Slack, whatever the environment says.
        self.assertIsNone(cfg_for(doc=None))
        self.assertIsNone(cfg_for(doc=None, env={
            'SLACK_CLIENT_ID': 'CID', 'SLACK_CLIENT_SECRET': 's'}))
        # The doc must be for exactly this key + team number.
        self.assertIsNone(cfg_for(key='other'))
        self.assertIsNone(cfg_for(team=1234))
        self.assertIsNone(cfg_for(team='nope'))
        self.assertIsNone(cfg_for(key=''))
        self.assertIsNone(cfg_for(doc={**DOC, 'client_secret': ''}))
        self.assertIsNone(cfg_for(doc={**DOC, 'slack_team_id': ''}))
        self.assertIsNone(cfg_for(doc={**DOC, 'enabled': False}))
        self.assertIsNotNone(cfg_for(team='4003'))
        cfg = cfg_for()
        self.assertEqual(cfg['redirect_uri'], 'https://x.net/api/SlackCallback')
        self.assertEqual(cfg['client_secret'], 'sec')
        cfg = cfg_for(env={'API_PUBLIC_URL': 'https://p.org/'}, url='')
        self.assertEqual(cfg['redirect_uri'], 'https://p.org/api/SlackCallback')

    def test_fake_refused_in_azure(self):
        local = {'SLACK_FAKE': '1', 'LOCAL_DEV': '1'}
        self.assertTrue(sl.fake_enabled(local))
        # Off unless LOCAL_DEV is set, and never on an Azure host.
        self.assertFalse(sl.fake_enabled({'SLACK_FAKE': '1'}))
        for marker in sl.AZURE_MARKERS:
            self.assertFalse(sl.fake_enabled({**local, marker: 'x'}))
            self.assertFalse(sl.local_dev({'LOCAL_DEV': '1', marker: 'x'}))
        azure = {**local, 'WEBSITE_SITE_NAME': 'abc'}
        self.assertIsNone(cfg_for(doc=None, env=azure, key='zz-claude-test'))
        fake = cfg_for(doc=None, env=local, key='zz-claude-test')
        self.assertTrue(fake['fake'])
        self.assertEqual(fake['slack_team_id'], 'TFAKE')
        # Fake mode is only for the test key.
        self.assertIsNone(cfg_for(doc=None, env=local))

    def test_authorize_url(self):
        cfg = cfg_for()
        s = sl.new_login_session(cfg)
        self.assertEqual((s['secret_key'], s['team_number']), ('club', 4003))
        url = sl.authorize_url(cfg, s)
        self.assertIn('scope=openid%20profile', url)
        self.assertIn('team=T1', url)
        self.assertIn('client_id=CID', url)
        self.assertNotIn('sec', url.replace('scope', ''))
        self.assertIn('nonce=' + s['nonce'], url)

    def test_link_ids_per_key(self):
        self.assertNotEqual(sl.link_id('T1', 'U1', 'a'), sl.link_id('T1', 'U1', 'b'))
        self.assertNotIn('club', sl.link_id('T1', 'U1', 'club'))
        r = sl.result_for({'user_id': 'U1', 'team_id': 'T1', 'name': 'A'}, 'tok')
        self.assertNotIn('secret_key', r)

    def test_tokens(self):
        t = sl.new_link_token()
        self.assertEqual(sl.hash_token(t), sl.hash_token(t))
        self.assertNotEqual(sl.hash_token(t), sl.hash_token(t + 'x'))
        link = {}
        for i in range(15):
            sl.add_token_hash(link, str(i))
        self.assertEqual(len(link['link_token_hashes']), 10)
        self.assertTrue(sl.same_secret('a', 'a'))
        self.assertFalse(sl.same_secret('a', None))

    def test_page_escapes(self):
        self.assertNotIn('<script>', sl.page(True, '<script>x</script>'))


if __name__ == '__main__':
    unittest.main()
