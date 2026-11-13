"""Which e2e commands are scoped (see gate.py): a scope flag or a test file in the command or in the package script it runs."""
import os, re, shlex, sys
from pathlib import Path

import lean

# --shard 1/1 is a full run and --last-failed reruns nothing new, so neither counts as a scope.
SCOPE_FLAGS = ('--changed-since', '--grep', '-g', '--tag', '--only-changed', '--spec')
CONFIGS = ('e2e.config.ts', 'e2e.config.mts', 'e2e.config.js', 'e2e.config.mjs')
VALUE_FLAGS = ('--config', '-c', '--project')
TEST_FILE = re.compile(r'\.(e2e|spec|test|cy)\.\w+$')
RUNNERS = ('npm', 'pnpm', 'yarn', 'bun')


def script_words(cmd, cwd, depth=0):
    """cmd, with a package script replaced by the words of its package.json text; None when the script is unknown."""
    if len(cmd) < 2 or cmd[0] not in RUNNERS:
        return cmd
    if cmd[1] in ('run', 'run-script'):
        rest = cmd[2:]
    elif cmd[1] in ('exec', 'dlx'):
        return cmd  # a binary, not a script
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


def scopes(cmd, cwd=None):
    """The scope flags (and 'file' for a test file path) the command carries, after its package script is read."""
    found, skip = set(), False
    for a in script_words(cmd, cwd) or ():
        if skip:
            skip = False
        elif a in VALUE_FLAGS:
            skip = True
        elif a.split('=')[0] in SCOPE_FLAGS:
            found.add(a.split('=')[0])
        elif not a.startswith('-') and TEST_FILE.search(a):
            found.add('file')
    return found


def e2e_scoped(cmd, cwd=None):
    return bool(scopes(cmd, cwd))


def runner_words(words):
    """The words from the runner name on: npx, bunx, pnpm exec/dlx and their options are dropped, and an @version suffix too."""
    if words[:1] in (['npx'], ['bunx']):
        words = words[1:]
    elif words[:1] == ['pnpm'] and words[1:2] in (['exec'], ['dlx']):
        words = words[2:]
    while words and words[0].startswith('-'):
        words = words[1:]
    return [words[0].split('@')[0]] + words[1:] if words else []


def config_path(words, cwd):
    """The e2e config the runner reads: the --config/-c path, else the first e2e.config.* found from cwd up to the repository root."""
    for i, w in enumerate(words):
        if w in ('--config', '-c') and i + 1 < len(words):
            return Path(cwd or '.') / words[i + 1]
        if w.startswith('--config='):
            return Path(cwd or '.') / w[9:]
    here = Path(cwd or '.').resolve()
    top = lean.git('rev-parse', '--show-toplevel', cwd=cwd)
    for d in (here, *here.parents):
        for name in CONFIGS:
            if (d / name).is_file():
                return d / name
        if str(d) == top:
            break
    return None


def filters_missing(cmd, cwd=None):
    """The e2e config path (as given, or relative to cwd) when the agentic runner (`e2e run`) is scoped only by --changed-since
    and that config has no `filters` key (a plain text search), else ''. Without filters the flag leaves nothing out."""
    words = runner_words(script_words(cmd, cwd) or [])
    if words[:2] != ['e2e', 'run'] or scopes(cmd, cwd) != {'--changed-since'}:
        return ''
    cfg = config_path(words, cwd)
    try:
        text = cfg.read_text(errors='replace') if cfg else 'filters'
    except OSError:
        return ''
    return '' if 'filters' in text else os.path.relpath(os.path.realpath(cfg), os.path.realpath(cwd or '.'))


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
