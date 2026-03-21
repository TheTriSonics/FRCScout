import pandas as pd
import streamlit as st
import altair as alt
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data,
    load_pit_data, load_opr_data,
    BINARY_COLS, SKIP_COLS, SECTIONS, pretty_name,
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
    show_raw = st.checkbox('Show raw data')
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
                        if isinstance(val, bool) or val in (0, 1) and field not in ('fuel_capacity', 'hanging_level'):
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

            if show_raw:
                st.subheader("Team Raw Scouting Data")
                st.dataframe(tdf, hide_index=True)
                if pdf is not None:
                    st.subheader("Team Raw Pit Data")
                    st.dataframe(pdf, hide_index=True)

            if len(tdf.index) == 0:
                st.info("No matches scouted for this team yet.")
                return

            # Chart every attribute grouped by game phase
            chart_cols = [c for c in tdf.select_dtypes(include='number').columns
                          if c not in SKIP_COLS]

            for section_name, section_filter in SECTIONS:
                section_cols = [c for c in chart_cols if section_filter(c)]
                if not section_cols:
                    continue
                st.subheader(section_name)
                for col in sorted(section_cols):
                    st.markdown(f"**{pretty_name(col)}**")
                    if col in BINARY_COLS:
                        chart = _match_binary_stacked_chart(tdf, col)
                    else:
                        chart = _match_bar_chart(tdf, col)
                    st.altair_chart(chart, use_container_width=True)

            # --- OPR summary ---
            if opr_data is not None:
                odf = opr_data.loc[opr_data.teamNumber == team_number]
                if not odf.empty:
                    st.subheader("OPR Breakdown")
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
