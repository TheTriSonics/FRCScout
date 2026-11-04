"""What the 2026 (REBUILT) scouting fields mean.

Mirrors ScoutStats.defs in RebuiltScouting lib/analytics/scout_stats.dart so
the bot's averages match the app. For a new season, copy this file and
describe the new form; the tools read it, they don't hard-code fields.
"""

GAME_NAME = 'REBUILT (2026)'

GAME_NOTES = """\
REBUILT (FRC 2026): robots score FUEL into their alliance HUB and climb the
TOWER in auto and endgame. In teleop each alliance's hub alternates between
ACTIVE (fuel scored counts) and INACTIVE (robots collect fuel, pass it or play
defense). Official score breakdowns count hub fuel per period (auto,
transition, shift1-4, endgame) plus tower points and fouls. Ranking points
come from wins plus bonus RPs named energized, supercharged and traversal.
Scouts record shooting ACCURACY ratings and VOLLEYS, not exact fuel counts;
exact fuel counts come only from official breakdowns and OPR."""

# (key, label, section, binary). auto_climbed / endgame_climbed are derived
# here (tower level > 0) and aren't in the app's list. Binary stats are 0/1 per match; their mean
# is the share of scouted matches where it happened.
STATS = [
    ('auto_fuel_accuracy', 'Auto shooting accuracy %', 'Auto', False),
    ('auto_tower_level', 'Auto tower level', 'Auto', False),
    ('auto_middle_pickup', 'Auto middle pickups', 'Auto', False),
    ('auto_human_station_pickup', 'Auto human station pickups', 'Auto', False),
    ('auto_climbed', 'Climbed in auto (any level)', 'Auto', True),
    ('win_auto', 'Won auto', 'Auto', True),
    ('auto_did_nothing', 'Did nothing in auto', 'Auto', True),
    ('auto_depot_pickup', 'Auto depot pickup', 'Auto', True),
    ('teleop_volleys', 'Teleop volleys', 'Teleop', False),
    ('teleop_volley_accuracy', 'Teleop volley accuracy %', 'Teleop', False),
    ('teleop_fuel_accuracy', 'Teleop shooting accuracy %', 'Teleop', False),
    ('hopper_size', 'Hopper size', 'Teleop', False),
    ('teleop_shoot_on_fly', 'Shoots on the fly', 'Teleop', True),
    ('teleop_inactive_scored_fuel', 'Scores while inactive', 'Teleop', True),
    ('teleop_inactive_collected_fuel', 'Collects while inactive', 'Teleop', True),
    ('teleop_inactive_collected_fuel_push', 'Inactive: push', 'Teleop', True),
    ('teleop_inactive_collected_fuel_lobby', 'Inactive: lobby', 'Teleop', True),
    ('teleop_inactive_collected_fuel_refill', 'Inactive: refill', 'Teleop', True),
    ('teleop_active_defense_penalties', 'Defense penalties (active)', 'Teleop', True),
    ('teleop_inactive_defense_penalties', 'Defense penalties (inactive)', 'Teleop', True),
    ('endgame_tower_level', 'Endgame tower level', 'Endgame', False),
    ('endgame_climbed', 'Climbed in endgame (any level)', 'Endgame', True),
    ('endgame_fuel_accuracy', 'Endgame shooting accuracy %', 'Endgame', False),
    ('endgame_carried', 'Carried in endgame', 'Endgame', True),
    ('endgame_thumbs_up', 'Scout thumbs up', 'Endgame', True),
    ('fuel_ground_pickup', 'Ground pickup', 'General', True),
    ('fuel_human_pickup', 'Human player pickup', 'General', True),
    ('fuel_depot_pickup', 'Depot pickup', 'General', True),
]
STAT_KEYS = [s[0] for s in STATS]
STAT_LABEL = {s[0]: s[1] for s in STATS}

TEXT_FIELDS = ['auto_notes', 'match_notes', 'teleop_active_defense_quality',
               'teleop_inactive_defense_quality']

# OPR columns worth offering (GetOPRData has more; these are the useful ones).
OPR_COLUMNS = {
    'totalPoints': 'OPR total points',
    'totalAutoPoints': 'OPR auto points',
    'totalTeleopPoints': 'OPR teleop points',
    'hubScore_totalCount': 'OPR hub fuel (all periods)',
    'hubScore_autoCount': 'OPR hub fuel in auto',
    'hubScore_teleopCount': 'OPR hub fuel in teleop',
    'hubScore_endgameCount': 'OPR hub fuel in endgame',
    'totalTowerPoints': 'OPR tower points',
    'autoTowerPoints': 'OPR auto tower points',
    'endGameTowerPoints': 'OPR endgame tower points',
    'foulPoints': 'OPR foul points drawn',
    'rp': 'OPR ranking points',
}

PIT_SKIP = {'id', 'secret_team_key', 'event_key', 'image_names', '_rid', '_self',
            '_etag', '_attachments', '_ts', 'timestamp'}


def row_stats(row):
    """Numeric stats for one GetResults row (bools -> 0/1, volleys derived)."""
    out = {}
    for key in STAT_KEYS:
        v = row.get(key)
        if isinstance(v, bool):
            out[key] = 1.0 if v else 0.0
        elif isinstance(v, (int, float)):
            out[key] = float(v)
    for lvl, flag in (('auto_tower_level', 'auto_climbed'), ('endgame_tower_level', 'endgame_climbed')):
        if lvl in out:
            out[flag] = 1.0 if out[lvl] > 0 else 0.0
    acc = [a for a in row.get('volley_accuracy_list') or [] if isinstance(a, (int, float))]
    out['teleop_volleys'] = float(len(acc))
    if acc:
        out['teleop_volley_accuracy'] = sum(acc) / len(acc)
    else:
        out.pop('teleop_volley_accuracy', None)
    return out
