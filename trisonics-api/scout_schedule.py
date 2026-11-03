"""Match-scouting schedules and their calendar feed.

Containers (both partitioned by /event_key, created on first use):

  Scouters:       one doc per secret key + event + normalized name
      {'id': '{sk}_{ek}_{voter_key}', 'kind': 'scouter', 'secret_key',
       'event_key', 'scouter_name', 'name_key', 'first_seen', 'last_seen',
       'calendar_token'}
  ScoutSchedules: one doc per secret key + event + publisher
      {'id': '{sk}_{ek}_{voter_key(published_by)}', 'kind': 'schedule',
       'secret_key', 'event_key', 'published_by', 'published_at',
       'shifts': [{'scouter_name', 'station', 'first_match', 'last_match'}]}

A shift is one scouter on one station for qualification matches
first_match..last_match inclusive. The app uses the newest schedule.
"""

import hashlib
import time

from pick_votes import voter_key

STATIONS = ('red1', 'red2', 'red3', 'blue1', 'blue2', 'blue3')
MATCH_MINUTES = 8       # a shift ends this long after its last match starts
ALARM_MINUTES = 15


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


# --- iCalendar (RFC 5545), written by hand ---

def _escape(text):
    return (str(text).replace('\\', '\\\\').replace(';', '\\;')
            .replace(',', '\\,').replace('\r\n', '\n').replace('\r', '\n')
            .replace('\n', '\\n'))


def _fold(line):
    """Fold to 75 octets per line, never splitting a UTF-8 character."""
    data = line.encode('utf-8')
    if len(data) <= 75:
        return [line]
    out, limit = [], 75
    while data:
        cut = min(limit, len(data))
        while cut < len(data) and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(data[:cut].decode('utf-8'))
        data = data[cut:]
        limit = 74  # continuation lines start with a space
    return [out[0]] + [' ' + p for p in out[1:]]


def _stamp(unix):
    return time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(unix))


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


def build_calendar(*, secret_key, event_key, scouter_name, schedule, times,
                   now=None):
    """The scouter's shifts as an iCalendar string (CRLF line endings)."""
    now = int(now if now is not None else time.time())
    me = voter_key(scouter_name)
    published_by = (schedule or {}).get('published_by', '')
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0',
        'PRODID:-//Trisonics//Scouting Schedule//EN', 'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:' + _escape(f'Scouting \u2013 {event_key}'),
        'REFRESH-INTERVAL;VALUE=DURATION:PT15M', 'X-PUBLISHED-TTL:PT15M',
    ]
    for s in (schedule or {}).get('shifts', []):
        if voter_key(s['scouter_name']) != me:
            continue
        start = times.get(s['first_match'])
        last = times.get(s['last_match'])
        if start is None or last is None:
            continue  # match times aren't known yet
        end = last + MATCH_MINUTES * 60
        uid = hashlib.sha256(
            f"{secret_key}|{event_key}|{s['station']}|{s['first_match']}"
            .encode()).hexdigest()[:32] + '@trisonics-scouting'
        q1, q2 = s['first_match'], s['last_match']
        rng = f'Q{q1}' if q1 == q2 else f'Q{q1}\u2013Q{q2}'
        summary = f"Scout {station_label(s['station'])} \u00b7 {rng}"
        lines += [
            'BEGIN:VEVENT', f'UID:{uid}', f'DTSTAMP:{_stamp(now)}',
            f'DTSTART:{_stamp(start)}', f'DTEND:{_stamp(end)}',
            'SUMMARY:' + _escape(summary),
            'DESCRIPTION:' + _escape(f'{event_key}\nPublished by {published_by}'),
            'BEGIN:VALARM', f'TRIGGER:-PT{ALARM_MINUTES}M', 'ACTION:DISPLAY',
            'DESCRIPTION:Scouting shift starting soon', 'END:VALARM',
            'END:VEVENT',
        ]
    lines.append('END:VCALENDAR')
    folded = [p for line in lines for p in _fold(line)]
    return '\r\n'.join(folded) + '\r\n'
