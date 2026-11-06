"""Run the regression cases and write a report to judge.

  python -m evals.run                     # every case
  python -m evals.run --only finals_dq,hang_works
  python -m evals.run --tags history --repeat 3
  python -m evals.run --accept evals/results/<stamp> id1 id2   # save those answers as known good

Writes evals/results/<stamp>/results.jsonl and report.md. Each case gets a
fresh chat as the default asker (4003data, team 4003, "Justin B"). The
regexes in cases.py give a quick PASS/CHECK per case; the real grade comes
from reading report.md against the reference queries and expected facts.
"""
import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import live_sql  # noqa: E402
from agent import DEPLOYMENT, Chat, make_client  # noqa: E402
from evals.cases import CASES  # noqa: E402
from tools import TOOLSET, Session  # noqa: E402

GOOD = HERE / 'good_answers.json'
KEY, TEAM, NAME = '4003data', 4003, 'Justin B'


def _good():
    return json.loads(GOOD.read_text()) if GOOD.exists() else {}


def reference(case):
    s = Session(KEY, case.get('ref_event') or case.get('event', '2026miwmi'), NAME, TEAM)
    return [{'sql': ' '.join(q.split()), 'result': live_sql.run(s, q)} for q in case.get('ref', [])]


def check(case, answer):
    miss = [p for p in case.get('must', []) if not re.search(p, answer, re.I)]
    bad = [p for p in case.get('must_not', []) if re.search(p, answer, re.I)]
    return ('PASS' if not miss and not bad else 'CHECK'), miss, bad


def ask(client, case, lock):
    calls = []
    session = Session(KEY, case.get('event', '2026miwmi'), NAME, TEAM)
    chat = Chat(client, session, log=lambda *a: calls.append([a[1], a[2]]) if a and a[0] == 'tool' else None)
    t0 = time.time()
    try:
        answer = chat.ask(case['q'])
    except Exception as e:
        answer = f'(error: {type(e).__name__}: {e})'
    status, miss, bad = check(case, answer)
    with lock:
        print(f"{status:5} {case['id']}  ({time.time() - t0:.0f}s, ${chat.cost():.3f})", flush=True)
    return {'id': case['id'], 'q': case['q'], 'answer': answer, 'tool_calls': calls,
            'status': status, 'missing': miss, 'flagged': bad, 'cost': round(chat.cost(), 4),
            'seconds': round(time.time() - t0, 1), 'usage': chat.usage}


def report(out, cases, results, refs):
    good = _good()
    by_id = {c['id']: c for c in cases}
    lines = [f'# Eval run {out.name}', '',
             f'Model `{DEPLOYMENT}`, toolset `{TOOLSET}`. '
             f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} pass the regex smoke check; "
             f"total ${sum(r['cost'] for r in results):.2f}.", '',
             '| Case | Smoke | s | $ |', '|---|---|---|---|']
    lines += [f"| {r['id']} | {r['status']} | {r['seconds']} | {r['cost']} |" for r in results]
    for r in results:
        c = by_id[r['id']]
        lines += ['', '---', f"## {r['id']}: {r['status']}", '', f"**Q:** {c['q']}", '',
                  f"**Stress:** {c.get('stress', '')}", '', '**Expect:**']
        lines += [f'- {e}' for e in c.get('expect', [])]
        if c.get('judge'):
            lines += ['', f"**Judge:** {c['judge']}"]
        if r['missing'] or r['flagged']:
            lines += ['', f"**Smoke:** missing {r['missing']}, flagged {r['flagged']}"]
        lines += ['', '**Reference:**']
        for ref in refs[r['id']]:
            lines += ['```', ref['sql'][:600], json.dumps(ref['result'], default=str)[:1500], '```']
        lines += ['', f"**Tools:** {json.dumps(r['tool_calls'], default=str)[:1500]}", '',
                  '**Answer:**', '', r['answer']]
        if r['id'] in good:
            lines += ['', f"**Known good ({good[r['id']]['date']}):**", '', good[r['id']]['answer']]
    (out / 'report.md').write_text('\n'.join(lines) + '\n')


def accept(results_dir, ids):
    good = _good()
    rows = [json.loads(line) for line in (Path(results_dir) / 'results.jsonl').read_text().splitlines()]
    for r in rows:
        if r['id'] in ids:
            good[r['id']] = {'answer': r['answer'], 'date': Path(results_dir).name,
                             'tool_calls': r['tool_calls']}
            print('accepted', r['id'])
    GOOD.write_text(json.dumps(good, indent=1, sort_keys=True) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', help='comma-separated case ids')
    ap.add_argument('--tags', help='comma-separated; a case runs if it has any of them')
    ap.add_argument('--repeat', type=int, default=1, help='ask each case this many times')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--accept', nargs='+', metavar=('RESULTS_DIR', 'ID'),
                    help='save these answers from a run as known good')
    args = ap.parse_args()
    if args.accept:
        accept(args.accept[0], set(args.accept[1:]))
        return

    cases = CASES
    if args.only:
        want = set(args.only.split(','))
        unknown = want - {c['id'] for c in cases}
        if unknown:
            sys.exit(f'unknown case ids: {sorted(unknown)}')
        cases = [c for c in cases if c['id'] in want]
    if args.tags:
        tags = set(args.tags.split(','))
        cases = [c for c in cases if tags & set(c.get('tags', []))]

    out = HERE / 'results' / datetime.now().strftime('%Y%m%d-%H%M%S')
    out.mkdir(parents=True)
    refs = {c['id']: reference(c) for c in cases}
    client, lock = make_client(), threading.Lock()
    jobs = [c for c in cases for _ in range(args.repeat)]
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda c: ask(client, c, lock), jobs))
    with open(out / 'results.jsonl', 'w') as f:
        for r in results:
            f.write(json.dumps(r, default=str) + '\n')
    report(out, cases, results, refs)
    print(f"\n{sum(r['status'] == 'PASS' for r in results)}/{len(results)} smoke pass, "
          f"${sum(r['cost'] for r in results):.2f}. Report: {out / 'report.md'}")


if __name__ == '__main__':
    main()
