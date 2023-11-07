import pandas as pd
import numpy as np
import streamlit as st
import pygwalker as pyg
import streamlit.components.v1 as components

from scout import (
    load_event_data, load_opr_data, load_team_data, get_event_key,
    get_secret_key,
)


def show_raw_grid_panel(df):
    st.subheader("Raw")

    # Generate the HTML using Pygwalker, a charting tool
    pyg_html = pyg.to_html(df)
    # Embed the HTML into the Streamlit app
    components.html(pyg_html, height=1000, scrolling=True)



scouted_data = load_event_data(get_secret_key(), get_event_key())
show_raw_grid_panel(scouted_data)
