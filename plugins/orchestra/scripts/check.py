"""Orchestra: `lean.py check`, a pre-PR scan of the branch diff (see docs/check.md)."""
import fnmatch, json, re, subprocess, sys
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
SENSITIVE = {'auth', 'oauth', 'login', 'session', 'token', 'secret', 'password', 'payment', 'billing', 'permission', 'role', 'crypto',
             'webhook', 'middleware', 'migration'}  # singular: words() strips a trailing s
KINDS = ('size', 'test-weakened', 'self-mock', 'debug', 'rules', 'sensitive', 'secret')
TIMEOUT = re.compile(r'timeout\W{0,4}(\d+)', re.I)


def gitb(*args, cwd=None):
    """Git stdout decoded with errors='replace' and not stripped; '' on failure."""
    try:
        p = subprocess.run(['git', '--literal-pathspecs', *args], cwd=cwd, capture_output=True)
    except OSError:
        return ''
    return p.stdout.decode('utf-8', 'replace') if p.returncode == 0 else ''


def nul_list(text):
    return [x for x in text.split('\0') if x]


def check_base(base, cwd):
    if base:
        return git('rev-parse', '--verify', '--quiet', base + '^{commit}', cwd=cwd)
    d = default_branch(cwd)
    return git('merge-base', 'HEAD', 'origin/' + d, cwd=cwd) or git('merge-base', 'HEAD', d, cwd=cwd)


def changed_files(base, cwd):
    """{path: {'add': [(line, text)], 'rem': [text], 'deleted': bool, 'old': path at base}}: the working tree against base, untracked included."""
    files = {}
    parts = nul_list(gitb('diff', '--raw', '-z', '-M', '--no-abbrev', base, cwd=cwd))
    i = 0
    while i < len(parts):  # ':mode mode sha sha STATUS' then one path, or two for a rename or copy
        status = parts[i].split(' ')[-1][:1]
        paths = parts[i + 1:i + (3 if status in 'RC' else 2)]
        i += len(paths) + 1
        path = paths[-1]
        info = files[path] = {'add': [], 'rem': [], 'deleted': status == 'D', 'old': paths[0] if status == 'R' else path}
        n = 0
        for ln in gitb('diff', '-U0', '-M', '--no-color', base, '--', *paths, cwd=cwd).split('\n'):
            if ln.startswith('@@'):
                n = int(re.search(r'\+(\d+)', ln).group(1))
            elif n and ln.startswith('+'):
                info['add'].append((n, ln[1:]))
                n += 1
            elif n and ln.startswith('-'):
                info['rem'].append(ln[1:])
    for path in nul_list(gitb('ls-files', '-o', '-z', '--exclude-standard', cwd=cwd)):
        text = read_text(path, cwd) or ''
        files[path] = {'add': [] if '\0' in text else list(enumerate(text.splitlines(), 1)), 'rem': [], 'deleted': False, 'old': path}
    return files


def read_text(path, cwd):
    try:
        return (Path(cwd or '.') / path).read_bytes().decode('utf-8', 'replace')
    except OSError:  # gone
        return None


GENERATED = re.compile(r'^\s*(#|//|/\*|\*|<!--|--|;)\s*.*(@generated|\bgenerated (by|file)\b|\b(is|was|are) (auto-?)?generated\b|\bauto-?generated\b|do not edit)', re.I)


def over_budget(path, old, text, base, max_lines, cwd):
    """A message when a text source file grew past the budget in this diff, else None."""
    name = path.rsplit('/', 1)[-1]
    if re.search(r'\.lock$|^package-lock\.json$|\.min\.|\.(patch|diff|svg|csv|tsv|snap)$', name) or {'dist', 'build'} & set(path.split('/')[:-1]):
        return None
    waivers = read_text('.orchestra/budget-waivers', cwd) or ''
    if '\0' in text or any(GENERATED.match(ln) for ln in text.splitlines()[:5]) or any(
            fnmatch.fnmatch(path, w.split()[0]) for w in waivers.splitlines() if w.split() and not w.startswith('#')):
        return None
    now, was = len(text.strip().splitlines()), len(gitb('show', f'{base}:{old}', cwd=cwd).splitlines())
    if now > max_lines and now > was:
        return f'{was} lines at base, {now} now, over the {max_lines} budget'


def words(path):
    """Lowercase words of a path: split on separators and camelCase, trailing s stripped."""
    ws = re.split(r'[^A-Za-z0-9]+', re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', path))
    return {w.lower().removesuffix('s') if not w.lower().endswith('ss') else w.lower() for w in ws if w}


def raised_timeouts(info):
    """Added timeout lines whose same line (apart from the number) was removed with a smaller number."""
    old = {}
    for t in info['rem']:
        m = TIMEOUT.search(t)
        if m:
            old.setdefault(TIMEOUT.sub('', t).strip(), []).append(int(m.group(1)))
    for n, t in info['add']:
        m = TIMEOUT.search(t)
        if m and any(int(m.group(1)) > v for v in old.get(TIMEOUT.sub('', t).strip(), [])):
            yield n


def check(base, max_lines=500, cwd=None):
    cwd = git('rev-parse', '--show-toplevel', cwd=cwd)
    sha = cwd and check_base(base, cwd)
    if not sha:
        return None
    pkgs = {p.split('/')[1 if p.startswith('src/') else 0].removesuffix('.py') for p in nul_list(gitb('ls-files', '-co', '-z', '--exclude-standard', cwd=cwd)) if p.endswith('.py')}
    out = []

    def add(kind, path, line, msg):
        out.append({'kind': kind, 'path': path, 'line': line, 'message': msg})

    for path, info in changed_files(sha, cwd).items():
        text = None if info['deleted'] else read_text(path, cwd)
        msg = text and over_budget(path, info['old'], text, sha, max_lines, cwd)
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
        for n in raised_timeouts(info):
            add('test-weakened', path, n, 'test timeout raised; ' + REASON)
        if path.split('/')[-1] in ('AGENTS.md', 'CLAUDE.md', 'CONTEXT.md') or path.startswith('.claude/'):
            add('rules', path, None, 'rules changed; the reviewer judges with the base version')
        if words(path) & SENSITIVE or any(s.startswith('.env') for s in path.lower().split('/')):
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
