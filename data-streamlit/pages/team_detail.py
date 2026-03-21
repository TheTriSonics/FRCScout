import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import plotly.graph_objects as go
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data,
    load_pit_data, load_opr_data,
    BINARY_COLS, SKIP_COLS, SECTIONS, SCOUTED_OPR_MAP, pretty_name,
)


def _match_bar_chart(tdf, col):
    """Bar chart of a numeric column across matches for one team."""
    chart_df = tdf[['match_number', col]].copy()
    chart_df['match_number'] = chart_df['match_number'].astype(str)
    chart = alt.Chart(chart_df).mark_bar().encode(
        x=alt.X('match_number:N', title='Match', sort=None),
        y=alt.Y(f'{col}:Q', title=pretty_name(col)),
        tooltip=['match_number', alt.Tooltip(f'{col}:Q', format='.1f')],
    ).properties(height=250)
    return chart


def _match_binary_stacked_chart(tdf, col):
    """Stacked bar chart for a binary column across matches (yes/no)."""
    chart_df = tdf[['match_number', col]].copy()
    chart_df['match_number'] = chart_df['match_number'].astype(str)
    chart_df['result'] = chart_df[col].map({1: 'yes', 0: 'no', True: 'yes', False: 'no'})
    chart = alt.Chart(chart_df).mark_bar().encode(
        x=alt.X('match_number:N', title='Match', sort=None),
        y=alt.Y('count():Q', title=''),
        color=alt.Color('result:N',
                        scale=alt.Scale(domain=['yes', 'no'],
                                        range=['#59a14f', '#e15759']),
                        title=''),
        tooltip=['match_number', 'result'],
        order=alt.Order('result:N', sort='descending'),
    ).properties(height=200)
    return chart


def _match_bar_chart_with_trend(tdf, col):
    """Bar chart with a trend line overlay."""
    chart_df = tdf[['match_number', col]].copy()
    chart_df['match_number'] = chart_df['match_number'].astype(str)
    chart_df['match_seq'] = range(len(chart_df))

    bars = alt.Chart(chart_df).mark_bar().encode(
        x=alt.X('match_number:N', title='Match', sort=None),
        y=alt.Y(f'{col}:Q', title=pretty_name(col)),
        tooltip=['match_number', alt.Tooltip(f'{col}:Q', format='.1f')],
    )

    # Trend line via linear regression
    trend = alt.Chart(chart_df).mark_line(color='#e15759', strokeWidth=2).transform_regression(
        'match_seq', col, method='linear'
    ).encode(
        x=alt.X('match_seq:Q', axis=None),
        y=alt.Y(f'{col}:Q'),
    )

    # Overlay using dual axis trick — layer bars with independent trend
    return alt.layer(bars, trend).resolve_scale(x='independent').properties(height=250)


def _compute_consistency(tdf, chart_cols):
    """Compute consistency metrics for non-binary columns."""
    rows = []
    for col in sorted(chart_cols):
        if col in BINARY_COLS:
            continue
        vals = tdf[col].dropna()
        if len(vals) < 2:
            continue
        avg = vals.mean()
        std = vals.std()
        # Consistency: 100% means zero variance, lower = more erratic
        consistency = max(0, 100 * (1 - std / (avg + 1e-10))) if avg > 0 else 100
        # Trend: slope of linear fit (positive = improving)
        if len(vals) >= 2:
            x = np.arange(len(vals))
            slope = np.polyfit(x, vals.values, 1)[0]
        else:
            slope = 0
        rows.append({
            'Attribute': pretty_name(col),
            'Avg': round(avg, 1),
            'Std Dev': round(std, 1),
            'Consistency': round(consistency, 0),
            'Trend': round(slope, 2),
        })
    return pd.DataFrame(rows)


def team_detail_page():
    """Team Detail page function"""
    team = None
    secret_key = get_secret_key()
    event_key = get_event_key()

    st.header("Team Details")
    with st.expander('Instructions'):
        st.write("""
        Select a team to see their detailed data across all scouted matches.
        """)

    if secret_key is None or event_key is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    td = load_team_data(event_key)
    all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]

    # Check if we have team_detail_number in the query params
    if 'team_detail_number' in st.query_params:
        team = int(st.query_params['team_detail_number'])
        matching = td.loc[td.number == team]
        if not matching.empty:
            st.session_state.team_detail_number = (team, matching.iloc[0]['name'])
    team = st.selectbox("Team", all_teams,
                        key='team_detail_number',
                        format_func=lambda x: f'{x[0]} ({x[1]})')
    if team:
        with st.spinner('Loading team data...'):
            scouted_data = load_event_data(secret_key, event_key)
            opr_data = load_opr_data(secret_key, event_key)
            (team_number, team_name) = team
            pdf = load_pit_data(secret_key, event_key, team_number)

        # --- Pit Scouting Summary ---
        if pdf is not None and len(pdf.index) > 0:
            st.subheader("Pit Scouting")
            skip_fields = {
                'scouter_name', 'secret_team_key', 'event_key',
                'team_number', 'timestamp', 'image_names',
            }
            for pit_idx in range(len(pdf.index)):
                pit_row = pdf.iloc[pit_idx]
                pit_cols = pdf.columns.tolist()
                scouter = pit_row.get('scouter_name', 'Unknown')
                ts = pit_row.get('timestamp', '')
                with st.expander(f"Scout: {scouter} — {ts}", expanded=(pit_idx == len(pdf.index) - 1)):
                    # Photos
                    if 'image_names' in pit_cols:
                        images = pit_row.get('image_names')
                        if isinstance(images, list) and len(images) > 0:
                            img_cols = st.columns(min(len(images), 3))
                            for i, img_url in enumerate(images):
                                try:
                                    img_cols[i % len(img_cols)].image(img_url, width=300)
                                except Exception:
                                    pass

                    # Build a clean two-column table of all fields
                    display_rows = []
                    for field in pit_cols:
                        if field in skip_fields:
                            continue
                        val = pit_row.get(field)
                        if val is None or (isinstance(val, str) and not val.strip()):
                            continue
                        label = pretty_name(field)
                        is_bool = isinstance(val, bool) or (val in (0, 1) and field not in ('fuel_capacity', 'hanging_level'))
                        if is_bool:
                            display_val = 'Yes' if val else 'No'
                        else:
                            display_val = str(val)
                        display_rows.append({'Field': label, 'Value': display_val})
                    if display_rows:
                        st.table(pd.DataFrame(display_rows).set_index('Field'))

        # --- Match Scouting Charts ---
        if len(scouted_data.index) == 0:
            st.subheader("No match data")
        else:
            tdf = scouted_data.loc[scouted_data.team_number == team_number].copy()
            tdf = tdf.sort_values('match_number')

            if len(tdf.index) == 0:
                st.info("No matches scouted for this team yet.")
                return

            chart_cols = [c for c in tdf.select_dtypes(include='number').columns
                          if c not in SKIP_COLS]

            # --- KPI Summary Cards ---
            # Pick the most important metrics for at-a-glance view
            kpi_cols = [c for c in ['auto_fuel_made', 'teleop_fuel_made',
                                    'endgame_fuel_made', 'endgame_tower_level',
                                    'auto_tower_level']
                        if c in tdf.columns]
            if kpi_cols:
                kpi_columns = st.columns(len(kpi_cols) + 1)
                for i, col in enumerate(kpi_cols):
                    avg = tdf[col].mean()
                    # Delta: last 3 matches vs first 3 matches
                    if len(tdf) >= 4:
                        first_half = tdf[col].head(len(tdf) // 2).mean()
                        second_half = tdf[col].tail(len(tdf) // 2).mean()
                        delta = round(second_half - first_half, 1)
                        delta_str = f"{delta:+.1f}"
                    else:
                        delta_str = None
                    kpi_columns[i].metric(pretty_name(col), f"{avg:.1f}", delta=delta_str)
                # Matches scouted count
                kpi_columns[-1].metric("Matches Scouted", len(tdf))

            # --- Similar Teams ---
            with st.expander("Similar Teams"):
                st.write("""
                Find teams most similar to this one. Select dimensions,
                then check neighbors to add them to the radar chart.
                """)

                all_avgs = scouted_data.groupby('team_number').mean(numeric_only=True).reset_index()
                nn_numeric_cols = [c for c in all_avgs.select_dtypes(include='number').columns
                                   if c not in SKIP_COLS and c != 'team_number' and c != 'match_number']
                nn_binary_cols = [c for c in nn_numeric_cols if c in BINARY_COLS]
                nn_value_cols = [c for c in nn_numeric_cols if c not in BINARY_COLS]

                nn_selected_cols = []
                for section_name, section_test in SECTIONS:
                    sec_binary = [c for c in nn_binary_cols if section_test(c)]
                    sec_numeric = [c for c in nn_value_cols if section_test(c)]
                    if not sec_binary and not sec_numeric:
                        continue
                    st.markdown(f"**{section_name}**")
                    if sec_binary:
                        cols = st.columns(min(len(sec_binary), 4))
                        for i, col_name in enumerate(sec_binary):
                            with cols[i % len(cols)]:
                                if st.checkbox(pretty_name(col_name), key=f'nn_bin_{col_name}'):
                                    nn_selected_cols.append(col_name)
                    if sec_numeric:
                        cols = st.columns(min(len(sec_numeric), 4))
                        for i, col_name in enumerate(sec_numeric):
                            with cols[i % len(cols)]:
                                if st.checkbox(pretty_name(col_name), key=f'nn_num_{col_name}'):
                                    nn_selected_cols.append(col_name)

                if len(nn_selected_cols) == 0:
                    st.info("Select dimensions above to find similar teams.")
                elif len(all_avgs) < 2:
                    st.info("Need at least 2 scouted teams for comparison.")
                else:
                    feature_matrix = all_avgs[nn_selected_cols].values
                    stds = feature_matrix.std(axis=0)
                    stds[stds == 0] = 1
                    scaled = (feature_matrix - feature_matrix.mean(axis=0)) / stds

                    team_idx = all_avgs.index[all_avgs['team_number'] == team_number]
                    if len(team_idx) > 0:
                        team_vec = scaled[team_idx[0]]
                        dists = np.linalg.norm(scaled - team_vec, axis=1)
                        all_avgs_copy = all_avgs[['team_number']].copy()
                        all_avgs_copy['distance'] = dists
                        all_avgs_copy = all_avgs_copy[all_avgs_copy['team_number'] != team_number]
                        all_avgs_copy = all_avgs_copy.sort_values('distance').reset_index(drop=True)

                        sk = get_secret_key()
                        ek = get_event_key()

                        # Neighbor list with checkboxes for radar chart
                        st.markdown("**Nearest neighbors** (check to compare on radar)")
                        radar_teams = [team_number]  # always include current team
                        for rank, (_, nrow) in enumerate(all_avgs_copy.iterrows()):
                            tnum = int(nrow['team_number'])
                            dist = nrow['distance']
                            tname = next((x[1] for x in all_teams if x[0] == tnum), 'N/A')
                            col_link, col_check = st.columns([3, 1])
                            with col_link:
                                st.markdown(
                                    f"{rank+1}. [{tnum} ({tname})](/team_detail?secret_key={sk}"
                                    f"&event_key={ek}&team_detail_number={tnum})"
                                    f" — distance: {dist:.2f}"
                                )
                            with col_check:
                                if st.checkbox("Radar", key=f'radar_{tnum}',
                                               value=(rank < 2)):
                                    radar_teams.append(tnum)

                        # --- Radar chart (Plotly) ---
                        if len(radar_teams) > 1 and len(nn_selected_cols) >= 3:
                            st.markdown("---")
                            attr_labels = [pretty_name(c) for c in nn_selected_cols]

                            fig = go.Figure()
                            for tn in radar_teams:
                                row = all_avgs[all_avgs['team_number'] == tn]
                                if row.empty:
                                    continue
                                label = f"{tn} (this team)" if tn == team_number else str(tn)
                                # Normalize to 0-100 percentile scale
                                vals = []
                                raw_vals = []
                                for col in nn_selected_cols:
                                    val = row[col].values[0]
                                    col_min = all_avgs[col].min()
                                    col_max = all_avgs[col].max()
                                    col_range = col_max - col_min
                                    pct = ((val - col_min) / col_range * 100) if col_range > 0 else 50
                                    vals.append(round(pct, 1))
                                    raw_vals.append(round(val, 1))
                                hover = [f"{a}: {r} (P{int(p)})"
                                         for a, r, p in zip(attr_labels, raw_vals, vals)]
                                fig.add_trace(go.Scatterpolar(
                                    r=vals + [vals[0]],
                                    theta=attr_labels + [attr_labels[0]],
                                    name=label,
                                    fill='toself',
                                    opacity=0.3 if tn != team_number else 0.5,
                                    hovertext=hover + [hover[0]],
                                    hoverinfo='text+name',
                                ))
                            fig.update_layout(
                                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                                title='Attribute Comparison (percentile scale)',
                                height=500,
                                margin=dict(t=60, b=40, l=60, r=60),
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        elif len(nn_selected_cols) < 3:
                            st.caption("Select at least 3 dimensions for radar chart.")

            # --- Consistency & Trends ---
            with st.expander("Consistency & Trends"):
                st.write("""
                **Consistency** measures how repeatable a team's performance is
                (100% = identical every match, lower = more variable).
                **Trend** is the per-match slope — positive means improving,
                negative means declining over the event.
                """)
                consistency_df = _compute_consistency(tdf, chart_cols)
                if not consistency_df.empty:
                    # Color the trend column
                    def _trend_color(val):
                        if val > 0:
                            return 'color: #59a14f'
                        elif val < 0:
                            return 'color: #e15759'
                        return ''

                    styled = (consistency_df.set_index('Attribute')
                              .style
                              .map(_trend_color, subset=['Trend'])
                              .format({'Consistency': '{:.0f}%', 'Trend': '{:+.2f}'}))
                    st.dataframe(styled, use_container_width=True)
                else:
                    st.info("Need more than one match for consistency data.")

                # Outlier detection (within the same expander)
                if len(tdf) >= 4:
                    st.markdown("---")
                    st.markdown("**Outlier Matches**")
                    st.caption("Matches where a value is more than 2 standard deviations from the team's mean.")
                    outlier_rows = []
                    for col in sorted(chart_cols):
                        if col in BINARY_COLS:
                            continue
                        vals = tdf[col].dropna()
                        if len(vals) < 4:
                            continue
                        mean = vals.mean()
                        std = vals.std()
                        if std < 0.01:
                            continue
                        for _, mrow in tdf.iterrows():
                            val = mrow[col]
                            if abs(val - mean) > 2 * std:
                                direction = 'high' if val > mean else 'low'
                                outlier_rows.append({
                                    'Match': int(mrow['match_number']),
                                    'Attribute': pretty_name(col),
                                    'Value': round(val, 1),
                                    'Team Avg': round(mean, 1),
                                    'Flag': f"Unusually {direction}",
                                })
                    if outlier_rows:
                        out_df = pd.DataFrame(outlier_rows)
                        def _flag_color(val):
                            if 'high' in str(val):
                                return 'color: #f28e2b'
                            elif 'low' in str(val):
                                return 'color: #e15759'
                            return ''
                        st.dataframe(out_df.style.map(_flag_color, subset=['Flag']),
                                     hide_index=True, use_container_width=True)
                    else:
                        st.caption("No outliers detected.")

            # --- Match charts in per-section accordions ---
            show_trends = st.checkbox("Show trend lines on charts", value=True)

            for section_name, section_filter in SECTIONS:
                section_cols = [c for c in chart_cols if section_filter(c)]
                if not section_cols:
                    continue
                with st.expander(section_name):
                    for col in sorted(section_cols):
                        st.markdown(f"**{pretty_name(col)}**")
                        if col in BINARY_COLS:
                            chart = _match_binary_stacked_chart(tdf, col)
                        elif show_trends and len(tdf) >= 2:
                            chart = _match_bar_chart_with_trend(tdf, col)
                        else:
                            chart = _match_bar_chart(tdf, col)
                        st.altair_chart(chart, use_container_width=True)

            # --- Match Notes ---
            note_cols = [c for c in ['match_notes', 'auto_notes'] if c in tdf.columns]
            if note_cols:
                has_notes = False
                for col in note_cols:
                    if tdf[col].dropna().astype(str).str.strip().str.len().sum() > 0:
                        has_notes = True
                        break
                if has_notes:
                    with st.expander("Match Notes"):
                        for _, mrow in tdf.iterrows():
                            match_num = mrow.get('match_number', '?')
                            notes = []
                            for col in note_cols:
                                val = str(mrow.get(col, '')).strip()
                                if val:
                                    notes.append(f"**{pretty_name(col)}:** {val}")
                            if notes:
                                st.markdown(f"**Match {match_num}** — " + " | ".join(notes))

            # --- Scouted vs OPR ---
            has_opr = opr_data is not None
            odf = None
            if has_opr:
                odf = opr_data.loc[opr_data.teamNumber == team_number]
                if odf.empty:
                    has_opr = False

            if has_opr:
                with st.expander("Scouted vs OPR"):
                    st.write("""
                    Side-by-side comparison of our scouting averages against
                    OPR (calculated from official match scores). Large gaps
                    may indicate scouting inaccuracies or that OPR is
                    distributing credit differently than what we observed.
                    """)

                    # Build comparison data
                    team_avg = tdf.select_dtypes(include='number').mean()
                    opr_row = odf.iloc[0]

                    comparison_rows = []
                    for scouted_col, opr_col, label in SCOUTED_OPR_MAP:
                        if scouted_col in team_avg.index and opr_col in opr_row.index:
                            s_val = team_avg[scouted_col]
                            o_val = opr_row[opr_col]
                            diff = s_val - o_val
                            pct = (diff / (o_val + 1e-10)) * 100 if o_val != 0 else 0
                            comparison_rows.append({
                                'Metric': label,
                                'Scouted Avg': round(s_val, 1),
                                'OPR': round(o_val, 1),
                                'Diff': round(diff, 1),
                                '% Diff': round(pct, 0),
                            })

                    if comparison_rows:
                        comp_df = pd.DataFrame(comparison_rows)

                        # Grouped bar chart
                        chart_data = comp_df.melt(
                            id_vars='Metric',
                            value_vars=['Scouted Avg', 'OPR'],
                            var_name='Source',
                            value_name='Value',
                        )
                        chart = alt.Chart(chart_data).mark_bar().encode(
                            x=alt.X('Metric:N', title='', axis=alt.Axis(labelAngle=-45)),
                            y=alt.Y('Value:Q', title='Value'),
                            color=alt.Color('Source:N',
                                            scale=alt.Scale(
                                                domain=['Scouted Avg', 'OPR'],
                                                range=['#4e79a7', '#f28e2b']),
                                            title=''),
                            xOffset='Source:N',
                            tooltip=['Metric', 'Source', alt.Tooltip('Value:Q', format='.1f')],
                        ).properties(height=350)
                        st.altair_chart(chart, use_container_width=True)

                        # Difference table
                        def _diff_color(val):
                            if isinstance(val, (int, float)):
                                if abs(val) > 20:
                                    return 'color: #e15759; font-weight: bold'
                                elif abs(val) > 10:
                                    return 'color: #f28e2b'
                            return ''

                        styled = (comp_df.set_index('Metric')
                                  .style
                                  .map(_diff_color, subset=['% Diff'])
                                  .format({'% Diff': '{:+.0f}%', 'Diff': '{:+.1f}'}))
                        st.dataframe(styled, use_container_width=True)
                    else:
                        st.info("No matching scouted/OPR columns to compare.")

                # --- Scouting Accuracy (event-wide) ---
                with st.expander("Scouting Accuracy (All Teams)"):
                    st.write("""
                    How well does our scouting correlate with OPR across all
                    teams? Each dot is a team — closer to the diagonal line
                    means better agreement. The R² value tells you how much
                    of the OPR variation our scouting explains.
                    """)

                    all_avgs = scouted_data.groupby('team_number').mean(numeric_only=True).reset_index()
                    # Merge with OPR
                    opr_copy = opr_data.copy()
                    opr_copy['teamNumber'] = opr_copy['teamNumber'].astype(int)
                    merged = all_avgs.merge(opr_copy, left_on='team_number', right_on='teamNumber', how='inner')

                    for scouted_col, opr_col, label in SCOUTED_OPR_MAP:
                        if scouted_col not in merged.columns or opr_col not in merged.columns:
                            continue
                        valid = merged[[scouted_col, opr_col, 'team_number']].dropna()
                        if len(valid) < 3:
                            continue

                        # R² calculation
                        x = valid[scouted_col].values
                        y = valid[opr_col].values
                        correlation = np.corrcoef(x, y)[0, 1] if np.std(x) > 0 and np.std(y) > 0 else 0
                        r_squared = correlation ** 2

                        # Color the current team differently
                        valid = valid.copy()
                        valid['team_number'] = valid['team_number'].astype(str)
                        valid['highlight'] = valid['team_number'].apply(
                            lambda t: 'This team' if int(t) == team_number else 'Other'
                        )

                        scatter = alt.Chart(valid).mark_circle(size=80).encode(
                            x=alt.X(f'{scouted_col}:Q', title=f'Scouted ({label})'),
                            y=alt.Y(f'{opr_col}:Q', title=f'OPR ({label})'),
                            color=alt.Color('highlight:N',
                                            scale=alt.Scale(
                                                domain=['Other', 'This team'],
                                                range=['#4e79a7', '#e15759']),
                                            title=''),
                            tooltip=['team_number',
                                     alt.Tooltip(f'{scouted_col}:Q', format='.1f', title='Scouted'),
                                     alt.Tooltip(f'{opr_col}:Q', format='.1f', title='OPR')],
                        )

                        # Perfect agreement line
                        min_val = min(valid[scouted_col].min(), valid[opr_col].min())
                        max_val = max(valid[scouted_col].max(), valid[opr_col].max())
                        line_df = pd.DataFrame({scouted_col: [min_val, max_val], opr_col: [min_val, max_val]})
                        ref_line = alt.Chart(line_df).mark_line(
                            strokeDash=[5, 5], color='gray', opacity=0.5
                        ).encode(x=f'{scouted_col}:Q', y=f'{opr_col}:Q')

                        r2_color = '#59a14f' if r_squared > 0.7 else ('#f28e2b' if r_squared > 0.4 else '#e15759')
                        st.markdown(f"**{label}** — R² = :{r2_color}[{r_squared:.2f}]")
                        st.altair_chart(scatter + ref_line, use_container_width=True)

                # --- Full OPR Breakdown ---
                with st.expander("Full OPR Breakdown"):
                    default_off = ['teamNumber'] + [
                        col for col in odf.columns if col.endswith('Points')
                    ]
                    opr_drop = [col for col in odf.columns if col in default_off]
                    opr_features = odf.select_dtypes(include='number').drop(columns=opr_drop)
                    opr_features = opr_features.melt(var_name='feature', value_name='value')
                    chart = alt.Chart(opr_features).mark_bar().encode(
                        x=alt.X('value:Q'),
                        y=alt.Y('feature:N', sort='-x'),
                        tooltip=['feature', alt.Tooltip('value:Q', format='.1f')],
                    ).properties(title='OPR Dimensions (Descending)')
                    st.altair_chart(chart, use_container_width=True)

            # --- Raw data (bottom) ---
            with st.expander("Raw Data"):
                st.dataframe(tdf, hide_index=True)
                if pdf is not None:
                    st.subheader("Pit Data")
                    st.dataframe(pdf, hide_index=True)
