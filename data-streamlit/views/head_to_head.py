import pandas as pd
import streamlit as st
import altair as alt

from scout import (
    load_event_data, load_team_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name,
)


def head_to_head_page():
    """Head-to-Head Comparison page"""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Head-to-Head Comparison")
    with st.expander("Instructions"):
        st.write("""
        Pick 2-3 teams to compare side by side. Each attribute is shown as
        a grouped bar chart so you can see exactly where one team edges out
        another. Useful when deciding between candidates for an alliance pick.
        """)

    scouted_data = load_event_data(sk, ek)
    if scouted_data.empty:
        st.warning("No scouting data available.")
        st.stop()

    td = load_team_data(ek)
    all_teams = [(row.number, row['name']) for _, row in td.iterrows()]
    scouted_teams = sorted(scouted_data['team_number'].unique())
    # Filter to only teams that have scouting data
    available = [t for t in all_teams if t[0] in scouted_teams]

    selected = st.multiselect(
        "Select teams to compare",
        available,
        max_selections=5,
        format_func=lambda x: f'{x[0]} ({x[1]})',
        key='h2h_teams',
    )

    if len(selected) < 2:
        st.info("Select at least 2 teams to compare.")
        return

    team_nums = [t[0] for t in selected]
    team_names = {t[0]: t[1] for t in selected}

    # Compute averages for selected teams
    df = scouted_data[scouted_data['team_number'].isin(team_nums)]
    avgs = df.groupby('team_number').mean(numeric_only=True).reset_index()
    avgs['team_label'] = avgs['team_number'].map(
        lambda t: f"{t} ({team_names.get(t, '')})"
    )

    # Match counts for context
    match_counts = df.groupby('team_number').size().reset_index(name='matches')
    counts_md = " | ".join(
        f"**{int(r.team_number)}**: {r.matches} matches"
        for _, r in match_counts.iterrows()
    )
    st.caption(counts_md)

    chart_cols = [c for c in avgs.select_dtypes(include='number').columns
                  if c not in SKIP_COLS and c != 'team_number' and c != 'match_number']

    for section_name, section_filter in SECTIONS:
        section_cols = [c for c in chart_cols if section_filter(c)]
        if not section_cols:
            continue
        with st.expander(section_name, expanded=True):
            for col in sorted(section_cols):
                chart_df = avgs[['team_label', col]].copy()
                chart_df = chart_df.sort_values(col, ascending=False)

                if col in BINARY_COLS:
                    # For binary cols, show total count (sum) instead of avg
                    sums = df.groupby('team_number')[col].sum().reset_index()
                    totals = df.groupby('team_number')[col].count().reset_index()
                    totals.columns = ['team_number', 'total']
                    sums = sums.merge(totals, on='team_number')
                    sums['yes'] = sums[col]
                    sums['no'] = sums['total'] - sums['yes']
                    sums['team_label'] = sums['team_number'].map(
                        lambda t: f"{t} ({team_names.get(t, '')})"
                    )
                    melted = sums.melt(
                        id_vars='team_label', value_vars=['yes', 'no'],
                        var_name='result', value_name='matches'
                    )
                    chart = alt.Chart(melted).mark_bar().encode(
                        x=alt.X('team_label:N', title='', sort=sums.sort_values('yes', ascending=False)['team_label'].tolist()),
                        y=alt.Y('matches:Q', title=pretty_name(col)),
                        color=alt.Color('result:N',
                                        scale=alt.Scale(domain=['yes', 'no'],
                                                        range=['#59a14f', '#e15759']),
                                        title=''),
                        tooltip=['team_label', 'result', 'matches'],
                        order=alt.Order('result:N', sort='descending'),
                    ).properties(height=250, title=pretty_name(col))
                else:
                    chart = alt.Chart(chart_df).mark_bar().encode(
                        x=alt.X('team_label:N', title='',
                                sort=chart_df['team_label'].tolist()),
                        y=alt.Y(f'{col}:Q', title='Avg per Match'),
                        color=alt.Color('team_label:N', legend=None),
                        tooltip=['team_label', alt.Tooltip(f'{col}:Q', format='.1f')],
                    ).properties(height=250, title=pretty_name(col))
                st.altair_chart(chart, width='stretch')
