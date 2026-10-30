"""Pick list document logic for the ScoutingResults container.

One document per {secret_key}_{event_key}:
    {
        'id', 'secret_key', 'event_key',
        'teams': [{'team_number', 'ranking', 'dnp', 'decline', 'notes',
                   'picked'}],
        'version', 'updated_by', 'updated_at',
    }

`ranking` is a dense 1..n pick order. A team that is DNP or Decline has no
ranking. `picked` marks a team taken by another alliance during selection and
is independent of ranking so the list keeps its shape.

Updates are applied one team at a time against the latest stored document so
that concurrent editors never overwrite each other's changes.
"""

import datetime

STATUSES = ('dnp', 'decline', 'unranked')


def new_doc(secret_key, event_key):
    return {
        'id': doc_id(secret_key, event_key),
        'secret_key': secret_key,
        'event_key': event_key,
        'teams': [],
        'version': 0,
    }


def doc_id(secret_key, event_key):
    return f'{secret_key}_{event_key}'


def _is_ranked(entry):
    return (entry.get('ranking') is not None
            and not entry.get('dnp') and not entry.get('decline'))


def _is_empty(entry):
    return (not _is_ranked(entry) and not entry.get('dnp')
            and not entry.get('decline') and not entry.get('notes')
            and not entry.get('picked'))


def _sort_key(entry):
    ranked = _is_ranked(entry)
    return (not ranked, entry['ranking'] if ranked else 0,
            entry['team_number'])


def apply_update(doc, team_number, position=None, status=None, notes=None,
                 picked=None):
    """Apply a single-team change to a pick list doc in place.

    position: 1-based slot in the pick order; inserts the team there and
              shifts the rest down. Clears DNP/Decline.
    status:   'dnp', 'decline' or 'unranked'; removes the team from the
              pick order.
    notes:    replaces the team's notes.
    picked:   marks the team as taken (or not) by another alliance.
    """
    if position is not None and status is not None:
        raise ValueError('position and status are mutually exclusive')
    if status is not None and status not in STATUSES:
        raise ValueError(f'status must be one of {STATUSES}')

    teams = doc.setdefault('teams', [])
    entry = next((t for t in teams if t.get('team_number') == team_number),
                 None)
    if entry is None:
        entry = {'team_number': team_number, 'ranking': None, 'dnp': False,
                 'decline': False, 'notes': '', 'picked': False}
        teams.append(entry)

    if position is not None or status is not None:
        ranked = sorted((t for t in teams if t is not entry and _is_ranked(t)),
                        key=lambda t: t['ranking'])
        if position is not None:
            entry['dnp'] = False
            entry['decline'] = False
            idx = max(0, min(int(position) - 1, len(ranked)))
            ranked.insert(idx, entry)
        else:
            entry['dnp'] = status == 'dnp'
            entry['decline'] = status == 'decline'
            entry['ranking'] = None
        # Legacy (Streamlit) docs may have gaps in ranking; close them.
        for i, t in enumerate(ranked, start=1):
            t['ranking'] = i
    # DNP/Decline never carry a stale ranking.
    for t in teams:
        if not _is_ranked(t):
            t['ranking'] = None

    if notes is not None:
        entry['notes'] = str(notes).strip()
    if picked is not None:
        entry['picked'] = bool(picked)

    teams[:] = sorted((t for t in teams if not _is_empty(t)), key=_sort_key)
    return doc


def stamp(doc, updated_by):
    doc['version'] = int(doc.get('version') or 0) + 1
    doc['updated_by'] = updated_by or ''
    doc['updated_at'] = datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec='seconds')
    return doc


def carry_picked(new_doc_body, existing_doc):
    """Preserve `picked` flags when a legacy full-document write (Streamlit
    PostScoutingResults) replaces a doc that it doesn't know about."""
    if not existing_doc:
        return new_doc_body
    picked = {t['team_number'] for t in existing_doc.get('teams', [])
              if t.get('picked')}
    seen = set()
    for t in new_doc_body.get('teams', []):
        seen.add(t.get('team_number'))
        if t.get('team_number') in picked:
            t['picked'] = True
    for tn in picked - seen:
        new_doc_body.setdefault('teams', []).append({
            'team_number': tn, 'ranking': None, 'dnp': False,
            'decline': False, 'notes': '', 'picked': True,
        })
    return new_doc_body


def strip_system(doc):
    return {k: v for k, v in doc.items() if not k.startswith('_')}
