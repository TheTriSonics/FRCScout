# trisonics-chat (prototype)

A chat agent students can ask about the event: scouted data, OPR, results,
rankings, Statbotics predictions, the scouting schedule, scouting status and
the pick board. Claude runs in Microsoft Foundry: deployment `scout-chat` on
resource `trisonics-foundry` (resource group `trisonics-chat`). Tools are
read-only and go through the public scouting API.

```bash
cd trisonics-chat
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python cli.py                         # interactive (2026miwmi, key 4003data, as "Justin B")
python cli.py -q "Who climbs best?"   # one question
python cli.py --batch questions.txt   # regression set, each line a fresh chat
python cli.py --batch data_questions.txt  # questions that need query_data
python cli.py --batch guardrails.txt  # scope and safety checks: the first block should be declined
source ../trisonics-api/setenv && python injection_test.py  # plants instructions in test-key notes, checks the bot ignores them, deletes them
```

The Foundry key comes from `FOUNDRY_API_KEY`, or from `az` if you're logged in.
Other settings: `FOUNDRY_RESOURCE`, `FOUNDRY_DEPLOYMENT`,
`SCOUT_CHAT_EFFORT` (default `medium`), `SCOUT_API_BASE`, `SCOUT_CHAT_TOOLS` (`sql`, the default = one sql tool over live data and history; `legacy` = query_data + history_sql).

| File | What it does |
|---|---|
| `scout_data.py` | Cached GET calls to the API, plus time helpers |
| `season_2026.py` | What the season's fields mean. Copy it each year. |
| `tools.py` | The tools and their schemas. Averages match the app's `TeamStats`, and `pick_board` ports `PickBoard.rows`. |
| `query_data.py` | The `query_data` tool: a structured spec (tables, filters, group-by, aggregates, correlation) run in plain Python. Every call is logged as `query_data {...}`; common queries are candidates for real API endpoints. |
| `live_sql.py`, `test_live_sql.py` | The `sql` tool (default; `SCOUT_CHAT_TOOLS=legacy` brings back the old pair): one in-memory DuckDB per session and event, the history database attached read-only as the default catalog, and this event's live data (`live.scouted`, `team_results`, `opr`, `pit`, `pit_latest`, `rankings`, `event_teams`) loaded from the same builders as `query_data` when a query first names them, then locked down like `history_sql`. Replaces `query_data` and `history_sql`. `live_history_questions.txt` asks questions that need both. |
| `cluster_similarity.py` | Nearest teams in clustering space. A port of the app's `cluster_similarity.dart`, so `similar_teams` matches Team Details. |
| `test_query_data.py`, `data_questions.txt` | Offline asserts for `query_data` (`python test_query_data.py`), and ad-hoc data questions for `--batch` |
| `agent.py` | System prompt and the tool loop, with prompt caching and usage/cost tracking |
| `cli.py` | Terminal front end |
| `first_code_of_conduct.txt` | The FIRST Code of Conduct, verbatim from firstinspires.org/about/code-of-conduct. The system prompt includes it as rules to follow. Replace this file if FIRST updates it. |

To change models, repoint the `scout-chat` deployment in Foundry; the code
doesn't need to change. Azure counts `max_tokens` against the per-minute
token limit before the request runs, so keep `MAX_TOKENS` small. At 16k,
requests stalled on 429s.

## Regression evals (`evals/`)

`python -m evals.run` asks every case in `evals/cases.py` as a fresh chat (3 at a time, about
$1 and 2 minutes for all of them) and writes `evals/results/<stamp>/report.md` (git-ignored).
Each case records the question, why it's hard, reference SQL (re-run every time, so the
expected answer follows the data), the expected facts, `must`/`must_not` regexes for a quick
PASS/CHECK, and notes for the judge. The regexes are only a smoke check: grade a run by reading
the report, which puts each answer next to the reference results and the last known-good answer
(`evals/good_answers.json`; save new ones with `--accept <results dir> <ids>`).

- `--only id1,id2`, `--tags history`, `--repeat 3` (flaky cases need several runs).
- Run it after any change to the system prompt, tool descriptions or schema notes. When a case
  fails, fix the cause in a way that would help other questions too, not the case's wording.
- The cases use 2026miwmi / 4003data (finished event). For a new season, add cases on the new
  event and keep the history ones.

## Slack (deployed)

`function_app.py` runs on Function App `trisonics-chat` (Flex Consumption, Python 3.13):
- `SlackEvents` checks Slack's signature and queues the message.
- `SlackWorker` answers it. It posts "Looking that up…", runs the agent, then edits that message into the answer.

`slack_bot.py` has the Slack-side logic:
- **Request routing:** it uses the team's `SlackConfigs` doc, matched by `slack_app_id`. The doc needs `signing_secret` and `bot_token`.
- **Who's asking:** the Scouters doc linked through Sign in with Slack. Users who haven't linked get told how.
- **History:** the thread, or the last 30 minutes of a DM.
- **Rate limit:** 40 questions per user per hour.

Each Q&A is logged to App Insights (`trisonics-chat-insights`, traces starting with `chat `).

Deploy, or redeploy next season:
```bash
az deployment group create -g trisonics-chat -f infra/main.bicep   # Foundry, models, app, budget
func azure functionapp publish trisonics-chat --python             # code
```
The Slack app needs:
- Event Subscriptions pointing at `https://trisonics-chat.azurewebsites.net/api/SlackEvents`
- Bot events `app_mention` and `message.im`
- Scopes `app_mentions:read`, `chat:write`, `im:history` and `channels:history`
- The Messages tab turned on under App Home

## History lake (`history_sql`)

All of FRC since 1992 (matches since 2002) from TBA and Statbotics, queried by the bot with
read-only SQL (DuckDB). `history_sql.py` opens the database read-only with
file, network and extension access off and the configuration locked; one
SELECT per call, 15 s, 256 MB, 200 rows. Every query is logged
(`history_sql ...`).

Three layers, each made only from the one before by format changes (see
`history/lake.py`):

| Layer | What | Where |
|---|---|---|
| raw (bronze) | TBA/Statbotics responses, gzipped JSON | `history/data/raw/`, `history-source` `raw/` |
| lake (silver) | one Parquet file per table (`team_matches` derived from `matches` here) | `history/data/lake/`, `history-source` `lake/` |
| database (gold) | the Parquet tables loaded as is | `history/data/history.duckdb`, `history` `history.duckdb` |

`history-source` and `history` are containers in the chat app's storage
account (`trisonicschatst`). `history-source` is the source of truth.

- Raw paths: `<source>/<kind>/<year>/<file>.json.gz`. Kinds: `tba/`
  `matches`, `awards`, `alliances`, `team_statuses`, `event_teams` (file =
  event key), `district_rankings` (file = district key), `events`,
  `districts`, `teams` (pages, no year); `sb/` `team_years`, `team_events`
  (`offset_NNNNN` pages). `history/sync.py` `name()` is the mapping.
- `history/sync.py FIRST LAST [--refresh YEAR]`: download raw responses to
  `history/data/raw/` (cached; ~45 min from scratch, git-ignored). Push new
  files with `az storage blob upload-batch -d history-source --destination-path raw -s history/data/raw`.
- `python -m history.build [--db-only] [--upload]`: raw → lake (~40 s) →
  database (~6 s). `--db-only` remakes only the database from the Parquet
  files (e.g. after downloading `history-source/lake/`). `--upload` puts the
  Parquet files in `history-source` and the database in `history` (set
  `AzureWebJobsStorage` to the app's storage connection string). Bot
  instances download the database to temp storage and re-check its ETag
  every 5 minutes.
- Rebuild on any machine: `az storage blob download-batch -s history-source
  --pattern 'raw/*' -d history/data` then `python -m history.build`; or just
  the lake (`--pattern 'lake/*'`) and `--db-only`.
- `history/refresh.py`: re-pulls only events running now (start − 1 day to
  end + 1 day), the season's event list, active districts and EPA, and
  updates each layer in turn: the responses to `history-source/raw/`, those
  rows replaced in the Parquet tables (`history-source/lake/`), then the
  database made again from the Parquet and uploaded. Same result as a full
  rebuild (checked 2026-11-06). Retries 5xx/429. A 40-event weekend: ~50 s,
  ~255 MB peak (the instance has 512 MB; DuckDB runs at 100 MB with one
  thread, spills to disk, and Parquet row groups are capped at 8 MB).
  - Timer `HistoryRefresh`: **off** (`AzureWebJobs.HistoryRefresh.Disabled`).
    Turn on in season: `az deployment group create ... -p
    historyRefreshEnabled=true tbaKey=$TBA_KEY` (schedule param
    `historyRefreshSchedule`, default hourly at :05), or quickly with
    `az functionapp config appsettings set -g trisonics-chat -n trisonics-chat
    --settings AzureWebJobs.HistoryRefresh.Disabled=false` (an infra deploy
    without the param turns it back off).
  - `HistoryRefreshNow` (POST, function key; `?date=YYYY-MM-DD` to pretend
    it's that day) runs one by hand.
- Infra deploys must pass `tbaKey=$TBA_KEY` (from `trisonics-api/setenv`), or
  the app's TBA key is blanked.
- `history_questions.txt`: 20 test questions (`python cli.py --batch history_questions.txt`).

## Thread follow-ups

In a channel thread the bot answers a reply without an @mention when nobody
but the asker has posted since its last reply (otherwise people are talking to each
other). Needs the Slack app's bot events `message.channels`, `message.groups`
and `message.mpim` (scopes `channels:history`, `groups:history`,
`mpim:history`). Each message is answered once across instances: the worker
claims it with an empty blob in container `slack-claims`.

## Auto-answer channels

In channels listed in the SlackConfigs doc's `auto_channels` (channel IDs,
e.g. `["C0123ABCD"]`), the bot answers every top-level message, no @mention
needed, and replies in a thread. Everywhere else it still needs a mention.
Config is cached 5 minutes. The bot must be in the channel.

## Vernacular

`vernacular.md` holds team slang and nicknames ("worlds", "GVSU", "states"),
one `term: meaning` line each, sent in the system prompt. Add a line and
redeploy (`func azure functionapp publish trisonics-chat --python`).
