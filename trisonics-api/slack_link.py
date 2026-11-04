"""Sign in with Slack (OpenID Connect) so the scouting app can link a Slack
account. Pure logic only; function_app.py does the HTTP and Cosmos work.

Why the app polls: an installed iPhone home-screen PWA opens OAuth in Safari,
so a redirect back into the app would land in the wrong storage context. The
app starts a login session here, opens the Slack URL in another tab, then
asks SlackLinkStatus until the callback has filled the session in.

Configuration is per team, never global: a SlackConfigs doc (Cosmos,
partition /secret_key) for each secret key + team number that has its own
Slack app:
  {'id', 'secret_key', 'team_number': int, 'slack_team_id': 'T0123ABCD',
   'client_id', 'client_secret', 'enabled': true}
No doc (or enabled false) means that team can't link Slack. The API reads
these server-side only; nothing in them is ever sent to the app.

Environment:
  API_PUBLIC_URL     base for the redirect URI ({base}/api/SlackCallback);
                     default: taken from the request URL. Every team's Slack
                     app registers this same redirect URL.
  SLACK_FAKE=1       LOCAL TESTING ONLY; ignored in Azure (WEBSITE_INSTANCE_ID).
                     Gives secret key zz-claude-test a simulated Slack (any
                     team number) without a SlackConfigs doc; SLACK_FAKE_TEAM
                     changes the simulated workspace

Containers (SlackLinks, partition /id, per-item TTL on):
  login session {'id': session_id, 'kind': 'login', 'state', 'nonce',
                 'secret_key', 'team_number', 'created', 'ttl': 900,
                 'status': 'pending'|'done'|'error', 'result'?, 'error'?}
  link          {'id': 'slack_{team}_{user}_{key hash}', 'kind': 'link',
                 'secret_key', 'slack_user_id', 'slack_team_id', 'slack_name',
                 'link_token_hashes': [sha256], 'created', 'updated'}
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from html import escape
from urllib.parse import urlencode, urlparse

AUTHORIZE_URL = 'https://slack.com/openid/connect/authorize'
TOKEN_URL = 'https://slack.com/api/openid.connect.token'
ISSUER = 'https://slack.com'
TEAM_CLAIM = 'https://slack.com/team_id'
SESSION_TTL = 900
MAX_TOKENS_PER_LINK = 10

FAKE_TEAM = 'TFAKE'
FAKE_TEAM_KEY = 'zz-claude-test'
FAKE_USER = {'sub': 'U0FAKE01', TEAM_CLAIM: FAKE_TEAM, 'name': 'Test Scout'}
FAKE_CODE = 'fake'

NOT_CONFIGURED = "Slack linking isn't set up for your team"


class LinkError(Exception):
    """A sign-in problem whose message is safe to show the person."""


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def fake_enabled(env):
    """SLACK_FAKE=1 counts only outside Azure, so production can't have it."""
    return (str(env.get('SLACK_FAKE', '')).strip() == '1'
            and not env.get('WEBSITE_INSTANCE_ID'))


def redirect_uri(env, request_url=''):
    base = (env.get('API_PUBLIC_URL') or '').strip().rstrip('/')
    if not base and request_url:
        u = urlparse(request_url)
        base = f'{u.scheme}://{u.netloc}'
    return f'{base}/api/SlackCallback'


def parse_team_number(value):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def load_config(env, request_url, secret_key, team_number, doc):
    """One team's Slack settings, or None when that team can't link.

    [doc] is the team's SlackConfigs doc (or None). Returns {fake,
    client_id, client_secret, slack_team_id, secret_key, team_number,
    redirect_uri}.
    """
    secret_key = str(secret_key or '').strip()
    team_number = parse_team_number(team_number)
    if not secret_key or team_number is None:
        return None
    uri = redirect_uri(env, request_url)
    if fake_enabled(env) and secret_key == FAKE_TEAM_KEY:
        return {'fake': True, 'client_id': '', 'client_secret': '',
                'slack_team_id': FAKE_TEAM,
                'secret_key': secret_key, 'team_number': team_number,
                'redirect_uri': uri}
    if not isinstance(doc, dict) or doc.get('enabled') is False:
        return None
    # The doc must be for exactly this key + team (the caller queried by
    # them; checked again so a sloppy query can't hand out another team's).
    if (doc.get('secret_key') != secret_key
            or parse_team_number(doc.get('team_number')) != team_number):
        return None
    client_id = str(doc.get('client_id') or '').strip()
    client_secret = str(doc.get('client_secret') or '').strip()
    slack_team = str(doc.get('slack_team_id') or '').strip()
    if not (client_id and client_secret and slack_team):
        return None
    return {'fake': False, 'client_id': client_id,
            'client_secret': client_secret, 'slack_team_id': slack_team,
            'secret_key': secret_key, 'team_number': team_number,
            'redirect_uri': uri}


def new_login_session(cfg):
    return {'id': secrets.token_urlsafe(24), 'kind': 'login',
            'state': secrets.token_urlsafe(24),
            'nonce': secrets.token_urlsafe(24),
            'secret_key': cfg['secret_key'],
            'team_number': cfg['team_number'],
            'created': now_iso(), 'ttl': SESSION_TTL, 'status': 'pending'}


def authorize_url(cfg, session):
    if cfg['fake']:
        return (cfg['redirect_uri'] + '?' +
                urlencode({'state': session['state'], 'code': FAKE_CODE}))
    params = {'response_type': 'code', 'scope': 'openid profile',
              'client_id': cfg['client_id'],
              'redirect_uri': cfg['redirect_uri'],
              'state': session['state'], 'nonce': session['nonce']}
    # Send people straight to this team's workspace.
    params['team'] = cfg['slack_team_id']
    # Slack wants %20 between scopes, not '+'.
    return AUTHORIZE_URL + '?' + urlencode(params, quote_via=_quote)


def _quote(s, safe='', encoding=None, errors=None):
    from urllib.parse import quote
    return quote(s, safe=safe, encoding=encoding, errors=errors)


def same_secret(a, b):
    return hmac.compare_digest(str(a or '').encode(), str(b or '').encode())


def hash_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def new_link_token():
    return secrets.token_urlsafe(32)


def decode_jwt_payload(token):
    """Claims from a JWT's middle part. No signature check: the token came
    straight from Slack over TLS in the code exchange."""
    try:
        part = str(token).split('.')[1]
        part += '=' * (-len(part) % 4)
        claims = json.loads(base64.urlsafe_b64decode(part))
    except (IndexError, ValueError, TypeError):
        raise LinkError('Slack sent back something unreadable')
    if not isinstance(claims, dict):
        raise LinkError('Slack sent back something unreadable')
    return claims


def user_from_claims(claims, client_id, nonce, now=None):
    """Check iss/aud/nonce/exp and return {user_id, team_id, name}."""
    aud = claims.get('aud')
    auds = aud if isinstance(aud, list) else [aud]
    if claims.get('iss') != ISSUER:
        raise LinkError('Slack sign-in could not be verified')
    if client_id not in auds:
        raise LinkError('Slack sign-in could not be verified')
    if not same_secret(claims.get('nonce'), nonce):
        raise LinkError('Slack sign-in could not be verified')
    exp = claims.get('exp')
    if isinstance(exp, (int, float)) and exp < (now or time.time()):
        raise LinkError('This sign-in link expired — start again from the app')
    return _user(claims)


def _user(claims):
    user_id = str(claims.get('sub') or '').strip()
    team_id = str(claims.get(TEAM_CLAIM) or '').strip()
    name = str(claims.get('name') or claims.get('given_name') or '').strip()
    if not user_id or not team_id:
        raise LinkError('Slack did not say who you are')
    return {'user_id': user_id, 'team_id': team_id,
            'name': (name or user_id)[:60]}


def fake_user(env=None):
    """The simulated sign-in. SLACK_FAKE_TEAM (fake mode only) changes the
    simulated workspace, to test the not-allowed path."""
    claims = dict(FAKE_USER)
    team = ((env or {}).get('SLACK_FAKE_TEAM') or '').strip()
    if team:
        claims[TEAM_CLAIM] = team
    return _user(claims)


def check_workspace(cfg, team_id):
    """Only the team's own Slack workspace can link under its key."""
    if team_id != cfg['slack_team_id']:
        raise LinkError("That Slack account isn't in your team's Slack "
                        'workspace')


def link_id(team_id, user_id, secret_key):
    return f'slack_{team_id}_{user_id}_{hash_token(secret_key)[:16]}'


def add_token_hash(link, token_hash):
    hashes = [h for h in link.get('link_token_hashes', []) if h != token_hash]
    hashes.append(token_hash)
    link['link_token_hashes'] = hashes[-MAX_TOKENS_PER_LINK:]
    return link


def result_for(user, link_token):
    return {'slack_user_id': user['user_id'],
            'slack_team_id': user['team_id'], 'slack_name': user['name'],
            'link_token': link_token}


def page(ok, message):
    """A tiny standalone result page: no external assets, escaped text."""
    title = 'Slack linked' if ok else 'Slack link problem'
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(title)}</title><style>'
        'body{font:18px/1.5 system-ui,sans-serif;margin:0;padding:2rem 1rem;'
        'background:#fff;color:#111}main{max-width:32rem;margin:0 auto}'
        'h1{font-size:1.4rem}@media(prefers-color-scheme:dark){'
        'body{background:#121212;color:#eee}}'
        f'</style></head><body><main><h1>{escape(title)}</h1>'
        f'<p role="status">{escape(message)}</p></main></body></html>')
