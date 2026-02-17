import json
import streamlit as st


def app_status_page():
    """App Status/Workspace page"""
    def apply_state():
        obj = json.loads(ta)
        st.session_state.update(obj)

    # Create text input that lets us paste in the JSON status of our app
    # and then apply it to our session
    st.subheader('Apply state')
    ta = st.text_area(label='JSON')
    apply = st.button('Apply', on_click=apply_state)

    # Display the current session JSON to the user w/ a "copy" box in the
    # top right
    obj = dict(st.session_state)
    st.subheader('Current state')
    st.code(
        json.dumps(obj, indent=4, sort_keys=True),
        language="json",
    )
