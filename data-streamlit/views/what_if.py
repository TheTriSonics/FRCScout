import pandas as pd
import streamlit as st
import altair as alt

from scout import (
    load_team_data, load_event_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name,
)


def what_if_page():
    """Alliance Strength Calculator page"""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header('Alliance Builder')
    with st.expander('Instructions'):
        st.write("""
        Draft teams into alliances to see combined strengths, weaknesses,
        and gaps. Build up to 8 alliances of 3 teams each. Each alliance
        shows the combined average performance and highlights where the
        alliance is strong or has holes to fill.
        """)

    td = load_team_data(ek)
    scouted_data = load_event_data(sk, ek)
    if len(scouted_data.index) == 0:
        st.warning("No scouting data available.")
        st.stop()

    all_teams = [(row.number, row['name']) for _, row in td.iterrows()]
    scouted_teams = sorted(scouted_data['team_number'].unique())
    available = [t for t in all_teams if t[0] in scouted_teams]

    # Per-team averages for all scouted teams
    team_avgs = scouted_data.groupby('team_number').mean(numeric_only=True)
    chart_cols = [c for c in team_avgs.select_dtypes(include='number').columns
                  if c not in SKIP_COLS and c != 'match_number']

    # Event-wide averages for comparison
    event_avg = team_avgs[chart_cols].mean()

    alliances = {}

    def _used_teams():
        used = []
        for i in range(8):
            key = f'alliance_{i}_select'
            if key in st.session_state:
                used += st.session_state[key]
        return used

    def _available_teams(current_key):
        used = _used_teams()
        current = st.session_state.get(current_key, [])
        return [t for t in available if t not in used or t in current]

    for x in range(8):
        select_key = f'alliance_{x}_select'
        with st.expander(f'Alliance {x+1}', expanded=(x < 2)):
            alliances[x] = st.multiselect(
                'Members', _available_teams(select_key),
                placeholder='Choose up to 3 teams',
                max_selections=3,
                format_func=lambda t: f'{t[0]} ({t[1]})',
                key=select_key,
            )

            if not alliances[x]:
                st.info("Select teams to see alliance analysis.")
                continue

            team_nums = [t[0] for t in alliances[x]]

            # Get averages for alliance members
            alliance_avgs = team_avgs.loc[team_avgs.index.isin(team_nums), chart_cols]
            if alliance_avgs.empty:
                st.warning("No scouting data for selected teams.")
                continue

            # Combined alliance total (sum of averages = expected alliance output)
            alliance_total = alliance_avgs.sum()

            # --- Per-member breakdown ---
            member_df = alliance_avgs.copy()
            member_df.index = [f"{t} ({next((n for tn, n in all_teams if tn == t), 'N/A')})"
                               for t in member_df.index]

            for section_name, section_test in SECTIONS:
                sec_cols = [c for c in chart_cols if section_test(c) and c not in BINARY_COLS]
                if not sec_cols:
                    continue
                st.markdown(f"**{section_name}**")

                # Stacked bar: each team's contribution to alliance total
                stack_df = member_df[sec_cols].T
                stack_df.index.name = 'attribute'
                stack_df = stack_df.reset_index()
                melted = stack_df.melt(id_vars='attribute', var_name='team', value_name='value')

                chart = alt.Chart(melted).mark_bar().encode(
                    x=alt.X('attribute:N', title='', sort=sec_cols,
                            axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('value:Q', title='Combined Avg'),
                    color=alt.Color('team:N', title='Team'),
                    tooltip=['team', 'attribute', alt.Tooltip('value:Q', format='.1f')],
                    order=alt.Order('team:N'),
                ).properties(height=300)
                st.altair_chart(chart, use_container_width=True)

            # --- Strengths & Gaps ---
            st.markdown("**Strengths & Gaps** (vs event average)")
            comparison = pd.DataFrame({
                'attribute': [pretty_name(c) for c in chart_cols if c not in BINARY_COLS],
                'alliance': [alliance_total[c] for c in chart_cols if c not in BINARY_COLS],
                'event_avg_x3': [event_avg[c] * len(team_nums) for c in chart_cols if c not in BINARY_COLS],
            })
            comparison['diff'] = comparison['alliance'] - comparison['event_avg_x3']
            comparison['pct'] = (comparison['diff'] / (comparison['event_avg_x3'] + 1e-10) * 100).round(0)
            comparison = comparison.sort_values('diff', ascending=False)

            diff_chart = alt.Chart(comparison).mark_bar().encode(
                y=alt.Y('attribute:N', sort=comparison['attribute'].tolist(), title=''),
                x=alt.X('diff:Q', title='Difference vs Event Avg'),
                color=alt.condition(
                    alt.datum.diff > 0,
                    alt.value('#59a14f'),
                    alt.value('#e15759')
                ),
                tooltip=['attribute',
                         alt.Tooltip('alliance:Q', format='.1f', title='Alliance'),
                         alt.Tooltip('event_avg_x3:Q', format='.1f', title='Event Avg (scaled)'),
                         alt.Tooltip('pct:Q', format='.0f', title='% Diff')],
            ).properties(height=max(200, len(comparison) * 25))
            st.altair_chart(diff_chart, use_container_width=True)

            # Binary capabilities coverage
            bin_cols = [c for c in chart_cols if c in BINARY_COLS]
            if bin_cols:
                st.markdown("**Capability Coverage**")
                cap_rows = []
                for col in sorted(bin_cols):
                    team_caps = {}
                    for tn in team_nums:
                        if tn in team_avgs.index:
                            team_caps[str(tn)] = 'Yes' if team_avgs.loc[tn, col] > 0.5 else 'No'
                    any_yes = any(v == 'Yes' for v in team_caps.values())
                    cap_rows.append({
                        'Capability': pretty_name(col),
                        'Covered': 'Yes' if any_yes else 'MISSING',
                        **team_caps,
                    })
                cap_df = pd.DataFrame(cap_rows).set_index('Capability')

                def _highlight_missing(val):
                    if val == 'MISSING':
                        return 'color: #e15759; font-weight: bold'
                    elif val == 'Yes':
                        return 'color: #59a14f'
                    elif val == 'No':
                        return 'color: #999'
                    return ''

                st.dataframe(cap_df.style.map(_highlight_missing), use_container_width=True)

    # --- Alliance vs Alliance Comparison ---
    filled = {k: v for k, v in alliances.items() if v}
    if len(filled) >= 2:
        st.header("Alliance vs Alliance")
        alliance_labels = [f"Alliance {k+1}" for k in filled]
        compare_left, compare_right = st.columns(2)
        with compare_left:
            a1_key = st.selectbox("Alliance A", list(filled.keys()),
                                  format_func=lambda k: f"Alliance {k+1}",
                                  key='compare_a1')
        with compare_right:
            other_keys = [k for k in filled if k != a1_key]
            a2_key = st.selectbox("Alliance B", other_keys,
                                  format_func=lambda k: f"Alliance {k+1}",
                                  key='compare_a2') if other_keys else None

        if a2_key is not None:
            a1_nums = [t[0] for t in filled[a1_key]]
            a2_nums = [t[0] for t in filled[a2_key]]
            a1_totals = team_avgs.loc[team_avgs.index.isin(a1_nums), chart_cols].sum()
            a2_totals = team_avgs.loc[team_avgs.index.isin(a2_nums), chart_cols].sum()

            num_cols = [c for c in chart_cols if c not in BINARY_COLS]
            comp_data = pd.DataFrame({
                'Attribute': [pretty_name(c) for c in num_cols],
                f'Alliance {a1_key+1}': [a1_totals[c] for c in num_cols],
                f'Alliance {a2_key+1}': [a2_totals[c] for c in num_cols],
            })
            melted = comp_data.melt(id_vars='Attribute', var_name='Alliance', value_name='Value')
            chart = alt.Chart(melted).mark_bar().encode(
                x=alt.X('Attribute:N', title='', axis=alt.Axis(labelAngle=-45)),
                y=alt.Y('Value:Q', title='Combined Avg'),
                color=alt.Color('Alliance:N', title=''),
                xOffset='Alliance:N',
                tooltip=['Alliance', 'Attribute', alt.Tooltip('Value:Q', format='.1f')],
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)
