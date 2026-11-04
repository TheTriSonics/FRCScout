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
`SCOUT_CHAT_EFFORT` (default `medium`), `SCOUT_API_BASE`.

| File | What it does |
|---|---|
| `scout_data.py` | Cached GET calls to the API, plus time helpers |
| `season_2026.py` | What the season's fields mean. Copy it each year. |
| `tools.py` | The tools and their schemas. Averages match the app's `TeamStats`, and `pick_board` ports `PickBoard.rows`. |
| `query_data.py` | The `query_data` tool: a structured spec (tables, filters, group-by, aggregates, correlation) run in plain Python. Every call is logged as `query_data {...}`; common queries are candidates for real API endpoints. |
| `cluster_similarity.py` | Nearest teams in clustering space. A port of the app's `cluster_similarity.dart`, so `similar_teams` matches Team Details. |
| `test_query_data.py`, `data_questions.txt` | Offline asserts for `query_data` (`python test_query_data.py`), and ad-hoc data questions for `--batch` |
| `agent.py` | System prompt and the tool loop, with prompt caching and usage/cost tracking |
| `cli.py` | Terminal front end |
| `first_code_of_conduct.txt` | The FIRST Code of Conduct, verbatim from firstinspires.org/about/code-of-conduct. The system prompt includes it as rules to follow. Replace this file if FIRST updates it. |

To change models, repoint the `scout-chat` deployment in Foundry; the code
doesn't need to change. Azure counts `max_tokens` against the per-minute
token limit before the request runs, so keep `MAX_TOKENS` small. At 16k,
requests stalled on 429s.

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

All of FRC since 2010 from TBA and Statbotics, queried by the bot with
read-only SQL (DuckDB). `history_sql.py` opens the database read-only with
file, network and extension access off and the configuration locked; one
SELECT per call, 15 s, 256 MB, 200 rows. Every query is logged
(`history_sql ...`).

- `history/sync.py FIRST LAST [--refresh YEAR]`: download raw responses to
  `history/data/raw/` (cached; ~45 min from scratch, git-ignored).
- `python -m history.build [--upload]`: raw → `history/data/lake/*.parquet`
  and `history/data/history.duckdb` (~40 s). `--upload` puts the database in
  blob `history/history.duckdb` (set `AzureWebJobsStorage` to the app's
  storage connection string). Instances download it to temp storage and
  re-check its ETag every 5 minutes.
- `history/refresh.py`: re-pulls only events running now (start − 1 day to
  end + 1 day), the season's event list, active districts and EPA, replaces
  those rows and uploads. ~1 minute for 32 events.
  - Timer `HistoryRefresh`: **off** (`AzureWebJobs.HistoryRefresh.Disabled`).
    Turn on in season: `az deployment group create ... -p
    historyRefreshEnabled=true tbaKey=$TBA_KEY` (schedule param
    `historyRefreshSchedule`, default hourly at :05).
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

## Vernacular

`vernacular.md` holds team slang and nicknames ("worlds", "GVSU", "states"),
one `term: meaning` line each, sent in the system prompt. Add a line and
redeploy (`func azure functionapp publish trisonics-chat --python`).
