"""trisonics-chat Function App: the scouting chat bot in Slack.

SlackEvents (HTTP) checks Slack's signature, queues the message and answers
within Slack's 3-second limit. SlackWorker (queue) works out who's asking,
posts a placeholder, runs the agent and replaces the placeholder with the
answer. One message is handled once: the queue never retries (host.json
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
    wanted = (ev.get('type') == 'app_mention'
              or (ev.get('type') == 'message' and ev.get('channel_type') == 'im'))
    if payload.get('type') == 'event_callback' and wanted \
            and not ev.get('bot_id') and not ev.get('subtype') and ev.get('user'):
        auth = (payload.get('authorizations') or [{}])[0]
        out.set(json.dumps({
            'config_id': cfg['id'], 'event_id': payload.get('event_id'),
            'bot_user_id': auth.get('user_id'),
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
    # Mentions in a channel get a thread; DMs answer inline unless already threaded.
    thread = ev.get('thread_ts') or (ev['ts'] if ev.get('channel_type') != 'im' else None)

    def say(text):
        return slack_bot.api(token, 'chat.postMessage', channel=ev['channel'],
                             thread_ts=thread, text=text)

    who = slack_bot.scout_for(cfg, ev['user'])
    if who is None:
        say(slack_bot.NOT_LINKED)
        return
    if slack_bot.over_limit(ev['user']):
        say("That's a lot of questions this hour. Give me a few minutes.")
        return
    scouter, event_key = who
    placeholder = say(slack_bot.PLACEHOLDER)
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
    if placeholder.get('ok'):
        slack_bot.api(token, 'chat.update', channel=placeholder.get('channel') or ev['channel'],
                      ts=placeholder['ts'], text=answer)
    else:
        say(answer)
    # Audit trail (App Insights): who asked what, and what it cost.
    logging.info('chat %s', json.dumps({
        'secret_key': cfg['secret_key'], 'event_key': event_key, 'scouter': scouter,
        'question': question[:500], 'answer': answer[:1000], 'status': status,
        'seconds': round(time.time() - t0, 1),
        'usage': chat.usage if chat else None,
        'cost': round(chat.cost(), 4) if chat else None}))
