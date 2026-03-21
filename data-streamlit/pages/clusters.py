import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

from scout import (
    load_event_data, load_opr_data, get_event_key, get_secret_key,
    get_dnp, get_fsp, load_team_data
)


def _add_pca_components(df, feature_columns):
    """Project data onto first two principal components and add as columns."""
    X = df[feature_columns].values
    X_scaled = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-10)
    cov_matrix = np.cov(X_scaled.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    idx = eigenvalues.argsort()[::-1]
    eigenvectors = eigenvectors[:, idx]
    pca_transform = eigenvectors[:, :2]
    pca_result = np.dot(X_scaled, pca_transform)
    df_result = df.copy()
    df_result['pca1'] = pca_result[:, 0]
    df_result['pca2'] = pca_result[:, 1]
    return df_result


def _get_cluster_name(clusters, team_number):
    """Return the display index (1-based) for the cluster containing team_number."""
    team_number = str(team_number)
    for idx, (_cname, cluster) in enumerate(
        sorted(clusters.items(), key=lambda x: x[1]['opr_avg'], reverse=True),
        start=1,
    ):
        if team_number in cluster['teams']:
            return str(idx)
    return '?'


def _kmeans(data, k, n_init=10, max_iter=100, seed=1):
    """Pure numpy KMeans. Returns (labels, centers)."""
    rng = np.random.RandomState(seed)
    best_labels, best_centers, best_inertia = None, None, np.inf
    for _run in range(n_init):
        idx = rng.choice(len(data), k, replace=False)
        centers = data[idx].copy()
        for _step in range(max_iter):
            dists = np.linalg.norm(data[:, None] - centers[None, :], axis=2)
            labels = dists.argmin(axis=1)
            new_centers = np.array([
                data[labels == i].mean(axis=0) if np.any(labels == i)
                else centers[i]
                for i in range(k)
            ])
            if np.allclose(centers, new_centers):
                break
            centers = new_centers
        inertia = sum(np.sum((data[labels == i] - centers[i]) ** 2) for i in range(k))
        if inertia < best_inertia:
            best_labels, best_centers, best_inertia = labels, centers, inertia
    return best_labels, best_centers


def _compute_variances(score_vectors, score_cols):
    """Compute variance for each column, return sorted dict (descending)."""
    variances = {}
    for sc in score_cols:
        variances[sc] = np.var(score_vectors[sc])
    return dict(sorted(variances.items(), key=lambda x: x[1], reverse=True))


def clusters_page():
    """Clustering Page"""
    # Custom CSS to change pill highlight color from red to blue in dark mode
    st.markdown("""
    <style>
    @media (prefers-color-scheme: dark) {
        button[kind="pillsActive"] {
            background-color: rgba(28, 131, 225, 0.2) !important;
            color: rgb(28, 131, 225) !important;
            border-color: rgb(28, 131, 225) !important;
        }

        button[data-testid="stBaseButton-pills"]:hover {
            background-color: rgba(28, 131, 225, 0.1) !important;
            color: rgba(28, 131, 225, 0.8) !important;
        }

        .st-emotion-cache-191l437 {
            background-color: rgba(28, 131, 225, 0.2) !important;
            color: rgb(28, 131, 225) !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    sk = get_secret_key()
    ek = get_event_key()
    if sk is None or ek is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()

    scouted_data = load_event_data(sk, ek)
    if len(scouted_data.index) == 0:
        st.warning("No scouting data available for this event.")
        st.stop()
    opr_data = load_opr_data(sk, ek)
    td = load_team_data(get_event_key())
    all_teams = [(row.number, row['name']) for _, row in td.iterrows()]
    dnp = [t[0] for t in get_dnp()]
    fsp = [t[0] for t in get_fsp()]
    show_cluster_panel(scouted_data, opr_data, dnp, fsp, all_teams)


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
guide the way. What we're doing in KMeans clustering is finding things that are
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
But now we call it a Euclidean distance and it keeps on working in the 4th, 5th,
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
    # Filter out any team we are NOT picking from clustering
    if dnp_nums is not None and exclude_dnp:
        df = df[~df.team_number.isin(dnp_nums)]
    if fsp_nums is not None and exclude_fsp:
        df = df[~df.team_number.isin(fsp_nums)]
    scouted_score_vectors = (
        df
        .groupby("team_number")
        .mean(numeric_only=True)
        .reset_index()
    )

    has_opr = opr is not None and len(opr.index) > 0
    if has_opr:
        # Work on a copy to avoid mutating cached data
        opr = opr.copy()
        opr['teamNumber'] = opr['teamNumber'].astype(str)
        opr_score_vectors = (
            opr
            .groupby("teamNumber")
            .mean(numeric_only=True)
            .reset_index()
        )

    skip_cols = {'team_number', 'match_number'}
    scouted_score_cols = [
        x
        for x in scouted_score_vectors.select_dtypes(include='number').columns
        if x not in skip_cols
    ]
    scouted_variances = _compute_variances(scouted_score_vectors, scouted_score_cols)
    scouted_avail_cols = list(zip(scouted_variances.keys(), scouted_variances.values()))

    if has_opr:
        opr_score_cols = [x for x in opr_score_vectors.columns if x != 'teamNumber']
        opr_variances = _compute_variances(opr_score_vectors, opr_score_cols)
        opr_avail_cols = list(zip(opr_variances.keys(), opr_variances.values()))
    else:
        opr_score_cols = []
        opr_variances = {}
        opr_avail_cols = []

    with st.expander("Variance of each column (informational)"):
        scouted_var_df = pd.DataFrame({
            'measure': list(scouted_variances.keys()),
            'var': list(scouted_variances.values()),
        })
        if has_opr:
            opr_var_df = pd.DataFrame({
                'measure': list(opr_variances.keys()),
                'var': list(opr_variances.values()),
            })
        col_left, col_right = st.columns(2)
        with col_left:
            st.dataframe(scouted_var_df, hide_index=True)
        with col_right:
            if has_opr:
                st.dataframe(opr_var_df, hide_index=True)
            else:
                st.info("OPR data not available yet.")

    # Justin's own preference here; no reason to look at point level
    # cOPR data. Dynamically detect *Points columns.
    # Detail columns off by default — fuel_made columns are the key metrics
    detail_suffixes = ('_missed', '_accuracy', '_scored', '_shot')
    detail_prefixes = ('total_',)
    detail_exact = {'win_auto'}
    def _is_detail(name):
        return (any(name.endswith(s) for s in detail_suffixes)
                or any(name.startswith(p) for p in detail_prefixes)
                or name in detail_exact)

    scouted_data_cols = st.pills(
        'Dimensions (scouted data)', scouted_avail_cols,
        format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
        selection_mode='multi',
        default=[col for col in scouted_avail_cols
                 if not col[0].startswith('pca') and not _is_detail(col[0])]
    )
    opr_data_cols = []
    if has_opr:
        default_off = [
            col for col in opr_score_vectors.columns
            if col.endswith('Points')
        ]
        opr_data_cols = st.pills(
            'Dimensions (opr data)', opr_avail_cols,
            format_func=lambda x: f'{x[0]} ({x[1]:0.2f})',
            selection_mode='multi',
            default=[col for col in opr_avail_cols if not col[0].startswith('pca') and col[0] not in default_off]
        )

    show_features_chart = st.checkbox('Show features chart', value=True)

    if len(scouted_data_cols) == 0 and len(opr_data_cols) == 0:
        return

    # Make sure team_number is a string
    scouted_score_vectors['team_number'] = scouted_score_vectors['team_number'].astype(str)
    # Merge scouted score vectors with opr data if available
    if has_opr:
        merged_score_vectors = scouted_score_vectors.merge(
            opr_score_vectors, left_on='team_number', right_on='teamNumber'
        )
    else:
        merged_score_vectors = scouted_score_vectors
    v = merged_score_vectors.loc[:, [x[0] for x in scouted_data_cols + opr_data_cols]]
    k = min(int(cluster_count), len(v))
    if k < 1:
        st.warning("Not enough teams to cluster.")
        return
    km_labels, km_centers = _kmeans(v.to_numpy(), k)
    merged_score_vectors = _add_pca_components(
        merged_score_vectors, [x[0] for x in scouted_data_cols + opr_data_cols]
    )

    clusters = {}

    labels, centers = zip(
        *sorted(zip(set(km_labels), km_centers),
                reverse=True))
    for label, centroid in zip(labels, centers):
        clusters[label] = {
            'teams': [],
            'centroid_mag': np.linalg.norm(centroid),
            'opr_total': 0,
            'opr_avg': 0,
        }

    for (_row_idx, row), label in zip(merged_score_vectors.iterrows(), km_labels):
        clusters[label]['teams'].append(str(int(row.team_number)))
        if has_opr:
            teamopr = opr[opr.teamNumber == row.team_number]
            if len(teamopr) == 1 and 'totalPoints' in opr.columns:
                clusters[label]['opr_total'] += (
                    teamopr.totalPoints.values[0]
                )
                clusters[label]['opr_avg'] = (
                    clusters[label]['opr_total'] / len(clusters[label]['teams'])
                )

    merged_score_vectors['group_label'] = [
        _get_cluster_name(clusters, x) for x in merged_score_vectors.team_number
    ]
    for label, centroid in zip(labels, centers):
        # Create a dataframe where centroid is the 'value' column and the
        # column names are the feature names
        cluster_df = pd.DataFrame(
            [centroid],
            columns=v.columns
        )
        # Find the columns that have the largest absolute value and sort them
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
            tooltip='team_number',
        ).interactive()

        simp_text = simp.mark_text(
            align='left',
            baseline='top',
            color='blue',
            fontSize=20,
            dx=5,
        ).encode(
            text='team_number'
        )

        st.altair_chart(simp_text + simp,
                        theme="streamlit",
                        width='stretch')
    sk = get_secret_key()
    ek = get_event_key()
    group_idx = 1
    for cname, cluster in sorted(clusters.items(),
                                 key=lambda x: x[1]['opr_avg'],
                                 reverse=True):
        opr_avg = cluster['opr_total'] / len(cluster['teams']) if cluster['opr_total'] else 0
        if has_opr:
            st.header(f"Group {group_idx} ({opr_avg:0.2f} OPR Avg)")
        else:
            st.header(f"Group {group_idx}")
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
            if has_opr:
                team_opr_row = opr[opr.teamNumber == tnum]
                if 'totalPoints' in opr.columns and len(team_opr_row) > 0:
                    opr_val = round(team_opr_row.totalPoints.values[0], 1)
                    info_md += f"[{tnum} ({tname})](/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={tnum}):  {opr_val} OPR  \n"
                    continue
            info_md += f"[{tnum} ({tname})](/team_detail?secret_key={sk}&event_key={ek}&team_detail_number={tnum})  \n"
        if len(dnp_in_cluster) > 0:
            info_md += f"DNP members: {', '.join(dnp_in_cluster)}  \n"
        if len(fsp_in_cluster) > 0:
            info_md += f"1st pick members: {', '.join(fsp_in_cluster)}  \n"
        st.info(info_md)
        if show_features_chart:
            feature_df = pd.DataFrame(cluster['features'])
            feature_df.sort_values('value', ascending=False, inplace=True)
            scouted_features = feature_df[feature_df['feature'].isin([x[0] for x in scouted_data_cols])]
            chart = alt.Chart(scouted_features).mark_bar().encode(
                x=alt.X('value:Q'),
                y=alt.Y('feature:N', sort='-x'),
                tooltip=['feature', 'value']
            ).properties(
                title='Scouted Dimensions (Descending)',
            )
            st.altair_chart(chart, width='stretch')
            if has_opr and len(opr_data_cols) > 0:
                opr_features = feature_df[feature_df['feature'].isin([x[0] for x in opr_data_cols])]
                chart = alt.Chart(opr_features).mark_bar().encode(
                    x=alt.X('value:Q'),
                    y=alt.Y('feature:N', sort='-x'),
                    tooltip=['feature', 'value']
                ).properties(
                    title='OPR Dimensions (Descending)',
                )
                st.altair_chart(chart, width='stretch')
        group_idx += 1
