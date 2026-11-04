"""Match-scouting schedules.

Containers (both partitioned by /event_key, created on first use):

  Scouters:       one doc per secret key + event + normalized name
      {'id': '{sk}_{ek}_{voter_key}', 'kind': 'scouter', 'secret_key',
       'event_key', 'scouter_name', 'name_key', 'first_seen', 'last_seen'}
      (docs from before the calendar feed was dropped may still carry an
      unused 'calendar_token')
  ScoutSchedules: one doc per secret key + event + publisher
      {'id': '{sk}_{ek}_{voter_key(published_by)}', 'kind': 'schedule',
       'secret_key', 'event_key', 'published_by', 'published_at',
       'shifts': [{'scouter_name', 'station', 'first_match', 'last_match'}]}

A shift is one scouter on one station for qualification matches
first_match..last_match inclusive. The app uses the newest schedule.
"""

import time

from pick_votes import voter_key

STATIONS = ('red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3')
MATCH_MINUTES = 8       # a shift ends this long after its last match starts


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def scouter_id(secret_key, event_key, name):
    return f'{secret_key}_{event_key}_{voter_key(name)}'


def schedule_id(secret_key, event_key, published_by):
    return f'{secret_key}_{event_key}_{voter_key(published_by)}'


def clean_shifts(raw):
    """Validate and normalize a shift list; raises ValueError with a message."""
    if not isinstance(raw, list):
        raise ValueError('shifts must be a list')
    if len(raw) > 2000:
        raise ValueError('too many shifts')
    shifts = []
    for i, s in enumerate(raw, 1):
        if not isinstance(s, dict):
            raise ValueError(f'shift {i}: must be an object')
        name = str(s.get('scouter_name') or '').strip()[:60]
        station = str(s.get('station') or '').strip().lower()
        if not name:
            raise ValueError(f'shift {i}: scouter_name is required')
        if station not in STATIONS:
            raise ValueError(
                f'shift {i}: station must be one of {", ".join(STATIONS)}')
        try:
            first, last = s['first_match'], s['last_match']
            if isinstance(first, bool) or isinstance(last, bool):
                raise TypeError
            first, last = int(first), int(last)
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f'shift {i}: first_match and last_match must be integers')
        if first < 1 or last < first:
            raise ValueError(
                f'shift {i}: need 1 <= first_match <= last_match')
        shifts.append({'scouter_name': name, 'station': station,
                       'first_match': first, 'last_match': last})
    return shifts


def station_label(station):
    return f'{station[:-1].capitalize()} {station[-1]}'


# --- Match times (for shift reminders) ---

def qual_times(matches):
    """{qual match number: start unix seconds} from TBA simple matches."""
    times = {}
    for m in matches:
        if m.get('comp_level') != 'qm':
            continue
        t = m.get('predicted_time') or m.get('time')
        if t:
            times[int(m['match_number'])] = int(t)
    return times

