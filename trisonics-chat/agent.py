"""The chat agent: a manual tool-use loop against Claude in Microsoft Foundry.

The model is whatever the Foundry deployment FOUNDRY_DEPLOYMENT points at
(default "scout-chat"); swap models in Foundry, not here.
"""
import json
import os
import subprocess
import time

import anthropic

import season_2026 as season
from tools import TOOL_DEFS, Session, run_tool

FOUNDRY_RESOURCE = os.environ.get('FOUNDRY_RESOURCE', 'trisonics-foundry')
DEPLOYMENT = os.environ.get('FOUNDRY_DEPLOYMENT', 'scout-chat')
EFFORT = os.environ.get('SCOUT_CHAT_EFFORT', 'medium')
MAX_TOOL_ROUNDS = 12
# Azure counts max_tokens against the per-minute token limit up front, so
# keep it near what a chat answer needs.
MAX_TOKENS = 4000
MAX_RESULT_CHARS = 60_000

SYSTEM = f"""\
You are the scouting assistant for an FRC team. Students ask you about the
current event: teams, scouted data, OPR, official results and rankings,
Statbotics predictions, the scouting schedule, scouting progress and the
team's pick list. They are high school students, usually on a phone in a
loud arena, so answer briefly and plainly: lead with the answer, then the few
numbers that back it up. Use short lists or small tables only when comparing
several teams. No preamble.

Use the tools for every fact about the event; never guess numbers, names or
times. If the data doesn't cover the question, say so and say what would.
Say where numbers come from when it matters: "scouted" averages come from
this team's own scouts (accuracy ratings and volley counts, a few matches per
team, can be noisy); OPR and official results come from FIRST/TBA;
Statbotics predictions are estimates. Mention small samples (under 3
scouted matches). Call several tools at once when they're independent.
Refer to people by name; don't assume anyone's pronouns.

You only read data; you can't change the schedule, pick list or scouting
records. If asked to, explain where in the scouting app to do it.

Game context:
{season.GAME_NOTES}
"""


def _foundry_key():
    key = os.environ.get('FOUNDRY_API_KEY')
    if key:
        return key
    # Local convenience: borrow the key from a logged-in az CLI.
    out = subprocess.run(
        ['az', 'cognitiveservices', 'account', 'keys', 'list', '-g',
         os.environ.get('FOUNDRY_RESOURCE_GROUP', 'trisonics-chat'),
         '-n', FOUNDRY_RESOURCE, '--query', 'key1', '-o', 'tsv'],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def make_client():
    return anthropic.AnthropicFoundry(resource=FOUNDRY_RESOURCE, api_key=_foundry_key())


SLACK_STYLE = ('Reply in Slack mrkdwn: *bold* (single asterisks), _italic_, "-" bullets, '
               'no # headings and no markdown tables. For a small table use a ``` code block '
               'with aligned columns, under 60 characters wide.')


def _session_note(s: Session, style=None):
    who = s.scouter_name or 'unknown'
    note = (f'Asking: {who} (scout for team {s.team_number or "?"}). Event: {s.event_key}. '
            'Treat "me"/"my"/"I" as this scout and "us"/"our team" as their team number.')
    return f'{note} {SLACK_STYLE}' if style == 'slack' else note


class Chat:
    """One conversation. Keep the object to keep the history.

    history: earlier turns as [(role, text)] with role 'user' or 'assistant',
    oldest first (e.g. rebuilt from a Slack thread). Tool calls from those
    turns aren't kept; the model re-checks data it needs.
    """

    def __init__(self, client, session: Session, log=None, style=None, history=None):
        self.client = client
        self.session = session
        self.style = style
        self.messages = []
        for role, text in history or []:
            if not self.messages and role != 'user':
                continue  # must start with the user
            if self.messages and self.messages[-1]['role'] == role:
                self.messages[-1]['content'] += '\n\n' + text
            else:
                self.messages.append({'role': role, 'content': text})
        if self.messages:
            self.messages[0]['content'] = self._with_context(self.messages[0]['content'])
            if self.messages[-1]['role'] == 'user':
                self.messages.append({'role': 'assistant', 'content': '(no reply)'})
        self.log = log or (lambda *_: None)
        self.usage = {'input': 0, 'cache_read': 0, 'cache_write': 0, 'output': 0, 'calls': 0}

    def _with_context(self, text):
        return f'<context>{_session_note(self.session, self.style)}</context>\n\n{text}'

    def ask(self, question: str) -> str:
        if not self.messages:
            question = self._with_context(question)
        self.messages.append({'role': 'user', 'content': question})
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self.client.messages.create(
                model=DEPLOYMENT,
                max_tokens=MAX_TOKENS,
                system=SYSTEM,
                tools=TOOL_DEFS,
                messages=self.messages,
                output_config={'effort': EFFORT},
                cache_control={'type': 'ephemeral'},
            )
            self._count(resp.usage)
            self.messages.append({'role': 'assistant', 'content': resp.content})
            if resp.stop_reason == 'refusal':
                return "Sorry, I can't help with that one."
            if resp.stop_reason != 'tool_use':
                text = '\n'.join(b.text for b in resp.content if b.type == 'text').strip()
                if resp.stop_reason == 'max_tokens':
                    text += '\n\n(cut off: answer was too long)'
                return text or '(no answer)'
            results = []
            for block in resp.content:
                if block.type != 'tool_use':
                    continue
                t0 = time.time()
                try:
                    out = run_tool(self.session, block.name, block.input)
                    text = json.dumps(out, default=str, separators=(',', ':'))
                    if len(text) > MAX_RESULT_CHARS:
                        text = text[:MAX_RESULT_CHARS] + '...(truncated; ask for less)'
                    is_error = isinstance(out, dict) and 'error' in out
                except Exception as e:  # report to the model, keep going
                    text, is_error = f'{type(e).__name__}: {e}', True
                self.log('tool', block.name, block.input, f'{len(text)} chars',
                         f'{time.time() - t0:.1f}s', 'ERROR' if is_error else '')
                results.append({'type': 'tool_result', 'tool_use_id': block.id,
                                'content': text, 'is_error': is_error})
            self.messages.append({'role': 'user', 'content': results})
        return 'That took too many steps; try asking something narrower.'

    def _count(self, u):
        self.usage['calls'] += 1
        self.usage['input'] += u.input_tokens or 0
        self.usage['cache_read'] += u.cache_read_input_tokens or 0
        self.usage['cache_write'] += u.cache_creation_input_tokens or 0
        self.usage['output'] += u.output_tokens or 0

    # List price per million tokens (Foundry bills at API rates). Sonnet 5.5
    # unless SCOUT_CHAT_PRICES="input,cache_write,cache_read,output" says otherwise.
    PRICE = dict(zip(('input', 'cache_write', 'cache_read', 'output'),
                     map(float, os.environ.get('SCOUT_CHAT_PRICES', '2,2.5,0.2,10').split(','))))

    def cost(self):
        return sum(self.usage[k] * p for k, p in self.PRICE.items()) / 1e6
