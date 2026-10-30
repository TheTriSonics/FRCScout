"""Per-person pick lists ("votes") in the PickVotes container.

Partitioned by event_key. For each secret key + event there is:

  - one list doc per voter, using the same team entries as pick_list:
      {'id': '{sk}_{ek}_list_{voter_key}', 'kind': 'list', 'secret_key',
       'event_key', 'voter', 'teams': [{'team_number', 'ranking', 'dnp',
       'notes', ...}], 'version', 'updated_by', 'updated_at'}
  - one shared doc for teams taken by other alliances during selection:
      {'id': '{sk}_{ek}_taken', 'kind': 'taken', 'secret_key', 'event_key',
       'teams': [team_number, ...], 'version', 'updated_by', 'updated_at'}

People only write their own list, so lists never contend with each other.
Totals and consensus are computed by the app so the scoring can change
without an API deploy.

Live updates: after each write the API pushes the saved doc to a Web PubSub
group for that secret key + event ({'type': 'ballot'|'taken', 'doc': ...}).
"""

import hashlib
import re

import pick_list

VOTE_STATUSES = ('dnp', 'unranked')


def voter_key(voter):
    key = re.sub(r'[^a-z0-9]+', '-', (voter or '').strip().lower()).strip('-')
    if not key:
        raise ValueError('voter is required')
    return key


def list_id(secret_key, event_key, voter):
    return f'{secret_key}_{event_key}_list_{voter_key(voter)}'


def taken_id(secret_key, event_key):
    return f'{secret_key}_{event_key}_taken'


def group_name(secret_key, event_key):
    """Web PubSub group for one secret key + event. Hashed so the secret key
    never appears in group names or tokens."""
    digest = hashlib.sha256(f'{secret_key}|{event_key}'.encode()).hexdigest()
    return f'pickboard_{digest[:32]}'


def new_list(secret_key, event_key, voter):
    return {
        'id': list_id(secret_key, event_key, voter),
        'kind': 'list',
        'secret_key': secret_key,
        'event_key': event_key,
        'voter': voter.strip(),
        'teams': [],
        'version': 0,
    }


def new_taken(secret_key, event_key):
    return {
        'id': taken_id(secret_key, event_key),
        'kind': 'taken',
        'secret_key': secret_key,
        'event_key': event_key,
        'teams': [],
        'version': 0,
    }


def apply_vote(doc, voter, team_number, position=None, status=None,
               notes=None):
    """Apply one team's change to a voter's list in place. Same ordering
    rules as the shared pick list, minus Decline and the taken flag."""
    if status is not None and status not in VOTE_STATUSES:
        raise ValueError(f'status must be one of {VOTE_STATUSES}')
    doc['voter'] = voter.strip()
    return pick_list.apply_update(doc, team_number, position=position,
                                  status=status, notes=notes)


def set_taken(doc, team_number, taken):
    teams = set(doc.get('teams', []))
    if taken:
        teams.add(int(team_number))
    else:
        teams.discard(int(team_number))
    doc['teams'] = sorted(teams)
    return doc


def board(docs):
    """Shape the docs for one secret key + event into a GetPickVotes body."""
    lists = sorted((pick_list.strip_system(d) for d in docs
                    if d.get('kind') == 'list'),
                   key=lambda d: d.get('voter', '').lower())
    taken = next((d for d in docs if d.get('kind') == 'taken'), None)
    return {
        'lists': lists,
        'taken': pick_list.strip_system(taken) if taken else None,
    }
