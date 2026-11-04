"""trisonics-chat Function App: the scouting chat bot in Slack.

SlackEvents (HTTP, kept warm) checks Slack's signature, posts a "Looking that
up" placeholder so the asker sees it was heard, queues the message and answers
within Slack's 3-second limit. SlackWorker (queue, polled every 2 s) works out
who's asking, runs the agent and replaces the placeholder with the answer. One message is handled once: the queue never retries (host.json
maxDequeueCount 1), so a crash gives an apology, not a duplicate answer.

Cold starts can run past Slack's 3 seconds. Slack then retries the event
(X-Slack-Retry-Num), so retries are queued too; event_ids already seen are
skipped on both sides, which covers a first delivery that was queued but
answered late.
"""
import json
import logging
import time

import azure.functions as func

import slack_bot

# agent/tools (and the anthropic SDK) load in the worker only, keeping the
# HTTP function's cold start short.

app = func.FunctionApp()
QUEUE = 'slack-events'
_client = None
_queued = slack_bot.Seen()   # event_ids queued by this HTTP instance
_handled = slack_bot.Seen()  # event_ids answered by this worker instance


def _json(body, status=200):
    return func.HttpResponse(json.dumps(body), status_code=status, mimetype='application/json')


@app.function_name(name='SlackEvents')
@app.route(route='SlackEvents', methods=['POST'], auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(arg_name='out', queue_name=QUEUE, connection='AzureWebJobsStorage')
def slack_events(req: func.HttpRequest, out: func.Out[str]) -> func.HttpResponse:
    body = req.get_body()
    try:
        payload = json.loads(body)
    except ValueError:
        return _json({'error': 'bad json'}, 400)
    cfg = slack_bot.config_for(payload, req.headers.get('X-Slack-Request-Timestamp'),
                               body, req.headers.get('X-Slack-Signature'))
    if cfg is None:
        logging.warning('SlackEvents: bad signature or unknown app %s', payload.get('api_app_id'))
        return _json({'error': 'unauthorized'}, 401)
    if payload.get('type') == 'url_verification':
        return func.HttpResponse(payload.get('challenge', ''), mimetype='text/plain')
    ev = payload.get('event') or {}
    if req.headers.get('X-Slack-Retry-Num'):
        logging.info('SlackEvents: retry %s (%s) for %s', req.headers.get('X-Slack-Retry-Num'),
                     req.headers.get('X-Slack-Retry-Reason'), payload.get('event_id'))
    if not _queued.add(payload.get('event_id')):
        return _json({'ok': True})  # this instance already queued it
    logging.info('SlackEvents: %s', json.dumps({
        'event_id': payload.get('event_id'), 'type': ev.get('type'), 'subtype': ev.get('subtype'),
        'channel_type': ev.get('channel_type'), 'thread': bool(ev.get('thread_ts')),
        'bot': bool(ev.get('bot_id'))}))
    auth = (payload.get('authorizations') or [{}])[0]
    bot = auth.get('user_id')
    is_msg = ev.get('type') == 'message'
    # A thread reply in a channel without a mention (mentions come as
    # app_mention); answered only if it follows the bot's reply.
    followup = (is_msg and ev.get('channel_type') in ('channel', 'group', 'mpim')
                and bool(ev.get('thread_ts')) and f'<@{bot}>' not in (ev.get('text') or ''))
    wanted = (ev.get('type') == 'app_mention' or followup
              or (is_msg and ev.get('channel_type') == 'im'))
    if not (payload.get('type') == 'event_callback' and wanted
            and not ev.get('bot_id') and not ev.get('subtype') and ev.get('user')):
        return _json({'ok': True})
    token = cfg['bot_token']
    if followup and not slack_bot.follows_bot(token, ev, bot):
        logging.info('SlackEvents: thread reply %s not a follow-up; skipped', ev['ts'])
        return _json({'ok': True})  # people talking to each other, not to the bot
    # One answer per Slack message, across instances (Slack can deliver the
    # same message as two events, e.g. a DM that also mentions the bot).
    if not slack_bot.claim(ev['channel'], ev['ts']):
        logging.info('SlackEvents: %s/%s already taken', ev['channel'], ev['ts'])
        return _json({'ok': True})
    # Show it was heard right away; the worker replaces this with the answer.
    placeholder = slack_bot.api(token, 'chat.postMessage', channel=ev['channel'],
                                thread_ts=slack_bot.reply_thread(ev), text=slack_bot.PLACEHOLDER)
    out.set(json.dumps({
        'config_id': cfg['id'], 'event_id': payload.get('event_id'),
        'bot_user_id': bot, 'followup': followup,
        'placeholder': ({'channel': placeholder.get('channel'), 'ts': placeholder.get('ts')}
                        if placeholder.get('ok') else None),
        'event': {k: ev.get(k) for k in ('type', 'user', 'channel', 'channel_type',
                                         'ts', 'thread_ts', 'text')},
    }))
    return _json({'ok': True})


@app.function_name(name='SlackWorker')
@app.queue_trigger(arg_name='msg', queue_name=QUEUE, connection='AzureWebJobsStorage')
def slack_worker(msg: func.QueueMessage) -> None:
    job = json.loads(msg.get_body())
    if not _handled.add(job.get('event_id')):
        logging.info('SlackWorker: skipping duplicate %s', job.get('event_id'))
        return
    try:
        _answer(job)
    except Exception:
        logging.exception('SlackWorker failed for %s', job.get('event_id'))


def _answer(job):
    global _client
    from agent import Chat, make_client
    from tools import Session
    cfg = slack_bot.config_by_id(job['config_id'])
    if cfg is None:
        logging.error('SlackWorker: config %s gone', job['config_id'])
        return
    ev, token = job['event'], cfg['bot_token']
    logging.info('SlackWorker: %s in %s (%s)', ev.get('type'), ev.get('channel_type'),
                 'follow-up' if job.get('followup') else 'direct')
    ph = job.get('placeholder')

    def finish(text):
        """Replace the placeholder SlackEvents posted (or post, if it couldn't)."""
        if ph:
            r = slack_bot.api(token, 'chat.update', channel=ph['channel'], ts=ph['ts'], text=text)
            if r.get('ok'):
                return
        slack_bot.api(token, 'chat.postMessage', channel=ev['channel'],
                      thread_ts=slack_bot.reply_thread(ev), text=text)

    who = slack_bot.scout_for(cfg, ev['user'])
    if who is None:
        finish(slack_bot.NOT_LINKED)
        return
    if slack_bot.over_limit(ev['user']):
        finish("That's a lot of questions this hour. Give me a few minutes.")
        return
    scouter, event_key = who
    question = slack_bot.clean(ev.get('text'))
    t0 = time.time()
    try:
        _client = _client or make_client()
        session = Session(cfg['secret_key'], event_key, scouter, int(cfg.get('team_number') or 0))
        chat = Chat(_client, session, style='slack',
                    history=slack_bot.history(token, ev, job.get('bot_user_id')))
        answer = slack_bot.to_mrkdwn(chat.ask(question or 'Hi'))
        status = 'ok'
    except Exception as e:
        logging.exception('Chat failed')
        answer = "Sorry, something broke while I was looking that up. Try again in a minute."
        chat, status = None, type(e).__name__
    finish(answer)
    # Audit trail (App Insights): who asked what, and what it cost.
    logging.info('chat %s', json.dumps({
        'secret_key': cfg['secret_key'], 'event_key': event_key, 'scouter': scouter,
        'question': question[:500], 'answer': answer[:1000], 'status': status,
        'seconds': round(time.time() - t0, 1),
        'usage': chat.usage if chat else None,
        'cost': round(chat.cost(), 4) if chat else None}))


# --- History lake refresh (off by default) ---
# The timer is disabled by the app setting AzureWebJobs.HistoryRefresh.Disabled
# (infra param historyRefreshEnabled); HISTORY_REFRESH_SCHEDULE sets how often.
# Only events running now are re-pulled; see history/refresh.py.

@app.function_name(name='HistoryRefresh')
@app.timer_trigger(arg_name='timer', schedule='%HISTORY_REFRESH_SCHEDULE%', run_on_startup=False)
def history_refresh(timer: func.TimerRequest) -> None:
    from history import refresh
    refresh.refresh()


@app.function_name(name='HistoryRefreshNow')
@app.route(route='HistoryRefreshNow', methods=['POST'], auth_level=func.AuthLevel.FUNCTION)
def history_refresh_now(req: func.HttpRequest) -> func.HttpResponse:
    """Run a refresh by hand (needs the function key). Optional ?date=YYYY-MM-DD
    pretends it's that day, ?days_after=N keeps events N days past their end."""
    import datetime as dt
    from history import refresh
    day = req.params.get('date')
    out = refresh.refresh(today=dt.date.fromisoformat(day) if day else None,
                          days_after=int(req.params.get('days_after', 1)))
    return _json(out)
