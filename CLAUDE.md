# FRCScout Project Rules

## Pre-Push Checklist
Before every `git push`, verify:
- **API URL is production**: Check that `data-streamlit/scout.py` has `_DEFAULT_API` pointing to `https://trisonics-scouting-api.azurewebsites.net/api`, NOT `http://localhost:7071/api`. This is a common mistake when switching between local dev and production.

## Python Environment
- Use `uv` for all Python package management and script execution. Never activate venvs manually.

## Project Structure

### Streamlit App (`data-streamlit/`)
- Entry point: `scout.py` — contains `main()`, key management (`_sync_keys`, `_get_key`, `_set_key`), data loading functions, Altair theme, and page navigation.
- Pages live in `views/` (NOT `pages/` — renamed to fix Streamlit MPAv1 cold-start routing bug, see streamlit/streamlit#8860).
- Key pages: `fuel_opr.py` (Scouting Breakdown — pick rankings, team detail, PDF export), `rankings.py`, `team_detail.py`, `match_breakdowns.py`.
- PDF export: `views/pdf_export.py` — generates one-page-per-team reports using reportlab.
- Key persistence: `session_state` is source of truth, `st.query_params` pinned via `_sync_keys()` before and after `pg.run()`, `localStorage` written only from config page callbacks.

### Azure Functions API (`trisonics-api/`)
- `function_app.py` — all endpoints defined here with inline CosmosDB access via `get_container()`.
- Database: CosmosDB `ScoutingData` database. Containers: `MatchResults{year}`, `PitResults{year}`, `ScoutingResults` (no year suffix — pick rankings), `TimeTracking`.
- `ScoutingResults` container: one document per `{secret_key}_{event_key}`, holds full team pick list: `teams: [{team_number, ranking, dnp, decline, notes, picked}]` plus `version`/`updated_by`/`updated_at`. `ranking` is a dense 1..n pick order; `picked` = taken by another alliance.
  - `UpdatePickListTeam` (POST) applies a single-team change server-side with ETag retry, so concurrent editors (Flutter app) never clobber each other. Logic lives in `pick_list.py` and is mirrored by `PickList.apply` in the RebuiltScouting Flutter app — keep them in sync.
  - `PostScoutingResults` is the legacy full-document write (Streamlit). It preserves `picked` and bumps `version`, but still overwrites rankings with the caller's (possibly stale) copy.
- `GetClusters` — KMeans over per-team scouted averages + OPR components (`clustering.py`, ported from `views/clusters.py` minus PCA). Inputs cached per instance for 60s.

## Pit Scouting Data Versions
- **Notes-only records**: `drive_train` is null. Only `scouter_name` and `notes` are meaningful. Show these as "Pit Notes" separate from full pit scouting.
- **Full pit scout records**: `drive_train` is set. Has all fields (drive train, fuel capacity, hanging, auto positions, etc.). Two field schemas exist across events — the newer one (2026miwmi+) adds `auto_start_*` booleans, `can_cross_bump`, `can_enter_trench`.
- Detection: check `drive_train` field — null means notes-only.

## Pick Ranking Widget State
- `_pick_rank_{team_num}` / `_pick_notes_{team_num}` — committed (saved) data, shown in summary table. Only written on Save button click.
- `_edit_rank_{team_num}` / `_edit_notes_{team_num}` — per-team widget keys for the selectbox/text_area. Seeded from saved data on first view. Prevents Streamlit position-based widget reuse bugs when switching teams.
- Rankings loaded from API once per session via `_load_saved_results()`.
