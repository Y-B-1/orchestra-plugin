"""Orchestra: `lean.py check`, a pre-PR scan of the branch diff (see docs/check.md)."""
import collections, fnmatch, json, re, subprocess, sys
from pathlib import Path

from lean import default_branch, git, usage

REASON = 'needs a reason in the report'
# Suppressions count in any file; skips that collide with application code (`rows.skip(n)`) count in test files only.
SUPPRESS = (r'eslint-disable|@ts-ignore|@ts-expect-error|@ts-nocheck|#\s*noqa|# ruff: noqa|# type: ignore|pylint: disable|# pragma: no cover'
            r'|biome-ignore|istanbul ignore|nolint|\bxit\(|\bxdescribe\(|\bxtest\(|\bfit\(|\bfdescribe\(|@pytest\.mark\.(skip|xfail)|@unittest\.(skip|expectedFailure)'
            r'|\bskipTest\(|\bt\.Skip(Now)?\(|#\[ignore\]|@Disabled|@Ignore\b')
TEST_ONLY = r'\.skip\(|\.only\(|\.skip\.|\.skipIf\(|\.fixme\(|\.todo\('
LINE_RULES = [  # (kind, regex on an added line, message)
    ('test-weakened', SUPPRESS, REASON),
    ('self-mock', r'''\b(?:vi|jest)\.(?:mock|doMock|unstable_mockModule)\(\s*(?:import\(\s*)?['"`](?:\.|@/|~/|src/)''', 'mocks an in-repo module; test the real one'),
    ('debug', r'console\.(?:log|debug)\(|(?:^|[\s;{])debugger\s*(?:;|$)|\[DEBUG-|breakpoint\(\)|pdb\.set_trace', 'leftover debug code'),
    ('secret', r'(?:AKIA|ASIA)[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|gh[pousr]_\w{36}|github_pat_\w{22,}|\bsk-[\w-]{20,}'
     r'|\b[sr]k_live_\w{20,}|whsec_\w{20,}|xox[abeprs]-[\w-]{10,}|xapp-\d-[\w-]{10,}|AIza[\w-]{35}|npm_\w{36}',
     'looks like a credential (value not shown)'),
]
WEAK_FILES = (r'(^|/)(eslint\.config\.[^/]*|\.eslintrc[^/]*|\.eslintignore|tsconfig[^/]*\.json|setup\.cfg|ruff\.toml|\.ruff\.toml|mypy\.ini|\.flake8|pytest\.ini'
              r'|tox\.ini|pyrightconfig\.json|biome\.jsonc?|(vitest|jest|playwright)[^/]*\.config\.[^/]*|\.pre-commit-config\.yaml|\.gitlab-ci\.yml'
              r'|\.golangci\.ya?ml)$|\.snap$|(^|/)__snapshots__/|^\.github/workflows/|^\.circleci/|^scripts/check\.sh$')
RULES_FILES = (r'(^|/)(AGENTS|CLAUDE|CONTEXT)\.md$|(^|/)\.(claude|agents)/|\.cursor/rules/|(^|/)\.cursorrules$'
               r'|^\.github/copilot-instructions\.md$|^docs/AGENT-MEMORY\.md$|^\.orchestra/budget-waivers$')
TOOL_SECTION = ('[tool.ruff', '[tool.mypy', '[tool.pytest', '[tool.coverage', '[tool.pyright', '[tool.pylint')
SENSITIVE = {'auth', 'oauth', 'login', 'session', 'token', 'secret', 'password', 'payment', 'billing', 'permission', 'role', 'crypto',
             'webhook', 'middleware', 'migration', 'jwt', 'csrf', 'rbac', 'acl', 'security', 'signin', 'signup', 'admin', 'stripe'}  # singular: words() strips a trailing s
SENSITIVE_PREFIX = ('auth', 'polic', 'encrypt', 'credential')
NOT_AUTH = {'author', 'authored', 'authoring', 'authority'}
KINDS = ('size', 'test-weakened', 'self-mock', 'debug', 'rules', 'sensitive', 'secret')
TIMEOUT = re.compile(r'timeout\W{0,4}(\d[\d_]*)', re.I)
IS_TEST = re.compile(r'(^|/)(tests?/|__tests__/|test_[^/]*$|conftest\.py$|[^/]*_test\.[^/]*$|[^/]*Tests?\.(java|kt)$|[^/]*\.(test|spec|cy)\.|[^/]*_spec\.|(e2e|spec|cypress)/)')
TIMEOUT_CONFIG = re.compile(r'(^|/)((vitest|jest|playwright|karma|cypress)[^/]*config|pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml)')
ASSERTS = re.compile(r'\bassert|\bexpect\(|\.should\b')
NO_BUDGET = re.compile(r'\.lock$|\.lock\.|^(package-lock|npm-shrinkwrap)\.json$|^(pnpm-lock\.yaml|go\.sum)$|\.min\.|\.(patch|diff|svg|csv|tsv|snap|md|mdx|rst|txt|json|ya?ml|sql)$')


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
    """(sha, how it was chosen): the merge base with --base, else with origin/<default branch>, else with the local one."""
    if base:
        ref = git('rev-parse', '--verify', '--quiet', base + '^{commit}', cwd=cwd)
        if not ref:
            return None, None
        mb = git('merge-base', 'HEAD', ref, cwd=cwd)
        return (mb, f'merge-base with {base}') if mb else (ref, f'{base}, no merge base')
    d = default_branch(cwd)
    for r in ('origin/' + d, d):
        mb = git('merge-base', 'HEAD', r, cwd=cwd)
        if mb:
            return mb, f'merge-base with {r}'
    return None, None


def changed_files(base, cwd):
    """{path: {'add': [(line, text)], 'rem': [text], 'remn': [old line numbers], 'deleted': bool, 'old': path at base}}: the working tree against base, untracked included.
    Two git calls in all: the raw listing, then the whole patch, split per file in the same order."""
    entries = []
    parts = nul_list(gitb('diff', '--raw', '-z', '-M', '--no-abbrev', '--no-ext-diff', '--no-textconv', base, cwd=cwd))
    i = 0
    while i < len(parts):  # ':mode mode sha sha STATUS' then one path, or two for a rename or copy
        status = parts[i].split(' ')[-1][:1]
        paths = parts[i + 1:i + (3 if status in 'RC' else 2)]
        i += len(paths) + 1
        entries.append((paths[-1], {'add': [], 'rem': [], 'remn': [], 'deleted': status == 'D', 'old': paths[0] if status == 'R' else paths[-1]}))
    DIFF = ('diff', '-U0', '-M', '--no-color', '--no-ext-diff', '--no-textconv', '--inter-hunk-context=0', base)
    blocks = gitb(*DIFF, cwd=cwd).split('\ndiff --git ')
    # A block belongs to an entry only when its header names the path; a type change prints two blocks for one entry.
    matched = len(blocks) == len(entries) and all(blk.split('\n', 1)[0].endswith(path) for blk, (path, _) in zip(blocks, entries))
    files = {}
    for k, (path, info) in enumerate(entries):
        files[path] = info
        mine = blocks[k:k + 1] if matched else gitb(*DIFF, '--', *dict.fromkeys((info['old'], path)), cwd=cwd).split('\ndiff --git ')
        for blk in mine:
            n = o = 0
            hunk = False
            for ln in blk.split('\n'):
                if ln.startswith('@@'):
                    m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)', ln)
                    o, n, hunk = int(m.group(1)), int(m.group(2)), True
                elif hunk and ln.startswith('+'):
                    info['add'].append((n, ln[1:]))
                    n += 1
                elif hunk and ln.startswith('-'):
                    info['rem'].append(ln[1:])
                    info['remn'].append(o)
                    o += 1
    for path in nul_list(gitb('ls-files', '-o', '-z', '--exclude-standard', cwd=cwd)):
        if path.startswith('.orchestra/sessions/'):  # Orchestra's own ledger, never part of the branch
            continue
        text = read_text(path, cwd) or ''
        files[path] = {'add': [] if '\0' in text else list(enumerate(text.splitlines(), 1)), 'rem': [], 'remn': [], 'deleted': False, 'old': path}
    return files


def read_text(path, cwd):
    try:
        return (Path(cwd or '.') / path).read_bytes().decode('utf-8', 'replace')
    except OSError:  # gone
        return None


GENERATED = re.compile(r'^\s*(#|//|/\*|\*|<!--|--|;)\s*.*(@generated|\bgenerated (by|file)\b|\b(is|was|are) (auto-?)?generated\b|\bauto-?generated\b|do not edit)', re.I)


def over_budget(path, old, text, base, max_lines, waivers, cwd):
    """A message when a text source file grew past the budget in this diff, else None."""
    name = path.rsplit('/', 1)[-1]
    if NO_BUDGET.search(name) or {'dist', 'build'} & set(path.split('/')[:-1]):
        return None
    if '\0' in text or any(GENERATED.match(ln) for ln in text.splitlines()[:5]) or any(
            fnmatch.fnmatch(path, w.split()[0]) for w in waivers.splitlines() if w.split() and not w.startswith('#')):
        return None
    now = len(text.strip().splitlines())
    if now <= max_lines:
        return None
    was = len(gitb('show', f'{base}:{old}', cwd=cwd).splitlines())
    if now > was:
        return f'{was} lines at base, {now} now, over the {max_lines} budget'


def words(path):
    """Lowercase words of a path: split on separators, camelCase, acronyms and digits, trailing s stripped."""
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', path)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    ws = re.split(r'[^A-Za-z]+', s)
    return {w.lower().removesuffix('s') if not w.lower().endswith('ss') else w.lower() for w in ws if w}


def is_sensitive(path):
    ws = words(path)
    return (bool(ws & SENSITIVE) or any(w.startswith(SENSITIVE_PREFIX) and w not in NOT_AUTH for w in ws)
            or path.endswith(('.prisma', '.sql')) or any(s.startswith('.env') for s in path.lower().split('/')))


def num(s):
    return int(s.replace('_', ''))


def raised_timeouts(info):
    """Added timeout lines whose same line (apart from the number) was removed with a smaller number."""
    old = {}
    for t in info['rem']:
        m = TIMEOUT.search(t)
        if m:
            old.setdefault(TIMEOUT.sub('', t).strip(), []).append(num(m.group(1)))
    for n, t in info['add']:
        m = TIMEOUT.search(t)
        if m and any(num(m.group(1)) > v for v in old.get(TIMEOUT.sub('', t).strip(), [])):
            yield n


def tool_section_lines(text, numbers):
    """True when any of the 1-based line numbers sits under a lint, type or test tool section of a TOML text."""
    lines = text.splitlines()
    return any(next((s for s in reversed(lines[:n]) if s.startswith('[')), '').startswith(TOOL_SECTION) for n in numbers)


def check(base, max_lines=500, cwd=None):
    cwd = git('rev-parse', '--show-toplevel', cwd=cwd)
    sha, how = check_base(base, cwd) if cwd else (None, None)
    if not sha:
        return None
    mods = set()  # in-repo python module names: every .py stem and every folder holding one
    for p in nul_list(gitb('ls-files', '-co', '-z', '--exclude-standard', cwd=cwd)):
        if p.endswith('.py'):
            parts = p[:-3].split('/')
            mods.update(parts[-1:] + parts[:-1])
    mods.discard('__init__')
    mods -= set(sys.stdlib_module_names)
    waivers = read_text('.orchestra/budget-waivers', cwd) or ''
    files = changed_files(sha, cwd)
    removed = collections.Counter(t.strip() for info in files.values() for t in info['rem'])  # a suppression that only moved is not new

    def moved(t):
        """True once per removed occurrence of the line; a second added copy is new."""
        if removed[t.strip()] > 0:
            removed[t.strip()] -= 1
            return True
        return False
    out = []

    def add(kind, path, line, msg):
        out.append({'kind': kind, 'path': path, 'line': line, 'message': msg})

    for path, info in files.items():
        text = None if info['deleted'] else read_text(path, cwd)
        names = {path, info['old']}  # a rename is judged under both names
        is_test = bool(IS_TEST.search(path))
        msg = text and over_budget(path, info['old'], text, sha, max_lines, waivers, cwd)
        if msg:
            add('size', path, None, msg)
        if any(re.search(WEAK_FILES, p) for p in names):
            add('test-weakened', path, None, 'test, CI or lint config changed; ' + REASON)
        if path.endswith('pyproject.toml') and (info['add'] or info['rem']):
            was = gitb('show', f"{sha}:{info['old']}", cwd=cwd) if info['rem'] else ''
            if (text and tool_section_lines(text, [n for n, _ in info['add']])) or tool_section_lines(was, info['remn']):
                add('test-weakened', path, None, 'lint, type or test config changed; ' + REASON)
        if (info['deleted'] and is_test) or (IS_TEST.search(info['old']) and not is_test):
            add('test-weakened', path, None, 'test file deleted or moved out of the tests; ' + REASON)
        elif is_test and sum(len(ASSERTS.findall(t)) for t in info['rem']) > sum(len(ASSERTS.findall(t)) for _, t in info['add']):
            add('test-weakened', path, None, 'assertions removed; ' + REASON)
        if is_test or TIMEOUT_CONFIG.search(path):
            for n in raised_timeouts(info):
                add('test-weakened', path, n, 'test timeout raised; ' + REASON)
        if any(re.search(RULES_FILES, p) for p in names):
            add('rules', path, None, 'rules changed; the reviewer judges with the base version')
        if any(is_sensitive(p) for p in names):
            add('sensitive', path, None, 'security-relevant path; the reviewer loads the security lens')
        prose = path.endswith(('.md', '.txt', '.rst'))  # docs quote these patterns; only secrets count there
        for n, t in info['add']:
            for kind, rx, why in LINE_RULES:
                if (kind == 'secret' or not prose) and re.search(rx, t) and not (kind == 'test-weakened' and moved(t)):
                    add(kind, path, n, why)
            if is_test and not prose and re.search(TEST_ONLY, t) and not moved(t):
                add('test-weakened', path, n, REASON)
            m = None if prose else re.search(r'''\b(?:patch|monkeypatch\.setattr)\(\s*['"]([\w.]+)|\bpatch\.object\(\s*(\w+)''', t)
            if m and (m.group(2) in mods or '.' in (m.group(1) or '') and m.group(1).split('.')[0] in mods):
                add('self-mock', path, n, 'mocks an in-repo module; test the real one')
            if path.endswith('.py') and not is_test and 'DEBUG' in t and re.search(r'\bprint\(', t):
                add('debug', path, n, 'leftover debug code')
    out.sort(key=lambda f: (KINDS.index(f['kind']), f['path'], f['line'] or 0))
    return {'base': sha, 'how': how, 'files': len(files), 'added': sum(len(i['add']) for i in files.values()),
            'removed': sum(len(i['rem']) for i in files.values()),
            'findings': out, 'counts': {k: sum(f['kind'] == k for f in out) for k in KINDS if any(f['kind'] == k for f in out)}}


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
    print(f"base {result['base'][:9]} ({result['how']}), {result['files']} files, +{result['added']} -{result['removed']} lines")
    for f in result['findings']:
        print(f"{f['kind']} {f['path']}{':%d' % f['line'] if f['line'] else ''} {f['message']}")
    counts = ', '.join(f'{k} {n}' for k, n in result['counts'].items())
    print(f"{len(result['findings'])} findings ({counts})" if counts else 'no findings')
    return 0
