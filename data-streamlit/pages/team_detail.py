import base64
import pandas as pd
import streamlit as st
import altair as alt
from scout import (
    get_event_key, get_secret_key, load_event_data, load_team_data,
    load_pit_data, load_opr_data
)

def team_detail_page():
    """Team Detail page function"""
    team = None
    secret_key = get_secret_key()
    event_key = get_event_key()

    st.header("Team Details")
    with st.expander('Instructions'):
        st.write("""
        Select a team to see their detailed data.
        """)

    if secret_key is None or event_key is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.info(f"Current URL keys: secret_key={'set' if 'secret_key' in st.query_params else 'not set'}, event_key={'set' if 'event_key' in st.query_params else 'not set'}")
        st.stop()

    td = load_team_data(event_key)
    all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]

    # Check if we have team_detail_number in the query params
    if 'team_detail_number' in st.query_params:
        team = int(st.query_params['team_detail_number'])
        st.session_state.team_detail_number = (team, td.loc[td.number == team].iloc[0]['name'])
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
            pit_row = pdf.iloc[0]
            pit_cols = pdf.columns.tolist()

            # Photo
            if 'photo_base64' in pit_cols and pd.notna(pit_row.get('photo_base64')):
                try:
                    img_bytes = base64.b64decode(pit_row['photo_base64'])
                    st.image(img_bytes, caption=f"Team {team_number}", width=300)
                except Exception:
                    pass

            # Key fields displayed as metrics / text
            col1, col2, col3 = st.columns(3)
            # Drive train
            for field in ['drive_train', 'driveTrain', 'drivetrain']:
                if field in pit_cols and pd.notna(pit_row.get(field)):
                    col1.metric("Drive Train", str(pit_row[field]))
                    break

            # Fuel / game-piece capacity
            for field in ['fuel_capacity', 'fuelCapacity', 'game_piece_capacity']:
                if field in pit_cols and pd.notna(pit_row.get(field)):
                    col2.metric("Capacity", pit_row[field])
                    break

            # Weight
            for field in ['weight', 'robot_weight', 'robotWeight']:
                if field in pit_cols and pd.notna(pit_row.get(field)):
                    col3.metric("Weight", pit_row[field])
                    break

            # Boolean capabilities shown as yes/no chips
            bool_fields = [c for c in pit_cols if pit_row.get(c) in [True, False, 0, 1]
                           and c not in ['photo_base64', 'scouting_team', 'team_key']]
            if bool_fields:
                cap_cols = st.columns(min(len(bool_fields), 4))
                for i, field in enumerate(bool_fields):
                    val = pit_row[field]
                    label = field.replace('_', ' ').title()
                    cap_cols[i % len(cap_cols)].metric(label, "Yes" if val else "No")

            # Notes
            for field in ['notes', 'pit_notes', 'pitNotes', 'comment', 'comments']:
                if field in pit_cols and pd.notna(pit_row.get(field)) and str(pit_row[field]).strip():
                    st.write(f"**Notes:** {pit_row[field]}")
                    break

        # Trim team data down from the full event data to just theirs w/ Pandas
        if len(scouted_data.index) == 0:
            st.subheader("No match data")
        else:
            tdf = scouted_data.loc[scouted_data.scouting_team == team_number]
            if opr_data is not None:
                odf = opr_data.loc[opr_data.teamNumber == team_number]

            if show_raw:
                st.subheader("Team Raw Scouting Data")
                st.dataframe(tdf, hide_index=True)
                st.subheader("Team Raw Pit Data")
                st.dataframe(pdf, hide_index=True)

            # Gets a list of every column name in the dataframe
            allcols = tdf.columns
            # Now we can create new dataframes where we only see the auto columns
            auton_cols = [c for c in allcols if (c.startswith("auto") and not c.endswith('total')) or c == 'match_key']
            auton_df = tdf[auton_cols]
            # And then teleop...
            teleop_cols = [c for c in allcols if (c.startswith("tele") and not c.endswith('total')) or c == 'match_key']
            teleop_df = tdf[teleop_cols]
            # And endgame.
            endgame_cols = [c for c in allcols if c.startswith("endgame") or c == 'match_key']
            endgame_df = tdf[endgame_cols]
            # And our computed ones
            # comp_cols = [c for c in allcols if c.startswith("comp")]
            # comp_df = tdf[comp_cols]

            # st.subheader("Computed")
            # st.bar_chart(comp_df)

            st.subheader("Auton")
            st.bar_chart(auton_df, x='match_key')

            st.subheader("Teleop")
            st.bar_chart(teleop_df, x='match_key')

            st.subheader("Endgame")
            endgame_numeric = endgame_df.select_dtypes(include='number')
            if not endgame_numeric.empty:
                avg_endgame = endgame_numeric.mean().mean()
                st.metric("Avg Endgame Score", f"{avg_endgame:.1f}")
            st.bar_chart(endgame_df, x='match_key')

            default_off = ['teamNumber'] + [
                col for col in (odf.columns if opr_data is not None else [])
                if col.endswith('Points')
            ]
            scouted_drop = [col for col in tdf.columns if col in default_off]
            if opr_data is not None:
                opr_drop = [col for col in odf.columns if col in default_off]
            scouted_features = tdf.select_dtypes(include='number').drop(columns=['scouting_team', 'match_key'])
            # now average everything in the dataframe by number of rows
            scouted_features = scouted_features.mean().to_frame().reset_index()
            scouted_features.columns = ['feature', 'value']

            if opr_data is not None:
                opr_features = odf.select_dtypes(include='number').drop(columns=opr_drop)
                opr_features = opr_features.melt(var_name='feature', value_name='value')
            # Display the chart in Streamlit
            chart = alt.Chart(scouted_features).mark_bar().encode(
                x=alt.X('value:Q'),
                y=alt.Y('feature:N', sort='-x'),
                tooltip=['feature', 'value']
            ).properties(
                title='Scouted Dimensions (Descending)',
            )
            st.altair_chart(chart, width='stretch')

            if opr_data is not None:
                chart = alt.Chart(opr_features).mark_bar().encode(
                    x=alt.X('value:Q'),
                    y=alt.Y('feature:N', sort='-x'),
                    tooltip=['feature', 'value']
                ).properties(
                    title='OPR Dimensions (Descending)',
                )
                st.altair_chart(chart, width='stretch')
