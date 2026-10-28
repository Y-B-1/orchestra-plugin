"""Orchestra: `lean.py check`, a pre-PR scan of the branch diff (see docs/check.md)."""
import fnmatch, json, re, sys
from pathlib import Path

from lean import default_branch, git, usage

REASON = 'needs a reason in the report'
LINE_RULES = [  # (kind, regex on an added line, message)
    ('test-weakened', r'\.skip\(|\.only\(|\bxit\(|\bxdescribe\(|@pytest\.mark\.skip|@unittest\.skip|eslint-disable|@ts-ignore'
     r'|@ts-expect-error|# noqa|# type: ignore', REASON),
    ('self-mock', r'''\b(?:vi|jest)\.mock\(\s*['"]\.''', 'mocks an in-repo module; test the real one'),
    ('debug', r'console\.log\(|debugger;|\[DEBUG-|breakpoint\(\)|pdb\.set_trace', 'leftover debug code'),
    ('secret', r'AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_\w{36}|github_pat_\w{22,}|\bsk-[\w-]{20,}|xox[bp]-[\w-]{10,}',
     'looks like a credential (value not shown)'),
]
WEAK_FILES = r'(^|/)(eslint\.config\.[^/]*|\.eslintrc[^/]*|tsconfig[^/]*\.json|setup\.cfg)$|\.snap$|(^|/)__snapshots__/|^\.github/workflows/'
SENSITIVE = {'auth', 'login', 'session', 'token', 'secret', 'password', 'payment', 'billing', 'permission', 'role', 'crypto',
             'webhook', 'middleware', 'migration', 'migrations'}
KINDS = ('size', 'test-weakened', 'self-mock', 'debug', 'rules', 'sensitive', 'secret')
TIMEOUT = re.compile(r'timeout\W{0,4}(\d+)', re.I)


def check_base(base, cwd):
    if base:
        return git('rev-parse', '--verify', '--quiet', base + '^{commit}', cwd=cwd)
    d = default_branch(cwd)
    return git('merge-base', 'HEAD', 'origin/' + d, cwd=cwd) or git('merge-base', 'HEAD', d, cwd=cwd)


def changed_files(base, cwd):
    """{path: {'add': [(line, text)], 'rem': [text], 'deleted': bool}}: the working tree against base, untracked included."""
    files, cur, n = {}, None, 0
    for ln in git('-c', 'core.quotepath=off', 'diff', '-U0', '--no-renames', base, cwd=cwd).split('\n'):
        if ln.startswith('diff --git '):
            cur = files.setdefault(ln.rsplit(' b/', 1)[1], {'add': [], 'rem': [], 'deleted': False})
            n = 0
        elif cur is None:
            continue
        elif ln.startswith('deleted file mode'):
            cur['deleted'] = True
        elif ln.startswith('@@'):
            n = int(re.search(r'\+(\d+)', ln).group(1))
        elif n and ln.startswith('+'):
            cur['add'].append((n, ln[1:]))
            n += 1
        elif n and ln.startswith('-'):
            cur['rem'].append(ln[1:])
    for path in filter(None, git('ls-files', '-o', '--exclude-standard', cwd=cwd).split('\n')):
        text = read_text(path, cwd) or ''
        files[path] = {'add': list(enumerate(text.splitlines(), 1)), 'rem': [], 'deleted': False}
    return files


def read_text(path, cwd):
    try:
        return (Path(cwd or '.') / path).read_text()
    except (OSError, UnicodeDecodeError):  # gone, or binary
        return None


def over_budget(path, text, base, max_lines, cwd):
    """A message when a text source file grew past the budget in this diff, else None."""
    name = path.rsplit('/', 1)[-1]
    if re.search(r'\.lock$|^package-lock\.json$|\.min\.|\.(patch|diff|svg|csv|tsv|snap)$', name) or {'dist', 'build'} & set(path.split('/')[:-1]):
        return None
    waivers = read_text('.orchestra/budget-waivers', cwd) or ''
    if '\0' in text or re.search('generated', '\n'.join(text.splitlines()[:5]), re.I) or any(
            fnmatch.fnmatch(path, w.split()[0]) for w in waivers.splitlines() if w.split() and not w.startswith('#')):
        return None
    now, was = len(text.strip().splitlines()), len(git('show', f'{base}:{path}', cwd=cwd).splitlines())
    if now > max_lines and now > was:
        return f'{was} lines at base, {now} now, over the {max_lines} budget'


def check(base, max_lines=500, cwd=None):
    sha = check_base(base, cwd)
    if not sha:
        return None
    pkgs = {p.split('/')[1 if p.startswith('src/') else 0].removesuffix('.py') for p in git('ls-files', '-co', '--exclude-standard', '*.py', cwd=cwd).split('\n') if p}
    out = []

    def add(kind, path, line, msg):
        out.append({'kind': kind, 'path': path, 'line': line, 'message': msg})

    for path, info in changed_files(sha, cwd).items():
        text = None if info['deleted'] else read_text(path, cwd)
        msg = text and over_budget(path, text, sha, max_lines, cwd)
        if msg:
            add('size', path, None, msg)
        if re.search(WEAK_FILES, path):
            add('test-weakened', path, None, 'test, CI or lint config changed; ' + REASON)
        if path.endswith('pyproject.toml') and text:
            lines = text.splitlines()
            for n, _ in info['add']:
                head = next((s for s in reversed(lines[:n]) if s.startswith('[')), '')
                if head.startswith(('[tool.ruff', '[tool.mypy')):
                    add('test-weakened', path, n, 'lint or type config changed; ' + REASON)
                    break
        old = [int(m.group(1)) for t in info['rem'] for m in [TIMEOUT.search(t)] if m]
        for n, t in info['add']:
            m = TIMEOUT.search(t)
            if m and old and int(m.group(1)) > min(old):
                add('test-weakened', path, n, 'test timeout raised; ' + REASON)
        if path.split('/')[-1] in ('AGENTS.md', 'CLAUDE.md', 'CONTEXT.md') or path.startswith('.claude/'):
            add('rules', path, None, 'rules changed; the reviewer judges with the base version')
        segments = path.lower().split('/')
        if {t for s in segments for t in re.split(r'[^a-z0-9]+', s)} & SENSITIVE or any(s.startswith('.env') for s in segments):
            add('sensitive', path, None, 'security-relevant path; the reviewer loads the security lens')
        is_test = re.search(r'(^|/)(tests?/|test_[^/]*$|[^/]*\.(test|spec)\.)', path)
        prose = path.endswith(('.md', '.txt', '.rst'))  # docs quote these patterns; only secrets count there
        for n, t in info['add']:
            for kind, rx, why in LINE_RULES:
                if (kind == 'secret' or not prose) and re.search(rx, t):
                    add(kind, path, n, why)
            m = re.search(r'''\bpatch\(\s*['"]([\w.]+)''', t)
            if m and '.' in m.group(1) and m.group(1).split('.')[0] in pkgs:
                add('self-mock', path, n, 'mocks an in-repo module; test the real one')
            if path.endswith('.py') and not is_test and 'DEBUG' in t and re.search(r'\bprint\(', t):
                add('debug', path, n, 'leftover debug code')
    out.sort(key=lambda f: (KINDS.index(f['kind']), f['path'], f['line'] or 0))
    return {'base': sha, 'findings': out, 'counts': {k: sum(f['kind'] == k for f in out) for k in KINDS if any(f['kind'] == k for f in out)}}


def run_check(args):
    base, max_lines, as_json, rest = None, 500, False, iter(args)
    for a in rest:
        if a == '--json':
            as_json = True
        elif a in ('--base', '--max-lines'):
            v = next(rest, '')
            if a == '--base' and v:
                base = v
            elif a == '--max-lines' and v.isdigit():
                max_lines = int(v)
            else:
                return usage()
        else:
            return usage()
    result = check(base, max_lines)
    if result is None:
        print('check: no base found (is this a git repo, and does --base exist?)', file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(result))
        return 0
    for f in result['findings']:
        print(f"{f['kind']} {f['path']}{':%d' % f['line'] if f['line'] else ''} {f['message']}")
    counts = ', '.join(f'{k} {n}' for k, n in result['counts'].items())
    print(f"{len(result['findings'])} findings ({counts})" if counts else 'no findings')
    return 0
