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
```

The Foundry key comes from `FOUNDRY_API_KEY`, or from `az` if you're logged in.
Other settings: `FOUNDRY_RESOURCE`, `FOUNDRY_DEPLOYMENT`,
`SCOUT_CHAT_EFFORT` (default `medium`), `SCOUT_API_BASE`.

| File | What it does |
|---|---|
| `scout_data.py` | Cached GET calls to the API, plus time helpers |
| `season_2026.py` | What the season's fields mean. Copy it each year. |
| `tools.py` | The 12 tools and their schemas. Averages match the app's `TeamStats`, and `pick_board` ports `PickBoard.rows`. |
| `agent.py` | System prompt and the tool loop, with prompt caching and usage/cost tracking |
| `cli.py` | Terminal front end |

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
