"""Shared fixtures for Streamlit app smoke tests."""
import os
import sys
import pytest

# Make sure the project root is on sys.path so `scout` can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Default event with known data — 2026week0 has 2 scouting records
TEST_SECRET_KEY = "4003data"
TEST_EVENT_KEY = "2026week0"


@pytest.fixture(autouse=True)
def _set_session_defaults(monkeypatch):
    """Inject test keys into environment so pages can load data."""
    monkeypatch.setenv("STREAMLIT_TEST", "1")
