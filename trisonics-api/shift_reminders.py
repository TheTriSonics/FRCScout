"""Slack DMs a few minutes before each scouting shift. Pure logic only;
function_app.py does the Cosmos, TBA and Slack calls.

Every few minutes a timer looks at every team with a Slack bot token (its
SlackConfigs doc), takes the newest published schedule for each of that
team's events, and DMs each linked scouter (Scouters doc with
slack_user_id) whose shift's first match starts within LEAD_MINUTES (or
started less than GRACE_MINUTES ago, in case a run was missed).

A ShiftReminders doc per reminder sent stops repeats. Its key covers the
scouter, station, matches and the schedule's time offset, so republishing
an unchanged shift doesn't send again, but a changed one does.

Practice runs: a schedule may carry 'time_offset' (seconds), set when it was
published in the app's schedule test mode. Every match time is moved by it,
so an old event's schedule can be replayed today.
"""

import hashlib

from pick_votes import voter_key
from scout_schedule import station_label

LEAD_MINUTES = 15
GRACE_MINUTES = 5
RECORD_TTL = 30 * 86400
MAX_OFFSET = 400 * 86400


def clean_offset(value):
    """A schedule's time offset in whole seconds; 0 when missing or silly."""
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return n if abs(n) <= MAX_OFFSET else 0


def moved_times(times, offset):
    """{match: start} with every start moved by [offset] seconds."""
    return {m: t + offset for m, t in times.items()} if offset else dict(times)


def anything_soon(times, now, lead=LEAD_MINUTES, grace=GRACE_MINUTES):
    """Whether any match starts in the reminder window (cheap skip)."""
    return any(now - grace * 60 <= t <= now + lead * 60
               for t in times.values())


def reminder_key(secret_key, event_key, shift, offset):
    raw = '|'.join(str(x) for x in (
        secret_key, event_key, voter_key(shift['scouter_name']),
        shift['station'], shift['first_match'], shift['last_match'], offset))
    return 'rem_' + hashlib.sha256(raw.encode()).hexdigest()[:40]


def _range(a, b):
    return f'Q{a}' if a == b else f'Q{a}–Q{b}'


def _slack_time(unix):
    """Slack shows this in the reader's own time zone."""
    return f'<!date^{int(unix)}^{{time}}|soon>'


def message(shift, start, now, mates, practice):
    mins = round((start - now) / 60)
    when = (f'in about {mins} min' if mins > 1
            else 'starting now' if mins >= -1 else 'already started')
    text = (f"{'Practice run: ' if practice else ''}"
            f"Scouting shift {when}: *{station_label(shift['station'])}*, "
            f"{_range(shift['first_match'], shift['last_match'])}. "
            f"Q{shift['first_match']} starts about {_slack_time(start)}.")
    if mates:
        text += ' With: ' + ', '.join(mates) + '.'
    return text


def due_reminders(*, secret_key, event_key, schedule, times, slack_users,
                  sent, now, lead=LEAD_MINUTES, grace=GRACE_MINUTES):
    """Reminders to send now.

    [times] are the event's real qual start times ({match: unix}); the
    schedule's time_offset is applied here. [slack_users] maps voter_key(name)
    to a Slack user ID. [sent] holds keys already sent (or a callable that
    says whether a key was). Returns [{'key', 'user', 'text', 'start',
    'scouter_name'}], earliest first.
    """
    offset = clean_offset(schedule.get('time_offset'))
    times = moved_times(times, offset)
    shifts = schedule.get('shifts') or []
    was_sent = sent if callable(sent) else (lambda k: k in sent)
    out = []
    for s in shifts:
        start = times.get(s['first_match'])
        if start is None or not now - grace * 60 <= start <= now + lead * 60:
            continue
        user = slack_users.get(voter_key(s['scouter_name']))
        if not user:
            continue
        key = reminder_key(secret_key, event_key, s, offset)
        if was_sent(key):
            continue
        # Who else is scouting when this shift starts.
        mates = sorted(
            {o['scouter_name'] for o in shifts
             if o is not s and o['first_match'] <= s['first_match'] <= o['last_match']
             and voter_key(o['scouter_name']) != voter_key(s['scouter_name'])},
            key=str.lower)
        out.append({'key': key, 'user': user, 'start': start,
                    'scouter_name': s['scouter_name'],
                    'text': message(s, start, now, mates, bool(offset))})
    out.sort(key=lambda r: r['start'])
    return out


def newest_by_event(schedules):
    """{event_key: newest schedule} from any number of schedule docs."""
    newest = {}
    for d in schedules:
        ek = d.get('event_key')
        if ek and d.get('published_at', '') >= newest.get(ek, {}).get(
                'published_at', ''):
            newest[ek] = d
    return newest
