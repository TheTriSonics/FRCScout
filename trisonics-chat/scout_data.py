"""Read-only access to the scouting API, cached briefly per process.

Everything here goes through the public trisonics-scouting-api GET
endpoints, so the bot can never write anything. Responses are cached for
CACHE_TTL seconds; one chat turn often calls several tools that need the
same data.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

API_BASE = os.environ.get(
    'SCOUT_API_BASE', 'https://trisonics-scouting-api.azurewebsites.net/api')
TIMEOUT = 60
CACHE_TTL = 120

_cache = {}


def get(route, **params):
    """GET {API_BASE}/{route}?params as parsed JSON (cached)."""
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f'{API_BASE}/{route}?{query}'
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        body = resp.read()
    data = json.loads(body) if body else None
    _cache[url] = (time.time(), data)
    return data


def voter_key(name):
    """Same normalization as pick_votes.voter_key / the app's voterKey."""
    return re.sub(r'[^a-z0-9]+', '-', (name or '').strip().lower()).strip('-')


class Event:
    """One user's view of one event: public data plus their secret key's data."""

    def __init__(self, secret_key, event_key):
        self.secret_key = secret_key
        self.event_key = event_key
        self.year = int(event_key[:4])

    # --- raw endpoints ---

    def info(self):
        for e in get('GetEvents', year=self.year) or []:
            if e.get('key') == self.event_key:
                return e
        return {}

    def tz(self):
        try:
            return ZoneInfo(self.info().get('timezone') or 'America/Detroit')
        except Exception:
            return ZoneInfo('America/Detroit')

    def teams(self):
        return get('GetTeamsForEvent', event_key=self.event_key) or []

    def team_names(self):
        return {t['number']: t.get('name') for t in self.teams()}

    def matches(self):
        return get('GetMatchesForEvent', event_key=self.event_key) or []

    def statbotics(self):
        try:
            return {m['key']: m for m in get('GetStatboticsMatches', event_key=self.event_key) or []}
        except Exception:
            return {}

    def opr(self):
        return {int(r['teamNumber']): r for r in get('GetOPRData', event_key=self.event_key) or []}

    def rankings(self):
        return get('GetRankings', event_key=self.event_key) or {}

    def scouted(self):
        rows = get('GetResults', event_key=self.event_key, secret_team_key=self.secret_key) or []
        return [r for r in rows if r.get('secret_team_key') == self.secret_key]

    def pit(self):
        rows = get('GetPitResults', event_key=self.event_key, secret_team_key=self.secret_key) or []
        return [r for r in rows if r.get('secret_team_key') == self.secret_key]

    def scouters(self):
        return get('GetScouters', secret_key=self.secret_key, event_key=self.event_key) or []

    def schedule(self):
        """Newest published schedule, or None."""
        scheds = get('GetSchedules', secret_key=self.secret_key, event_key=self.event_key) or []
        return max(scheds, key=lambda s: s.get('published_at') or '', default=None)

    def pick_votes(self):
        return get('GetPickVotes', secret_key=self.secret_key, event_key=self.event_key) or {}

    # --- time helpers ---

    def fmt_time(self, unix):
        if not unix:
            return None
        if unix > 1e11:  # some TBA fields are milliseconds
            unix = unix / 1000
        dt = datetime.fromtimestamp(unix, tz=timezone.utc).astimezone(self.tz())
        return dt.strftime('%a %b %d %I:%M %p').replace(' 0', ' ')

    def now_str(self):
        return datetime.now(tz=self.tz()).strftime('%a %b %d %Y %I:%M %p %Z')


def team_num(key):
    """'frc4003' or 4003 -> 4003."""
    if isinstance(key, int):
        return key
    return int(str(key).replace('frc', ''))


def match_start(m):
    """Best known start time (unix seconds) for a TBA match."""
    for k in ('actual_time', 'predicted_time', 'time'):
        t = m.get(k)
        if t:
            return t / 1000 if t > 1e11 else t
    return None


LEVEL_ORDER = {'qm': 0, 'ef': 1, 'qf': 2, 'sf': 3, 'f': 4}


def match_sort_key(m):
    return (LEVEL_ORDER.get(m.get('comp_level'), 9), m.get('set_number') or 0, m.get('match_number') or 0)


def match_label(m):
    lvl = m.get('comp_level')
    if lvl == 'qm':
        return f"Qual {m['match_number']}"
    if lvl == 'sf':
        return f"Playoff {m['set_number']}"
    if lvl == 'f':
        return f"Final {m['match_number']}"
    return f"{lvl.upper()} {m.get('set_number')}-{m.get('match_number')}"
