"""Which e2e commands are scoped (see gate.py): a scope flag or a test file in the command or in the package script it runs."""
import re, shlex, sys
from pathlib import Path

import lean

SCOPE_FLAGS = ('--changed-since', '--grep', '-g', '--tag', '--last-failed', '--shard', '--only-changed', '--spec')
VALUE_FLAGS = ('--config', '-c', '--project')
TEST_FILE = re.compile(r'\.(e2e|spec|test|cy)\.\w+$')
RUNNERS = ('npm', 'pnpm', 'yarn', 'bun')


def script_words(cmd, cwd, depth=0):
    """cmd, with a package script replaced by the words of its package.json text; None when the script is unknown."""
    if len(cmd) < 2 or cmd[0] not in RUNNERS:
        return cmd
    if cmd[1] in ('run', 'run-script'):
        rest = cmd[2:]
    elif cmd[0] != 'npm' or cmd[1] == 'test':
        rest = cmd[1:]
    else:
        return cmd
    scripts = lean.read_json(Path(cwd or '.') / 'package.json').get('scripts')
    text = scripts.get(rest[0]) if rest and isinstance(scripts, dict) else None
    if not isinstance(text, str) or depth > 3:
        return None
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return None
    if any(set(w) <= set(';&|()') for w in words):
        return None  # a chained or substituted script: one scope flag proves nothing about the rest
    extra = rest[1:]
    if cmd[0] == 'npm':  # npm keeps flags before `--` for itself; only what follows `--` reaches the script
        extra = extra[extra.index('--') + 1:] if '--' in extra else []
    return script_words(words + [a for a in extra if a != '--'], cwd, depth + 1)


def e2e_scoped(cmd, cwd=None):
    skip = False
    for a in script_words(cmd, cwd) or ():
        if skip:
            skip = False
        elif a in VALUE_FLAGS:
            skip = True
        elif a.split('=')[0] in SCOPE_FLAGS or (not a.startswith('-') and TEST_FILE.search(a)):
            return True
    return False


def nothing_to_gate(cwd):
    """The default branch's name when HEAD has no commits beyond it (reusing the Stop hook's count), else ''."""
    d = lean.default_branch(cwd)
    exists = any(lean.git('rev-parse', '--verify', '--quiet', r + d + '^{commit}', cwd=cwd) for r in ('refs/remotes/origin/', 'refs/heads/'))
    return d if exists and not lean.commits_ahead(cwd, '') else ''


def refuse_empty(cwd):
    d = nothing_to_gate(cwd)
    if d:
        print(f'gate: no commits beyond {d}: nothing to gate yet; commit first', file=sys.stderr)
    return bool(d)
