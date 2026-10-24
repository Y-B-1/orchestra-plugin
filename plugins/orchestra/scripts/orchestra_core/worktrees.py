"""Leftover Orchestra worktrees under .claude/worktrees, listed from git with their landed and clean state. Read-only:
the engine runs `git worktree list` and `git status` here and prints the removal commands; it never adds or removes one."""
import shlex
import subprocess
from pathlib import Path

SUBDIR = Path('.claude/worktrees')


def _entries(repo):
    """(path, head, branch or None) per linked worktree, from `git worktree list --porcelain`."""
    out = subprocess.run(['git', '-C', str(repo), 'worktree', 'list', '--porcelain'], capture_output=True, text=True)
    if out.returncode != 0:
        return []
    found, current = [], {}
    for line in out.stdout.splitlines() + ['']:
        if not line:
            if current.get('worktree'):
                found.append(current)
            current = {}
            continue
        key, _, value = line.partition(' ')
        current[key] = value
    return [(e['worktree'], e.get('HEAD', ''), e['branch'][len('refs/heads/'):] if e.get('branch', '').startswith('refs/heads/')
             else None) for e in found]


def _clean(path):
    out = subprocess.run(['git', '-C', path, 'status', '--porcelain'], capture_output=True, text=True)
    return out.returncode == 0 and not out.stdout.strip()


def listing(engine, state):
    """The worktrees under <repo>/.claude/worktrees: branch, the card it serves (by reported sha), landed and clean, and
    `git worktree remove` for each landed clean one."""
    root = (Path(engine.repo).resolve() / SUBDIR)
    cards = {t['report_sha']: t['id'] for t in state['tasks'].values() if t.get('report_sha')}
    items, remove = [], []
    for path, head, branch in _entries(engine.repo):
        real = Path(path).resolve()
        if real.parent != root:
            continue
        landed = bool(head) and engine._landed(head, state)
        clean = _clean(path)
        items.append(dict(path=str(real), branch=branch, head=head, card=cards.get(head), landed=landed, clean=clean))
        if landed and clean:
            remove.append('git worktree remove ' + shlex.quote(str(real)))
    return dict(worktrees=items, remove=remove, leftover=len(items))
