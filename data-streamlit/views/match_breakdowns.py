import streamlit as st
import pandas as pd

from scout import (
    load_matches_data, load_opr_data, load_team_data, get_event_key,
    load_statbot_matches_data, get_secret_key, load_parallel,
    _invalidate_session_cache,
)

def match_breakdowns_page():
    """Match Breakdowns Page"""

    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header('Match Breakdowns')

    matches, team_data = load_parallel(
        (load_matches_data, ek),
        (load_team_data, ek),
    )
    team_names = {row.number: row['name'] for _, row in team_data.iterrows()}

    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 2, 1])
    with col_f1:
        qm_filter = st.checkbox('Quals', True)
    with col_f2:
        po_filter = st.checkbox('Playoffs', True)
    with col_f3:
        team_filter = st.multiselect('Team', sorted(team_data['number'].tolist()),
                                     format_func=lambda t: f"{t} ({team_names.get(t, '')})",
                                     placeholder='Select a team')

    with col_f4:
        if st.button('Refresh'):
            _invalidate_session_cache()
            st.rerun()

    if not team_filter:
        st.info("Select a team to view their match breakdowns.")
        st.stop()

    # Determine if we should highlight a single team
    highlight_team = team_filter[0] if len(team_filter) == 1 else None

    match_types = []
    if qm_filter:
        match_types.append('qm')
    if po_filter:
        match_types.extend(['sf', 'f'])

    oprdata, statbotics = load_parallel(
        (load_opr_data, sk, ek),
        (load_statbot_matches_data, ek),
    )
    has_opr = oprdata is not None and 'totalPoints' in oprdata.columns
    if has_opr:
        opr_lookup = oprdata.set_index('teamNumber')['totalPoints'].to_dict()
    else:
        opr_lookup = {}

    matches = matches[matches['comp_level'].isin(match_types)]
    # Sort: quals first by match_number, then playoffs by set_number
    level_order = {'qm': 0, 'sf': 1, 'f': 2}
    matches = matches.copy()
    matches['_sort'] = matches['comp_level'].map(level_order).fillna(3) * 10000 + \
                        matches['set_number'] * 100 + matches['match_number']
    matches = matches.sort_values(by='_sort').reset_index(drop=True)

    if matches.empty:
        st.info('No match data available yet.')
        return

    # Parse alliance team keys
    n1 = pd.json_normalize(matches['alliances'])
    for color, col_prefix in [('blue', 'blue'), ('red', 'red')]:
        teams_col = n1[f'{color}.team_keys'].apply(
            lambda keys: [int(k.replace('frc', '')) for k in keys] if keys else []
        )
        matches[f'{col_prefix}_teams'] = teams_col

    # Filter by team
    if team_filter:
        mask = matches.apply(
            lambda r: any(t in r['red_teams'] or t in r['blue_teams'] for t in team_filter),
            axis=1
        )
        matches = matches[mask]

    if matches.empty:
        st.info('No matches found for selected filters.')
        return

    # Statbotics predictions (already loaded in parallel above)
    has_statbotics = statbotics is not None and not statbotics.empty
    pred_map = {}
    actual_map = {}
    if has_statbotics:
        for _, sb in statbotics.iterrows():
            mn = sb['match_number']
            if sb.get('pred'):
                pred_map[mn] = sb['pred']
            if sb.get('result'):
                actual_map[mn] = sb['result']

    # Render each match compactly
    for _, match in matches.iterrows():
        mn = int(match['match_number'])
        level = match.get('comp_level', 'qm')
        sn = int(match.get('set_number', 1))
        if level == 'qm':
            label = f"Q{mn}"
        elif level == 'sf':
            label = f"SF{sn}-{mn}"
        elif level == 'f':
            label = f"F{mn}"
        else:
            label = f"{level.upper()}{sn}-{mn}"

        red_teams = match['red_teams']
        blue_teams = match['blue_teams']

        # OPR totals
        red_opr = sum(opr_lookup.get(t, 0) for t in red_teams)
        blue_opr = sum(opr_lookup.get(t, 0) for t in blue_teams)

        # Predictions & actuals
        pred = pred_map.get(mn, {})
        actual = actual_map.get(mn, {})
        red_pred = pred.get('red_score', None)
        blue_pred = pred.get('blue_score', None)
        red_actual = actual.get('red_score', None)
        blue_actual = actual.get('blue_score', None)
        winner = actual.get('winner', None)
        red_win_prob = pred.get('red_win_prob', None)
        pred_winner = pred.get('winner', None)
        match_played = winner is not None

        # Determine if highlighted team's alliance wins/is predicted to win
        highlight_color = None
        team_wins = None
        if highlight_team:
            if highlight_team in red_teams:
                highlight_color = 'red'
            elif highlight_team in blue_teams:
                highlight_color = 'blue'
            if highlight_color:
                if match_played and winner:
                    team_wins = (winner == highlight_color)
                elif pred_winner:
                    team_wins = (pred_winner == highlight_color)

        # Match container
        if match_played:
            if team_wins is True:
                border_icon = '🟢'
            elif team_wins is False:
                border_icon = '🔴'
            else:
                border_icon = ''
        else:
            # Unplayed — show prediction with green/red icons
            if red_win_prob is not None and highlight_color:
                prob = red_win_prob if highlight_color == 'red' else (1 - red_win_prob)
                pct = prob * 100
                icon = '🟢' if pct >= 50 else '🔴'
                border_icon = f'{icon} {pct:.0f}% chance'
            elif red_win_prob is not None:
                fav = 'Red' if red_win_prob > 0.5 else 'Blue'
                fav_pct = max(red_win_prob, 1 - red_win_prob) * 100
                border_icon = f'{fav} {fav_pct:.0f}%'
            else:
                border_icon = ''

        with st.container(border=True):
            # Header row: match label + result indicator
            st.markdown(f"**{label}** {border_icon}")

            # Compact two-column layout
            col_red, col_blue = st.columns(2)

            for col, color, teams, opr_total in [
                (col_red, 'red', red_teams, red_opr),
                (col_blue, 'blue', blue_teams, blue_opr),
            ]:
                with col:
                    is_winner = (winner == color) if winner else False
                    win_marker = ' ★' if is_winner else ''
                    color_label = color.capitalize()

                    # Team list with highlighting
                    team_strs = []
                    for t in teams:
                        name = team_names.get(t, '')
                        t_opr = opr_lookup.get(t, None)
                        opr_str = f" — {t_opr:.0f} OPR" if t_opr else ""
                        if highlight_team and t == highlight_team:
                            team_strs.append(f"**`{t}`** ({name}){opr_str}")
                        else:
                            link = f"/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={t}"
                            team_strs.append(f"[{t}]({link}) ({name}){opr_str}")

                    # Build compact info block
                    lines = [f"**{color_label}{win_marker}**"]
                    for ts in team_strs:
                        lines.append(f"- {ts}")

                    info_parts = []
                    if has_opr:
                        info_parts.append(f"OPR: {opr_total:.0f}")
                    score_parts = []
                    if red_pred is not None:
                        s_pred = red_pred if color == 'red' else blue_pred
                        score_parts.append(f"Pred: {s_pred:.0f}")
                    if red_actual is not None:
                        s_actual = red_actual if color == 'red' else blue_actual
                        if s_actual >= 0:
                            score_parts.append(f"**Actual: {s_actual:.0f}**")
                    if score_parts:
                        info_parts.extend(score_parts)

                    if info_parts:
                        lines.append(" | ".join(info_parts))

                    st.markdown("  \n".join(lines))
