"""Register the scouter names already in an event's match and pit results.

Run from trisonics-api with the venv active and the env loaded:
    source ./setenv && python tools/seed_scouters.py [secret_key event_key]
Defaults to secret key 4003data, event 2026miwmi. Names are de-duplicated by
pick_votes.voter_key (first spelling wins); first_seen is the earliest record
time found for the name, when records carry one.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import function_app  # noqa: E402
import pick_votes  # noqa: E402

SK = sys.argv[1] if len(sys.argv) > 2 else '4003data'
EK = sys.argv[2] if len(sys.argv) > 2 else '2026miwmi'
TIME_FIELDS = ('created_at', 'timestamp', 'time', 'submitted_at', '_ts')


def record_time(doc):
    for f in TIME_FIELDS:
        v = doc.get(f)
        if v in (None, ''):
            continue
        if f == '_ts':
            import time
            return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(v)))
        if isinstance(v, str):
            return v if v.endswith('Z') else v + 'Z'
    return None


def main():
    found = {}  # voter_key -> [name, earliest time or None, source counts]
    for cname in (f'MatchResults{EK[:4]}', f'PitResults{EK[:4]}'):
        container = function_app.get_container(cname)
        docs = container.query_items(
            query="SELECT * FROM c WHERE c.event_key = @ek AND "
                  "TRIM(LOWER(c.secret_team_key)) = TRIM(LOWER(@sk))",
            parameters=[{'name': '@ek', 'value': EK},
                        {'name': '@sk', 'value': SK}],
            enable_cross_partition_query=True)
        for d in docs:
            name = str(d.get('scouter_name') or '').strip()
            if not name:
                continue
            try:
                key = pick_votes.voter_key(name)
            except ValueError:
                continue
            t = record_time(d)
            entry = found.setdefault(key, [name, None, {}])
            entry[2][cname] = entry[2].get(cname, 0) + 1
            if t and (entry[1] is None or t < entry[1]):
                entry[1] = t
    for key, (name, first, counts) in sorted(found.items()):
        function_app._register_scouter(SK, EK, name, first)
        print(name, first, counts)
    print(f'{len(found)} names')


if __name__ == '__main__':
    main()
