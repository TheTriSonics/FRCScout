# FRCScout Project Rules

## Pre-Push Checklist
Before every `git push`, verify:
- **API URL is production**: Check that `data-streamlit/scout.py` has `_DEFAULT_API` pointing to `https://trisonics-scouting-api.azurewebsites.net/api`, NOT `http://localhost:7071/api`. This is a common mistake when switching between local dev and production.

## Python Environment
- Use `uv` for all Python package management and script execution. Never activate venvs manually.
