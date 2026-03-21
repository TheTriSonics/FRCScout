"""
Smoke tests for every page in the Streamlit app.

These tests use Streamlit's AppTest framework to run each page and verify
it doesn't crash. They require the local API to be running at localhost:7071
and the event 2026week0 to have scouting data.

Run with:
    cd data-streamlit
    .venv/bin/python -m pytest tests/ -v
"""
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from streamlit.testing.v1 import AppTest

SECRET_KEY = "4003data"
EVENT_KEY = "2026week0"


def _make_app(page_path=None):
    """Create an AppTest instance with keys pre-loaded in session state."""
    if page_path:
        at = AppTest.from_file(page_path, default_timeout=30)
    else:
        at = AppTest.from_file(os.path.join(PROJECT_ROOT, "scout.py"), default_timeout=30)
    at.session_state["secret_key"] = SECRET_KEY
    at.session_state["event_key"] = EVENT_KEY
    return at


class TestConfigPage:
    def test_loads_without_error(self):
        at = _make_app()
        at.run()
        assert not at.exception, f"Config page crashed: {at.exception}"


class TestTeamDetailPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "team_detail.py"))
        at.run()
        assert not at.exception, f"Team Detail crashed: {at.exception}"


class TestTeamSearchPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "team_search.py"))
        at.run()
        assert not at.exception, f"Team Search crashed: {at.exception}"


class TestClustersPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "clusters.py"))
        at.run()
        assert not at.exception, f"Clusters crashed: {at.exception}"


class TestHeatmapPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "heatmap.py"))
        at.run()
        assert not at.exception, f"Heatmap crashed: {at.exception}"


class TestPicklistPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "picklist.py"))
        at.run()
        assert not at.exception, f"Picklist crashed: {at.exception}"


class TestHeadToHeadPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "head_to_head.py"))
        at.run()
        assert not at.exception, f"Head to Head crashed: {at.exception}"


class TestScoutingAccuracyPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "scouting_accuracy.py"))
        at.run()
        assert not at.exception, f"Scouting Accuracy crashed: {at.exception}"


class TestMatchBreakdownsPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "match_breakdowns.py"))
        at.run()
        assert not at.exception, f"Match Breakdowns crashed: {at.exception}"


class TestWhatIfPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "what_if.py"))
        at.run()
        assert not at.exception, f"What If crashed: {at.exception}"


class TestPCAPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "pca.py"))
        at.run()
        assert not at.exception, f"PCA crashed: {at.exception}"


class TestAppStatusPage:
    def test_loads_without_error(self):
        at = _make_app(os.path.join(PROJECT_ROOT, "pages", "app_status.py"))
        at.run()
        assert not at.exception, f"App Status crashed: {at.exception}"
