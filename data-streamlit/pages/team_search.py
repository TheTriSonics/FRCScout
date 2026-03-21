import pandas as pd
import streamlit as st
import altair as alt

from scout import (
    load_event_data, get_event_key, get_secret_key,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name,
)


def _binary_stacked_chart(df, col):
    """Stacked bar chart for binary columns: Yes vs No per team, sorted by Yes count."""
    grouped = df.groupby('team_number')[col].agg(['sum', 'count']).reset_index()
    grouped.columns = ['team_number', 'yes', 'total']
    grouped['no'] = grouped['total'] - grouped['yes']
    grouped['team_number'] = grouped['team_number'].astype(str)
    grouped = grouped.sort_values('yes', ascending=False)

    melted = grouped.melt(
        id_vars='team_number', value_vars=['yes', 'no'],
        var_name='result', value_name='matches'
    )

    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X('team_number:N', sort=grouped['team_number'].tolist(),
                title='Team'),
        y=alt.Y('matches:Q', title='Matches'),
        color=alt.Color('result:N',
                        scale=alt.Scale(domain=['yes', 'no'],
                                        range=['#59a14f', '#e15759']),
                        title='Result'),
        tooltip=['team_number', 'result', 'matches'],
        order=alt.Order('result:N', sort='descending'),
    ).properties(height=300)
    return chart


def _numeric_bar_chart(df, col):
    """Horizontal bar chart for numeric columns: average per team, sorted descending."""
    grouped = df.groupby('team_number')[col].mean().reset_index()
    grouped.columns = ['team_number', 'avg']
    grouped['team_number'] = grouped['team_number'].astype(str)
    grouped = grouped.sort_values('avg', ascending=False)

    chart = alt.Chart(grouped).mark_bar().encode(
        x=alt.X('team_number:N', sort=grouped['team_number'].tolist(),
                title='Team'),
        y=alt.Y('avg:Q', title='Avg per Match'),
        tooltip=['team_number', alt.Tooltip('avg:Q', format='.1f')],
    ).properties(height=300)
    return chart


def team_search_page():
    """Team Search / Attribute Rankings page"""
    sk = get_secret_key()
    ek = get_event_key()

    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    st.header("Team Search & Rankings")
    with st.expander('Instructions'):
        st.write("""
        Every scouted attribute is shown as a ranked chart so you can quickly
        see which teams lead in each category. Use the filters below to narrow
        results to teams with specific capabilities.

        **Binary attributes** (yes/no per match) are shown as stacked bar
        charts — green is "yes", red is "no". A shorter bar means fewer
        scouted matches for that team.

        **Numeric attributes** are shown as average-per-match bar charts,
        sorted best-to-worst.
        """)

    scouted_data = load_event_data(sk, ek)
    if len(scouted_data.index) == 0:
        st.warning("No scouting data available.")
        st.stop()

    # --- Filters ---
    # Build per-team averages/sums for filtering
    team_avgs = scouted_data.groupby('team_number').mean(numeric_only=True)

    # Collect all filterable columns
    filter_numeric = []
    filter_binary = []
    for c in sorted(scouted_data.select_dtypes(include='number').columns):
        if c in SKIP_COLS or c == 'team_number' or c == 'match_number':
            continue
        if c in BINARY_COLS:
            filter_binary.append(c)
        else:
            filter_numeric.append(c)

    # Build filters organized by section
    active_binary_filters = []
    active_numeric_filters = {}

    for section_name, section_test in SECTIONS:
        sec_binary = [c for c in filter_binary if section_test(c)]
        sec_numeric = [c for c in filter_numeric if section_test(c)]
        if not sec_binary and not sec_numeric:
            continue
        with st.expander(section_name):
            # Binary filters as checkboxes in columns
            if sec_binary:
                cols = st.columns(min(len(sec_binary), 4))
                for i, col_name in enumerate(sec_binary):
                    with cols[i % len(cols)]:
                        if st.checkbox(pretty_name(col_name), key=f'filter_bin_{col_name}'):
                            active_binary_filters.append(col_name)

            # Numeric filters as number inputs in columns
            if sec_numeric:
                cols = st.columns(min(len(sec_numeric), 3))
                for i, col_name in enumerate(sec_numeric):
                    with cols[i % len(cols)]:
                        max_val = int(team_avgs[col_name].max()) if col_name in team_avgs.columns else 0
                        val = st.number_input(
                            f"{pretty_name(col_name)} ≥",
                            min_value=0,
                            max_value=max_val,
                            value=0,
                            step=1,
                            key=f'filter_num_{col_name}',
                        )
                        if val > 0:
                            active_numeric_filters[col_name] = val

    # Apply all filters
    matching_teams = set(team_avgs.index)

    # Binary: team must have at least one "yes" across all matches
    for col_name in active_binary_filters:
        team_sums = scouted_data.groupby('team_number')[col_name].sum()
        matching_teams &= set(team_sums[team_sums > 0].index)

    # Numeric: team average must be >= threshold
    for col_name, threshold in active_numeric_filters.items():
        matching_teams &= set(team_avgs[team_avgs[col_name] >= threshold].index)

    has_filters = len(active_binary_filters) > 0 or len(active_numeric_filters) > 0
    if has_filters:
        if not matching_teams:
            st.warning("No teams match all filters.")
            st.stop()
        st.success(f"**{len(matching_teams)}** teams match: "
                   + ", ".join(str(t) for t in sorted(matching_teams)))

    df = scouted_data
    if has_filters:
        df = df[df['team_number'].isin(matching_teams)]

    # --- Percentile Rankings Table ---
    chart_cols = [c for c in df.select_dtypes(include='number').columns
                  if c not in SKIP_COLS]

    # Build per-team averages for the percentile table
    team_avgs_filtered = df.groupby('team_number').mean(numeric_only=True).reset_index()
    # Pick key numeric (non-binary) columns for the percentile table
    pct_cols = [c for c in chart_cols if c not in BINARY_COLS]
    if pct_cols and len(team_avgs_filtered) > 1:
        with st.expander("Percentile Rankings", expanded=True):
            # Build percentile dataframe
            pct_data = team_avgs_filtered[['team_number']].copy()
            pct_data['team_number'] = pct_data['team_number'].astype(str)
            col_config = {'team_number': st.column_config.TextColumn('Team', width='small')}
            for col in pct_cols:
                vals = team_avgs_filtered[col]
                col_min, col_max = vals.min(), vals.max()
                col_range = col_max - col_min
                if col_range > 0:
                    pct_data[pretty_name(col)] = ((vals - col_min) / col_range * 100).round(0).astype(int)
                else:
                    pct_data[pretty_name(col)] = 50
                col_config[pretty_name(col)] = st.column_config.ProgressColumn(
                    pretty_name(col), min_value=0, max_value=100, format='%d%%',
                )
            pct_data = pct_data.sort_values(
                pct_data.columns[1], ascending=False
            ).reset_index(drop=True)
            st.dataframe(pct_data, column_config=col_config,
                         hide_index=True, use_container_width=True)

    # --- Sparkline Trends Table ---
    spark_cols = [c for c in chart_cols if c not in BINARY_COLS]
    # Pick a handful of key columns for sparklines
    spark_display = [c for c in ['auto_fuel_made', 'teleop_fuel_made',
                                  'endgame_fuel_made', 'auto_tower_level',
                                  'endgame_tower_level']
                     if c in spark_cols]
    if spark_display and len(df) > 0:
        with st.expander("Match-by-Match Trends"):
            spark_data = {'Team': []}
            spark_config = {'Team': st.column_config.TextColumn('Team', width='small')}
            teams_in_df = sorted(df['team_number'].unique())
            for tn in teams_in_df:
                spark_data['Team'].append(str(int(tn)))
                team_matches = df[df['team_number'] == tn].sort_values('match_number')
                for col in spark_display:
                    label = pretty_name(col)
                    if label not in spark_data:
                        spark_data[label] = []
                        spark_config[label] = st.column_config.LineChartColumn(
                            label, y_min=0,
                        )
                    spark_data[label].append(team_matches[col].tolist())
            st.dataframe(pd.DataFrame(spark_data), column_config=spark_config,
                         hide_index=True, use_container_width=True)

    for section_name, section_filter in SECTIONS:
        section_cols = [c for c in chart_cols if section_filter(c)]
        if not section_cols:
            continue
        st.subheader(section_name)
        for col in sorted(section_cols):
            st.markdown(f"**{pretty_name(col)}**")
            if col in BINARY_COLS:
                chart = _binary_stacked_chart(df, col)
            else:
                chart = _numeric_bar_chart(df, col)
            st.altair_chart(chart, use_container_width=True)
