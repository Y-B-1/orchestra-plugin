"""lean.py owns COMMIT|A..B -- PATH...: exits 0 when every file the commit(s) changed is inside the unit (docs/hooks.md)."""
import re, subprocess, sys


def _git(*args):
    p = subprocess.run(['git', *args], capture_output=True)
    if p.returncode:
        raise ValueError(p.stderr.decode(errors='replace').strip() or f'git {args[0]} failed')
    return p.stdout.decode(errors='replace')


def pattern(path):
    """A regex for one unit path: a folder prefix ending in /, a glob (** crosses folders, * and ? do not), or a file."""
    if path.endswith('/'):
        return re.compile(re.escape(path) + '.*', re.S)
    out, i = '', 0
    while i < len(path):
        if path.startswith('**/', i):
            out, i = out + '(?:.*/)?', i + 3
        elif path.startswith('**', i):
            out, i = out + '.*', i + 2
        elif path[i] == '*':
            out, i = out + '[^/]*', i + 1
        elif path[i] == '?':
            out, i = out + '[^/]', i + 1
        else:
            out, i = out + re.escape(path[i]), i + 1
    return re.compile(out)


def changed(commit):
    """Files the commit changed against its first parent; a rename counts as both its paths."""
    parent = commit + '^' if _git('rev-list', '--parents', '-n1', commit).split()[1:] else _git('hash-object', '-t', 'tree', '/dev/null').strip()
    return [f for f in _git('diff-tree', '-r', '--no-renames', '--name-only', '-z', parent, commit).split('\0') if f]


def main(args):
    if '--' not in args or args.index('--') != 1 or len(args) < 3:
        print('owns: usage: lean.py owns COMMIT|A..B -- PATH...', file=sys.stderr)
        return 2
    spec, paths = args[0], [p for p in args[2:] if p]
    try:
        commits = _git('rev-list', '--reverse', spec).split() if '..' in spec else [_git('rev-parse', '--verify', '-q', spec + '^{commit}').strip()]
        if not all(commits):
            raise ValueError(f'not a commit: {spec}')
        patterns = [pattern(p) for p in paths]
        outside = []
        for c in commits:
            outside += [f for f in changed(c) if not any(r.fullmatch(f) for r in patterns) and f not in outside]
    except ValueError as e:
        print(f'owns: {e}', file=sys.stderr)
        return 2
    print('\n'.join(outside))
    return 1 if outside else 0
