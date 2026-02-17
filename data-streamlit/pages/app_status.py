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
    # top right. Filter out internal keys from streamlit components.
    hidden_keys = {'cookie_manager', 'cookies_loaded', 'get_all', 'cookie_manager_main'}
    obj = {}
    for k, v in st.session_state.items():
        if k in hidden_keys:
            continue
        try:
            json.dumps(v)
            obj[k] = v
        except (TypeError, ValueError):
            obj[k] = str(v)
    st.subheader('Current state')
    st.code(
        json.dumps(obj, indent=4, sort_keys=True),
        language="json",
    )
