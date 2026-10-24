"""CLI helpers: the refusal log and the stored board signature."""
import json
import os
from pathlib import Path
import shlex
import time

LOG = 'refusals.jsonl'
KEEP = 200


def without_lease(argv):
    """argv with every --lease value removed, in both `--lease V` and `--lease=V` spellings."""
    out, skip = [], False
    for item in argv:
        if skip:
            skip = False
        elif item == '--lease':
            skip = True
        elif not item.startswith('--lease='):
            out.append(item)
    return out


def log_refusal(state, argv, error):
    """Append one {at, command, error} line for a command that exited 2; keep the newest 200. Never raises, never creates `state`."""
    try:
        state = Path(state)
        if not state.is_dir():
            return
        path = state/LOG
        line = json.dumps(dict(at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                               command=shlex.join(without_lease(argv)), error=str(error)))
        lines = path.read_text().splitlines() if path.exists() else []
        lines = (lines+[line])[-KEEP:]
        temporary = path.with_name(LOG+'.%d.tmp' % os.getpid())
        temporary.write_text('\n'.join(lines)+'\n')
        os.replace(temporary, path)
    except Exception:  # a failing log never changes the exit code or the error text
        pass


def read_refusals(state, last):
    """The newest `last` log entries, oldest first; read-only."""
    path = Path(state)/LOG
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries[-last:] if last > 0 else []


def store_seen(state, signature):
    """Record the board signature whose delta line was just printed."""
    try:
        path = Path(state)/'board-seen.json'
        temporary = path.with_name('board-seen.json.%d.tmp' % os.getpid())
        temporary.write_text(json.dumps({'signature': signature}))
        os.replace(temporary, path)
    except OSError:
        pass
