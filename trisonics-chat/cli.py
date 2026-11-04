"""Local prototype: chat with the scouting agent in a terminal.

  source .venv/bin/activate
  python cli.py                       # interactive, 2026miwmi / 4003data
  python cli.py -q "Who has the best auto?"   # one question
  python cli.py --batch questions.txt         # each line a fresh chat
"""
import argparse
import sys
import time

from agent import Chat, make_client
from tools import Session


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--event', default='2026miwmi')
    ap.add_argument('--key', default='4003data', help='secret team key')
    ap.add_argument('--name', default='Justin B', help='who is asking')
    ap.add_argument('--team', type=int, default=4003)
    ap.add_argument('-q', '--question')
    ap.add_argument('--batch', help='file with one question per line')
    ap.add_argument('--quiet', action='store_true', help='hide tool calls')
    args = ap.parse_args()

    session = Session(args.key, args.event, args.name, args.team)
    client = make_client()
    log = (lambda *_: None) if args.quiet else \
        (lambda *a: print('   ·', *a, file=sys.stderr))

    def one(chat, q):
        t0 = time.time()
        answer = chat.ask(q)
        u = chat.usage
        print(f'\n{answer}\n')
        print(f'   [{time.time() - t0:.0f}s, {u["calls"]} calls, in {u["input"]} '
              f'+ cache {u["cache_read"]}r/{u["cache_write"]}w, out {u["output"]}, '
              f'${chat.cost():.3f} so far]', file=sys.stderr)

    if args.batch:
        total = 0.0
        for q in open(args.batch):
            q = q.strip()
            if not q or q.startswith('#'):
                continue
            print(f'\n=== {q}')
            chat = Chat(client, session, log)
            one(chat, q)
            total += chat.cost()
        print(f'\nTotal ${total:.2f}', file=sys.stderr)
        return
    chat = Chat(client, session, log)
    if args.question:
        one(chat, args.question)
        return
    print(f'Scouting chat for {args.event} as {args.name}. Ctrl-D to quit.')
    while True:
        try:
            q = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q:
            one(chat, q)


if __name__ == '__main__':
    main()
