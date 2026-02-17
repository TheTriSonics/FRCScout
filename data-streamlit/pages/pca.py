import numpy as np
from pandas import DataFrame
import streamlit as st
import altair as alt

from scout import (
    load_event_data, get_event_key, get_secret_key
)


def pca_page():
    """PCA page"""
    secret_key = get_secret_key()
    event_key = get_event_key()
    
    if secret_key is None or event_key is None:
        st.warning("Please set secret key and event key in the Config page first.")
        st.stop()
    
    st.header('Principal Component Analysis')

    scouted_data = load_event_data(secret_key, event_key)
    score_vectors = (
        scouted_data
        .groupby("scouting_team")
        .mean(numeric_only=True)
        .reset_index()
    )
    orig_score_vectors = score_vectors.copy()
    st.dataframe(score_vectors)

    numeric_cols = [c for c in orig_score_vectors.select_dtypes(include='number').columns
                    if c != 'scouting_team' and not c.startswith('comp')]
    if len(numeric_cols) >= 2:
        x_col = st.selectbox('X Axis', numeric_cols, index=0, key='pca_x')
        y_col = st.selectbox('Y Axis', numeric_cols, index=min(1, len(numeric_cols)-1), key='pca_y')

        simp = alt.Chart(orig_score_vectors).mark_circle().encode(
            x=x_col, y=y_col,
            tooltip='scouting_team',
        ).interactive()

        simp_text = simp.mark_text(
            align='left',
            baseline='top',
            color='blue',
            dx=5,
        ).encode(
            text='scouting_team'
        )
        st.altair_chart(simp_text + simp, width='stretch')

    dims = 2
    dropcols = [x for x in score_vectors.columns if x.startswith('comp')]
    score_vectors.drop(dropcols, axis=1, inplace=True)
    A = np.array(score_vectors.drop('scouting_team', axis=1).to_numpy())
    A -= A.mean(axis=0)
    U, Σ, V = np.linalg.svd(A, full_matrices=False)
    proj = U[:, :dims] * Σ[:dims]

    cols = [f'pca{x+1}' for x in range(dims)]
    proj = DataFrame(data=proj, columns=cols)
    proj['team_number'] = orig_score_vectors.scouting_team
    st.dataframe(proj)

    proj_chart = alt.Chart(proj).mark_circle().encode(
        x='pca1', y='pca2',
        tooltip='team_number',
    ).interactive()

    proj_text = proj_chart.mark_text(
        align='left',
        baseline='top',
        color='blue',
        dx=5,
    ).encode(
        text='team_number'
    )

    st.altair_chart(proj_chart+proj_text, width='stretch')
