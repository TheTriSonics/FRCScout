"""Slack side of the chat bot: request signing, who's asking, thread history.

Each team uses its own Slack app, the same one as Sign in with Slack and
shift reminders. Its SlackConfigs doc (Cosmos, filled in by hand) supplies
slack_app_id, slack_team_id, bot_token and signing_secret. A Slack user is
matched to a scout through the Scouters docs that Sign in with Slack linked
(slack_user_id). The secret key comes from that config, never from the
message.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request

from azure.cosmos import CosmosClient

CONFIG_TTL = 300
PLACEHOLDER = ':hourglass_flowing_sand: Looking that up…'
NOT_LINKED = ("I don't know who you are yet. In the scouting app, open *Settings → "
              'Link Slack account*, then ask me again.')

_db = None
_configs = (0.0, [])


def _container(name):
    global _db
    if _db is None:
        client = CosmosClient(os.environ['COSMOS_ENDPOINT'], os.environ['COSMOS_READ_KEY'])
        _db = client.get_database_client('ScoutingData')
    return _db.get_container_client(name)


def configs():
    """Enabled SlackConfigs docs that can run the bot (cached a few minutes)."""
    global _configs
    if time.time() - _configs[0] > CONFIG_TTL:
        rows = _container('SlackConfigs').query_items(
            'SELECT * FROM c WHERE IS_DEFINED(c.signing_secret) AND IS_DEFINED(c.bot_token)',
            enable_cross_partition_query=True)
        _configs = (time.time(), [r for r in rows if r.get('enabled') is not False])
    return _configs[1]


def verify(signing_secret, timestamp, body: bytes, signature) -> bool:
    """Slack's v0 request signature, rejecting anything over 5 minutes old."""
    if not (signing_secret and timestamp and signature):
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    base = b'v0:' + timestamp.encode() + b':' + body
    mine = 'v0=' + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mine, signature)


def config_for(payload, timestamp, body, signature):
    """The config whose signing secret signed this request, or None.

    Event callbacks name their app (api_app_id) and workspace (team_id), so
    only that team's config is tried. url_verification names neither, so
    every config is tried.
    """
    app_id, team_id = payload.get('api_app_id'), payload.get('team_id')
    for cfg in configs():
        if app_id and cfg.get('slack_app_id') != app_id:
            continue
        if team_id and cfg.get('slack_team_id') != team_id:
            continue
        if verify(cfg['signing_secret'], timestamp, body, signature):
            return cfg
    return None


def config_by_id(cfg_id):
    return next((c for c in configs() if c['id'] == cfg_id), None)


def scout_for(cfg, slack_user_id):
    """(scouter_name, event_key) for the most recent Scouters doc linked to
    this Slack user under this team's key and workspace, or None."""
    rows = list(_container('Scouters').query_items(
        'SELECT c.scouter_name, c.event_key, c.last_seen FROM c WHERE c.secret_key = @sk '
        'AND c.slack_user_id = @u AND c.slack_team_id = @t',
        parameters=[{'name': '@sk', 'value': cfg['secret_key']},
                    {'name': '@u', 'value': slack_user_id},
                    {'name': '@t', 'value': cfg['slack_team_id']}],
        enable_cross_partition_query=True))
    if not rows:
        return None
    best = max(rows, key=lambda r: r.get('last_seen') or '')
    return best['scouter_name'], best['event_key']


# --- Slack Web API ---

def api(token, method, **params):
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    req = urllib.request.Request(f'https://slack.com/api/{method}', data=data,
                                 headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except Exception as e:
        logging.error('Slack %s failed: %s', method, type(e).__name__)
        return {'ok': False, 'error': type(e).__name__}
    if not body.get('ok'):
        logging.error('Slack %s: %s', method, body.get('error'))
    return body


MENTION = re.compile(r'<@[A-Z0-9]+>')


def clean(text):
    return MENTION.sub('', text or '').strip()


def history(token, ev, bot_user_id):
    """Earlier turns of this conversation as [(role, text)], oldest first.

    In a thread: the thread so far. In a DM outside a thread: the last 30
    minutes of the DM. A channel mention outside a thread starts fresh.
    """
    ts, thread = ev['ts'], ev.get('thread_ts')
    if thread:
        msgs = api(token, 'conversations.replies', channel=ev['channel'], ts=thread,
                   limit=40).get('messages') or []
    elif ev.get('channel_type') == 'im':
        msgs = api(token, 'conversations.history', channel=ev['channel'], limit=12,
                   oldest=str(time.time() - 1800)).get('messages') or []
        msgs.reverse()
    else:
        return []
    out = []
    for m in msgs:
        if m.get('ts') == ts or float(m.get('ts', 0)) > float(ts):
            continue
        text = clean(m.get('text'))
        if not text or text == PLACEHOLDER:
            continue
        mine = m.get('user') == bot_user_id or bool(m.get('bot_id'))
        out.append(('assistant' if mine else 'user', text))
    return out[-20:]


def to_mrkdwn(text):
    """Patch the usual Markdown habits Slack doesn't render."""
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'^#{1,6}\s*(.+)$', r'*\1*', text, flags=re.M)
    return text


# --- per-user rate limit (per instance; the plan keeps instances few) ---

RATE_PER_HOUR = int(os.environ.get('SLACK_QUESTIONS_PER_HOUR', '40'))
_recent = {}


def over_limit(user):
    now = time.time()
    times = [t for t in _recent.get(user, []) if now - t < 3600]
    _recent[user] = times
    if len(times) >= RATE_PER_HOUR:
        return True
    times.append(now)
    return False


class Seen:
    """Recently seen ids (an hour's worth, per instance)."""

    def __init__(self, ttl=3600):
        self.ttl, self.ids = ttl, {}

    def add(self, key):
        """True the first time [key] is seen; falsy keys always count as new."""
        if not key:
            return True
        now = time.time()
        self.ids = {k: t for k, t in self.ids.items() if now - t < self.ttl}
        if key in self.ids:
            return False
        self.ids[key] = now
        return True
