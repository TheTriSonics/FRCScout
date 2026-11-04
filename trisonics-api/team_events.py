"""A team's season: every event it attended, with how it did and its awards.

Built from three TBA calls (events, per-event statuses, awards) by
function_app.GetTeamEvents. Pure shaping only, so it can be tested without
the network.
"""
import re

_TAG = re.compile(r'<[^>]+>')


def plain(s):
    """TBA status strings carry <b> tags; drop them."""
    return _TAG.sub('', s or '').strip() or None


def season(team_number, events, statuses, awards):
    """[events] = /team/{key}/events/{year}, [statuses] =
    /team/{key}/events/{year}/statuses ({event_key: status or None}),
    [awards] = /team/{key}/awards/{year}. Returns events sorted by start date:
    [{event_key, name, type, week, start_date, end_date, city, state_prov,
      country, qual_rank, num_teams, qual_record, alliance, playoff,
      summary, awards}]."""
    by_event = {}
    for a in awards or []:
        by_event.setdefault(a.get('event_key'), []).append(a.get('name'))
    rows = []
    for e in events or []:
        key = e.get('key')
        st = (statuses or {}).get(key) or {}
        qual = st.get('qual') or {}
        rank = qual.get('ranking') or {}
        rec = rank.get('record') or {}
        playoff = st.get('playoff') or {}
        prec = playoff.get('record') or {}
        rows.append({
            'event_key': key,
            'name': e.get('name'),
            'type': e.get('event_type_string') or _EVENT_TYPES.get(e.get('event_type')),
            'week': None if e.get('week') is None else int(e['week']) + 1,
            'start_date': e.get('start_date'),
            'end_date': e.get('end_date'),
            'city': e.get('city'),
            'state_prov': e.get('state_prov'),
            'country': e.get('country'),
            'qual_rank': rank.get('rank'),
            'num_teams': qual.get('num_teams'),
            'qual_record': (f"{rec.get('wins', 0)}-{rec.get('losses', 0)}-{rec.get('ties', 0)}"
                            if rec else None),
            'alliance': plain(st.get('alliance_status_str')) if st.get('alliance') else None,
            'playoff': ({'status': playoff.get('status'), 'level': playoff.get('level'),
                         'record': f"{prec.get('wins', 0)}-{prec.get('losses', 0)}-{prec.get('ties', 0)}"}
                        if playoff else None),
            'summary': plain(st.get('overall_status_str')),
            'awards': by_event.get(key, []),
        })
    rows.sort(key=lambda r: (r['start_date'] or '', r['event_key'] or ''))
    return {'team_number': int(team_number), 'events': rows}


# TBA event_type codes, in case event_type_string is missing.
_EVENT_TYPES = {0: 'Regional', 1: 'District', 2: 'District Championship',
                3: 'Championship Division', 4: 'Championship Finals',
                5: 'District Championship Division', 6: 'Festival of Champions',
                7: 'Remote', 99: 'Offseason', 100: 'Preseason'}
