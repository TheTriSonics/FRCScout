import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

from sklearn.cluster import KMeans

from scout import (
    load_event_data, load_opr_data, get_event_key, get_secret_key,
    get_dnp, get_fsp, load_team_data
)

def clusters_page():
    """Clustering Page"""
    
    norm = np.linalg.norm
    
    def add_pca_components(df, feature_columns):
        from sklearn.preprocessing import StandardScaler
        # Extract features
        X = df[feature_columns].values
    
        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    
        # Calculate covariance matrix
        cov_matrix = np.cov(X_scaled.T)
    
        # Calculate eigenvalues and eigenvectors
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    
        # Sort eigenvectors by eigenvalues in descending order
        idx = eigenvalues.argsort()[::-1]
        eigenvectors = eigenvectors[:, idx]
    
        # Get first two principal components
        pca_transform = eigenvectors[:, :2]
    
        # Project data onto first two principal components
        pca_result = np.dot(X_scaled, pca_transform)
    
        # Add PCA components to DataFrame
        df_result = df.copy()
        df_result['pca1'] = pca_result[:, 0]
        df_result['pca2'] = pca_result[:, 1]
    
        return df_result
    
    
    # TODO: Clean this up so we're not duplicating code
    def get_cluster_name(clusters, team_number):
        team_number = str(team_number)
        idx = 1
        for cname, cluster in sorted(clusters.items(),
                                     key=lambda x: x[1]['opr_avg'],
                                     reverse=True):
            if team_number in cluster['teams']:
                return str(idx)
            idx += 1
        return 'bob'
    
    
    def show_cluster_panel(df, opr, dnp_nums, fsp_nums, all_teams):
        st.header("KMeans clusters")
        with st.expander('Instructions'):
            st.write(
    """
    This allows us to break teams into groups that share similar attributes with one
    another.

    If you were to pick two numbers upon which to group robots and graph them out on
    an X/Y plane you can generally see which ones are similar based on their
    distance from one another. But, that only lets you consider two metrics. For
    example you could add up all of one type of scoring a team does and all of
    another type and use them as your X and Y values. And that kind of tells you
    something. But, what if you want to consider everything we collect? Every
    number. Well, you end up with more than the two dimensions you can graph in
    the X/Y plane. For most FRC games we collect 12-20 metrics and that means
    we're working in 12-20 dimensions.
    
    And while it's not intuitive to work in those higher dimensions, we have math to
    guide the way. What we're doing in KMeans clustering is finding thigns that are
    related to one another based on their distance from one another in those higher
    dimensions. To find the distance between two points in two dimensions you use
    the Pythagorean theorem.
            """)
            st.latex(
    """
    distance = \\sqrt{xdistance^2 + ydistance^2}"""
            )
            st.write(
    """
    And in three dimensions you just add the third measurement to the mix.  """)
            st.latex(
    """
    distance = \\sqrt{x^2 + y^2 + z^2}""")
            st.write(
    """
    But now we call it a Euclidian distance and it keeps on working in the 4th, 5th,
    and so on. We use this fundamental idea to find groups of teams that are similar
    using an algorithm known as KMeans clustering. It identifies groups that are
    near each other and works in higher dimensional spaces.  A suitable explanation
    of it can be found here: https://stanford.edu/~cpiech/cs221/handouts/kmeans.html
    
    In this particular tool if you set your clustering algorithm to only include
    two dimensions, or two things we measure, you'll be able to visually see that
    the groups are indeed members that are close to one another. It's just hard
    to present that relationship in any dimension higher than 3, even with the 3D
    capabilities of a computer at our disposal.
    """)
        dnp_show = 'none' if len(dnp_nums) == 0 else ', '.join(map(str, dnp_nums))
        fsp_show = 'none' if len(fsp_nums) == 0 else ', '.join(map(str, fsp_nums))
        exclude_dnp = st.checkbox(f'Exclude do not pick teams ({dnp_show})')
        exclude_fsp = st.checkbox(f'Exclude first pick teams ({fsp_show})')
        if 'cluster_count' not in st.session_state:
            st.session_state['cluster_count'] = '4'
        cluster_count = st.text_input("Cluster Count", 4)
        # Filter out any team we are NOT picking from custering
        if dnp_nums is not None and exclude_dnp:
            df = df[~df.scouting_team.isin(dnp_nums)]
        if fsp_nums is not None and exclude_fsp:
            df = df[~df.scouting_team.isin(fsp_nums)]
        scouted_score_vectors = (
            df
            .groupby("scouting_team")
            .mean(numeric_only=True)
            .reset_index()
        )
        # Conver teamNumber column to a string
        opr['teamNumber'] = opr['teamNumber'].astype(str)
        opr_score_vectors = (
            opr
            .groupby("teamNumber")
            .mean(numeric_only=True)
            .reset_index()
        )
    
        scouted_score_cols = [
            x
            for x in scouted_score_vectors.columns
            if x.startswith(("auto", "tele", "endgame", "comp"))
        ]
        opr_score_cols = [x for x in opr_score_vectors.columns if x != 'teamNumber']
        scouted_variances = {}
        opr_variances = {}
    
        for sc in scouted_score_cols:
            v = np.var(scouted_score_vectors[sc])
            scouted_variances[sc] = v
        scouted_variances_by_val = sorted(scouted_variances.items(), key=lambda x: x[1],
                                  reverse=True)
        scouted_variances = dict(scouted_variances_by_val)
        scouted_avail_cols = list(zip(scouted_variances.keys(), scouted_variances.values()))
    
        for sc in opr_score_cols:
            v = np.var(opr_score_vectors[sc])
            opr_variances[sc] = v
        opr_variances_by_val = sorted(opr_variances.items(), key=lambda x: x[1],
                                  reverse=True)
        opr_variances = dict(opr_variances_by_val)
        opr_avail_cols = list(zip(opr_variances.keys(), opr_variances.values()))
        with st.expander("Variance of each column (informational)"):
            scouted_col1 = scouted_variances.keys()
            scouted_col2 = scouted_variances.values()
            scouted_var_df = pd.DataFrame({'measure': scouted_col1, 'var': scouted_col2})
            opr_col1 = opr_variances.keys()
            opr_col2 = opr_variances.values()
            opr_var_df = pd.DataFrame({'measure': opr_col1, 'var': opr_col2})
            col_left, col_right = st.columns(2)
            with col_left:
                st.dataframe(scouted_var_df, hide_index=True)
            with col_right:
                st.dataframe(opr_var_df, hide_index=True)
    
        # Justin's own preference here; no reason to look at point level
        # cOPR data. Dynamically detect *Points columns.
        default_off = [
            col for col in opr_score_vectors.columns
            if col.endswith('Points')
        ]
        scouted_data_cols = st.pills(
            'Dimensions (scouted data)', scouted_avail_cols,
            format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
            selection_mode='multi',
            default=[col for col in scouted_avail_cols if not col[0].startswith('pca')]
        )
        opr_data_cols = st.pills(
            'Dimensions (opr data)', opr_avail_cols,
            format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
            selection_mode='multi',
            default=[col for col in opr_avail_cols if not col[0].startswith('pca') and col[0] not in default_off]
        )
    
        show_features_chart = st.checkbox('Show features chart', value=True)
    
        for sc in opr_score_cols:
            v = np.var(opr_score_vectors[sc])
            opr_variances[sc] = v
        if len(scouted_data_cols) == 0 and len(opr_data_cols) == 0:
            return  # Can't go on. Just abort
    
        model = KMeans(int(cluster_count),
                       random_state=1,
                       init='random',
                       n_init=10,
                       max_iter=100)
    
        # make sure scouting_team and teamNumber are both strings
        scouted_score_vectors['scouting_team'] = scouted_score_vectors['scouting_team'].astype(str)
        # merge scouted score vectors with opr data
        merged_score_vectors = scouted_score_vectors.merge(
            opr_score_vectors, left_on='scouting_team', right_on='teamNumber'
        )
        v = merged_score_vectors.loc[:, [x[0] for x in scouted_data_cols + opr_data_cols]]
        model.fit(v.to_numpy())
        merged_score_vectors = add_pca_components(
            merged_score_vectors, [x[0] for x in scouted_data_cols + opr_data_cols]
        )
    
        clusters = {}
    
        labels, centers = zip(
            *sorted(zip(set(model.labels_), model.cluster_centers_),
                    reverse=True))
        for label, centroid in zip(labels, centers):
            clusters[label] = {
                'teams': [],
                'centroid_mag': norm(centroid),
                'opr_total': 0,
                'opr_avg': 0,
            }
    
        for (idx, row), label in zip(merged_score_vectors.iterrows(), model.labels_):
            clusters[label]['teams'].append(str(int(row.scouting_team)))
            teamopr = opr_data[opr_data.teamNumber == row.scouting_team]
            if len(teamopr) == 1 and 'totalPoints' in opr_data.columns:
                clusters[label]['opr_total'] += (
                    teamopr.totalPoints.values[0]
                )
                clusters[label]['opr_avg'] = (
                    clusters[label]['opr_total'] / len(clusters[label]['teams'])
                )
            else:
                # Ignore team that's not in the tournament
                # print(f'{row.scouting_team}: {len(teamopr)}')
                pass
        idx = 1
    
        merged_score_vectors['group_label'] = [
            get_cluster_name(clusters, x) for x in merged_score_vectors.scouting_team
        ]
        for label, centroid in zip(labels, centers):
            # Now createa a dataframe where centroid is the 'value' column and the
            # column names are the feature names
            cluster_df = pd.DataFrame(
                [centroid],
                columns=v.columns
            )
            # Now let's find the columns that have an absolute value larger than the
            # others. IN order. We'll sort them.
            cluster_df = cluster_df.T
            cluster_df.columns = ['value']
            cluster_df['abs'] = cluster_df.value.abs()
            cluster_df = cluster_df.sort_values('abs', ascending=False)
            cluster_df = cluster_df.drop('abs', axis=1)
            cluster_df['feature'] = cluster_df.index
            cluster_df = cluster_df.reset_index(drop=True)
            clusters[label]['features'] = cluster_df.to_dict(orient='records')
    
    
        show_chart = st.checkbox('Display 2D chart (not always useful)')
        if show_chart:
            all_axis_cols = sorted([x[0] for x in scouted_data_cols + opr_data_cols])
            if 'x_axis' not in st.session_state:
                st.session_state.x_axis = 'totalPoints' if 'totalPoints' in all_axis_cols else all_axis_cols[0]
            if 'y_axis' not in st.session_state:
                st.session_state.y_axis = 'autoPoints' if 'autoPoints' in all_axis_cols else all_axis_cols[-1]
    
            x_axis = st.selectbox('X Axis', sorted([x[0] for x in scouted_data_cols + opr_data_cols + [('pca1', 1)]]), key='x_axis')
            y_axis = st.selectbox('Y Axis', sorted([x[0] for x in scouted_data_cols + opr_data_cols + [('pca2', 2)]]), key='y_axis')
    
            simp = alt.Chart(merged_score_vectors).mark_circle().encode(
                x=x_axis, y=y_axis,
                color='group_label',
                tooltip='scouting_team',
            ).interactive()
    
            simp_text = simp.mark_text(
                align='left',
                baseline='top',
                color='blue',
                fontSize=20,
                dx=5,
            ).encode(
                text='scouting_team'
            )
    
            st.altair_chart(simp_text + simp,
                            theme="streamlit",
                            width='stretch')
        sk = get_secret_key()
        ek = get_event_key()
        for cname, cluster in sorted(clusters.items(),
                                     key=lambda x: x[1]['opr_avg'],
                                     reverse=True):
            opr_avg = cluster['opr_total'] / len(cluster['teams'])
            st.header(f"Group {idx} ({opr_avg:0.2f} OPR Avg)")
            main_teams = cluster['teams']
            dnp_in_cluster = [t for t in main_teams if int(t) in dnp_nums]
            fsp_in_cluster = [t for t in main_teams if int(t) in fsp_nums]
            if exclude_dnp:
                main_teams = [t for t in main_teams if int(t) not in dnp_nums]
            if exclude_fsp:
                main_teams = [t for t in main_teams if int(t) not in fsp_nums]
            info_md = ''
            for tnum in main_teams:
                tname = next((x[1] for x in all_teams if x[0] == int(tnum)), 'N/A')
                team_opr_row = opr_data[opr_data.teamNumber == tnum]
                if 'totalPoints' in opr_data.columns and len(team_opr_row) > 0:
                    opr_val = round(team_opr_row.totalPoints.values[0], 1)
                    info_md += f"[{tnum} ({tname})](/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={tnum}):  {opr_val} OPR  \n"
                else:
                    info_md += f"[{tnum} ({tname})](/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={tnum})  \n"
            if len(dnp_in_cluster) > 0:
                info_md += f"DNP members: {', '.join(dnp_in_cluster)}  \n"
            if len(fsp_in_cluster) > 0:
                info_md += f"1st pick members: {', '.join(fsp_in_cluster)}  \n"
            st.info(info_md)
            if show_features_chart:
                # Now create a barchart from the features of this cluster sorted by
                # the value
                feature_df = pd.DataFrame(cluster['features'])
                # split feature_df into two dataframes, one for features in scouted_data_cols and another for
                # features in opr_data_cols
                feature_df.sort_values('value', ascending=False, inplace=True)
                opr_features = feature_df[ feature_df['feature'].isin([x[0] for x in opr_data_cols])]
                scouted_features = feature_df[feature_df['feature'].isin([x[0] for x in scouted_data_cols])]
                chart = alt.Chart(scouted_features).mark_bar().encode(
                    x=alt.X('value:Q'),
                    y=alt.Y('feature:N', sort='-x'),
                    tooltip=['feature', 'value']
                ).properties(
                    title='Scouted Dimensions (Descending)',
                )
                # Display the chart in Streamlit
                st.altair_chart(chart, width='stretch')
                chart = alt.Chart(opr_features).mark_bar().encode(
                    x=alt.X('value:Q'),
                    y=alt.Y('feature:N', sort='-x'),
                    tooltip=['feature', 'value']
                ).properties(
                    title='OPR Dimensions (Descending)',
                )
                # Display the chart in Streamlit
                st.altair_chart(chart, width='stretch')
            idx += 1
    
    # Custom CSS to change pill highlight color from red to blue in dark mode
    st.markdown("""
    <style>
    /* Change pills highlight color from red to blue in dark mode */
    @media (prefers-color-scheme: dark) {
        /* Target the pill button with attribute kind="pillsActive" */
        button[kind="pillsActive"] {
            background-color: rgba(28, 131, 225, 0.2) !important;
            color: rgb(28, 131, 225) !important;
            border-color: rgb(28, 131, 225) !important;
        }
    
        /* For hover state on inactive pills */
        button[data-testid="stBaseButton-pills"]:hover {
            background-color: rgba(28, 131, 225, 0.1) !important;
            color: rgba(28, 131, 225, 0.8) !important;
        }
    
        /* Target the specific class if needed */
        .st-emotion-cache-191l437 {
            background-color: rgba(28, 131, 225, 0.2) !important;
            color: rgb(28, 131, 225) !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    scouted_data = load_event_data(get_secret_key(), get_event_key())
    opr_data = load_opr_data(get_secret_key(), get_event_key())
    td = load_team_data(get_event_key())
    all_teams = [(row.number, row['name']) for idx, row in td.iterrows()]
    dnp = [t[0] for t in get_dnp()]
    fsp = [t[0] for t in get_fsp()]
    show_cluster_panel(scouted_data, opr_data, dnp, fsp, all_teams)
