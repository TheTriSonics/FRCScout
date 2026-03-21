import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from scout import (
    load_event_data, load_matches_data, load_team_data,
    get_event_key, get_secret_key, pretty_name,
)


def _extract_match_actuals(matches):
    """Extract per-match, per-alliance actual scores from TBA data."""
    rows = []
    for _, match in matches.iterrows():
        if match.get('comp_level') != 'qm':
            continue
        mn = match['match_number']
        sb = match.get('score_breakdown')
        alliances = match.get('alliances')
        if sb is None or alliances is None:
            continue
        for color in ['blue', 'red']:
            if color not in sb or sb[color] is None:
                continue
            breakdown = sb[color]
            hub = breakdown.get('hubScore', {})
            team_keys = alliances[color].get('team_keys', [])
            teams = [int(k.replace('frc', '')) for k in team_keys]
            rows.append({
                'match_number': mn,
                'alliance': color,
                'teams': teams,
                'tba_auto_fuel': hub.get('autoCount', 0),
                'tba_teleop_fuel': hub.get('teleopCount', 0),
                'tba_endgame_fuel': hub.get('endgameCount', 0),
                'tba_total_fuel': hub.get('totalCount', 0),
                'tba_total_points': breakdown.get('totalPoints', 0),
                'tba_minor_fouls': breakdown.get('minorFoulCount', 0),
                'tba_major_fouls': breakdown.get('majorFoulCount', 0),
                'tba_foul_points': breakdown.get('foulPoints', 0),
            })
    return pd.DataFrame(rows)


def _compute_scouted_alliance_totals(scouted_data, match_actuals):
    """For each match+alliance, sum up scouted values for the 3 teams."""
    rows = []
    for _, actual in match_actuals.iterrows():
        mn = actual['match_number']
        teams = actual['teams']
        alliance = actual['alliance']

        team_data = scouted_data[
            (scouted_data['match_number'] == mn) &
            (scouted_data['team_number'].isin(teams))
        ]

        if len(team_data) == 0:
            continue

        teams_scouted = len(team_data)

        # Compute fuel made from scored * accuracy
        auto_fuel = 0
        teleop_fuel = 0
        endgame_fuel = 0
        penalties = 0

        for _, t in team_data.iterrows():
            auto_s = t.get('auto_fuel_scored', 0) or 0
            auto_a = t.get('auto_fuel_accuracy', 0) or 0
            auto_fuel += round(auto_s * auto_a / 100)

            teleop_s = t.get('teleop_fuel_scored', 0) or 0
            teleop_a = t.get('teleop_fuel_accuracy', 0) or 0
            teleop_fuel += round(teleop_s * teleop_a / 100)

            endgame_s = t.get('endgame_fuel_scored', 0) or 0
            endgame_a = t.get('endgame_fuel_accuracy', 0) or 0
            endgame_fuel += round(endgame_s * endgame_a / 100)

            penalties += (t.get('teleop_active_defense_penalties', 0) or 0)
            penalties += (t.get('teleop_inactive_defense_penalties', 0) or 0)

        rows.append({
            'match_number': mn,
            'alliance': alliance,
            'teams_scouted': teams_scouted,
            'scouted_auto_fuel': auto_fuel,
            'scouted_teleop_fuel': teleop_fuel,
            'scouted_endgame_fuel': endgame_fuel,
            'scouted_total_fuel': auto_fuel + teleop_fuel + endgame_fuel,
            'scouted_penalties': penalties,
        })
    return pd.DataFrame(rows)


def _accuracy_pct(scouted, actual, tolerance_pct=0.20):
    """Compute accuracy as 0-100%. 100% if within tolerance, degrades linearly."""
    if actual == 0 and scouted == 0:
        return 100.0
    if actual == 0:
        return max(0, 100 - abs(scouted) * 10)
    error_ratio = abs(scouted - actual) / max(actual, 1)
    if error_ratio <= tolerance_pct:
        return 100.0
    return max(0, 100 * (1 - (error_ratio - tolerance_pct) / (1 - tolerance_pct)))


def scouting_accuracy_page():
    """Scouting Accuracy — compare scouted data against TBA actuals."""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Scouting Accuracy")
    with st.expander("Instructions"):
        st.write("""
        Compares our scouted data against official TBA match results.
        For each match, we sum what our scouts recorded for each alliance
        and compare it to TBA's official scoring breakdown.

        **Match Accuracy** shows how close we were per match.
        **Team Accuracy** averages the accuracy of all matches each team
        appeared in — if a team was in poorly-scouted matches, their
        accuracy score will be lower.

        Penalty flags show matches where TBA recorded fouls but our
        scouts didn't (or vice versa).
        """)

    scouted_data = load_event_data(sk, ek)
    matches = load_matches_data(ek)
    td = load_team_data(ek)
    team_names = {row.number: row['name'] for _, row in td.iterrows()}

    if len(scouted_data.index) == 0:
        st.warning("No scouting data available.")
        st.stop()
    if len(matches.index) == 0:
        st.warning("No TBA match data available yet.")
        st.stop()

    # Extract TBA actuals and compute scouted totals
    match_actuals = _extract_match_actuals(matches)
    if len(match_actuals) == 0:
        st.warning("No qualifying match data with score breakdowns yet.")
        st.stop()

    scouted_totals = _compute_scouted_alliance_totals(scouted_data, match_actuals)
    if len(scouted_totals) == 0:
        st.warning("No scouted matches overlap with TBA data.")
        st.stop()

    # Merge scouted with actuals
    merged = match_actuals.merge(scouted_totals, on=['match_number', 'alliance'], how='inner')

    # --- Per-match accuracy ---
    st.subheader("Match Accuracy")

    match_rows = []
    for _, row in merged.iterrows():
        auto_acc = _accuracy_pct(row['scouted_auto_fuel'], row['tba_auto_fuel'])
        teleop_acc = _accuracy_pct(row['scouted_teleop_fuel'], row['tba_teleop_fuel'])
        endgame_acc = _accuracy_pct(row['scouted_endgame_fuel'], row['tba_endgame_fuel'])
        total_acc = _accuracy_pct(row['scouted_total_fuel'], row['tba_total_fuel'])

        # Penalty check
        tba_fouls = row['tba_minor_fouls'] + row['tba_major_fouls']
        scouted_fouls = row['scouted_penalties']
        penalty_flag = ''
        if tba_fouls > 0 and scouted_fouls == 0:
            penalty_flag = 'Missed foul'
        elif tba_fouls == 0 and scouted_fouls > 0:
            penalty_flag = 'False foul'
        elif tba_fouls > 0 and scouted_fouls > 0 and abs(tba_fouls - scouted_fouls) > 1:
            penalty_flag = 'Foul count off'

        overall = (auto_acc + teleop_acc + endgame_acc) / 3

        match_rows.append({
            'Match': int(row['match_number']),
            'Alliance': row['alliance'].capitalize(),
            'Scouted': int(row['teams_scouted']),
            'Auto': f"{int(row['scouted_auto_fuel'])}/{int(row['tba_auto_fuel'])}",
            'Auto %': round(auto_acc),
            'Teleop': f"{int(row['scouted_teleop_fuel'])}/{int(row['tba_teleop_fuel'])}",
            'Teleop %': round(teleop_acc),
            'Endgame': f"{int(row['scouted_endgame_fuel'])}/{int(row['tba_endgame_fuel'])}",
            'Endgame %': round(endgame_acc),
            'Overall %': round(overall),
            'Penalties': penalty_flag if penalty_flag else 'OK',
            # Hidden for chart
            '_overall': overall,
            '_match': int(row['match_number']),
            '_alliance': row['alliance'],
            '_teams': row['teams'],
        })

    match_df = pd.DataFrame(match_rows)

    # Overall accuracy chart
    chart_data = match_df[['_match', '_alliance', '_overall']].copy()
    chart_data.columns = ['Match', 'Alliance', 'Accuracy']
    chart_data['Match'] = chart_data['Match'].astype(str)

    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Match:N', sort=None, title='Match'),
        y=alt.Y('Accuracy:Q', title='Accuracy %', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('Alliance:N',
                        scale=alt.Scale(domain=['blue', 'red'],
                                        range=['#4e79a7', '#e15759'])),
        xOffset='Alliance:N',
        tooltip=['Match', 'Alliance', alt.Tooltip('Accuracy:Q', format='.0f')],
    ).properties(height=300)

    st.altair_chart(chart, use_container_width=True)

    # Table
    display_cols = ['Match', 'Alliance', 'Scouted', 'Auto', 'Auto %',
                    'Teleop', 'Teleop %', 'Endgame', 'Endgame %',
                    'Overall %', 'Penalties']
    display_df = match_df[display_cols].copy()

    def _style_row(val):
        if isinstance(val, (int, float)):
            if val >= 80:
                return 'color: #59a14f'
            elif val >= 50:
                return 'color: #f28e2b'
            else:
                return 'color: #e15759'
        return ''

    def _penalty_style(val):
        if val in ('Missed foul', 'False foul', 'Foul count off'):
            return 'color: #e15759; font-weight: bold'
        return ''

    pct_cols = ['Auto %', 'Teleop %', 'Endgame %', 'Overall %']
    styled = (display_df.style
              .map(_style_row, subset=pct_cols)
              .map(_penalty_style, subset=['Penalties']))
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # --- Per-team accuracy ---
    st.subheader("Team Accuracy")
    st.write("Each team's score is the average accuracy across all matches they appeared in.")

    team_scores = {}
    for _, row in match_df.iterrows():
        for tn in row['_teams']:
            if tn not in team_scores:
                team_scores[tn] = []
            team_scores[tn].append(row['_overall'])

    team_rows = []
    for tn, scores in sorted(team_scores.items()):
        avg = np.mean(scores)
        team_rows.append({
            'Team': f"{tn} ({team_names.get(tn, '')})",
            'Matches': len(scores),
            'Avg Accuracy': round(avg, 1),
            '_team_num': tn,
            '_avg': avg,
        })

    team_df = pd.DataFrame(team_rows).sort_values('Avg Accuracy', ascending=False)

    # Chart
    team_chart = alt.Chart(team_df).mark_bar().encode(
        x=alt.X('Team:N', sort=team_df['Team'].tolist(), title=''),
        y=alt.Y('Avg Accuracy:Q', title='Avg Accuracy %',
                scale=alt.Scale(domain=[0, 100])),
        color=alt.condition(
            alt.datum['Avg Accuracy'] >= 70,
            alt.value('#59a14f'),
            alt.condition(
                alt.datum['Avg Accuracy'] >= 40,
                alt.value('#f28e2b'),
                alt.value('#e15759')
            )
        ),
        tooltip=['Team', 'Matches', alt.Tooltip('Avg Accuracy:Q', format='.1f')],
    ).properties(height=350)
    st.altair_chart(team_chart, use_container_width=True)

    # Summary stats
    overall_avg = match_df['_overall'].mean()
    st.metric("Event Scouting Accuracy", f"{overall_avg:.0f}%")

    # Penalty summary
    penalty_issues = match_df[match_df['Penalties'] != 'OK']
    if len(penalty_issues) > 0:
        st.subheader("Penalty Flags")
        st.dataframe(
            penalty_issues[['Match', 'Alliance', 'Penalties']],
            hide_index=True, use_container_width=True,
        )
