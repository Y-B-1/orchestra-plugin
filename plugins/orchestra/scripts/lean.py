#!/usr/bin/env python3
"""Orchestra: hooks and the small CLI behind /goal.

Hooks (stdin JSON from Claude Code):
  lean.py hook session-start   prints the session context
  lean.py hook pre-tool-use    denies merging into the default branch; allows everything else
  lean.py hook stop            keeps a /goal session going until its asks are done and the branch is pushed

CLI:
  lean.py run SECONDS -- CMD   runs CMD, kills it and its children after SECONDS (exit 124)
  lean.py ledger               prints the ask ledger path
  lean.py goal set TEXT        starts a goal
  lean.py goal stop REASON     ends a goal that only a human can unblock
  lean.py goal status
  lean.py check [--base REF] [--max-lines N] [--json]   scans the branch diff; findings never block (docs/check.md)

State is per session: <git common dir>/orchestra/sessions/<session id>/ holds asks.md and goal.json.
The session id comes from the hook event, or from CLAUDE_CODE_SESSION_ID in a Bash command.
"""
import fnmatch, json, os, re, shlex, subprocess, sys
from pathlib import Path

MAX_CONTINUES = 60
OPEN = re.compile(r'^\s*- \[( |>)\] +([^\s:]+)', re.M)
SESSION_ENV = 'CLAUDE_CODE_SESSION_ID'


def git(*args, cwd=None):
    try:
        p = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    except OSError:  # a cwd that no longer exists, or no git
        return ''
    return p.stdout.strip() if p.returncode == 0 else ''


def state_dir(cwd=None, session=None, create=False):
    """The session's state folder. Outside a Git repository nothing is created until a goal is set."""
    session = session or os.environ.get(SESSION_ENV) or ''
    session = re.sub(r'[^A-Za-z0-9._-]', '', session)
    common = git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=cwd)
    base = Path(common) / 'orchestra' if common else Path(cwd or os.getcwd()) / '.orchestra'
    base = base / 'sessions' / session if session else base
    if create or common:
        base.mkdir(parents=True, exist_ok=True)
    return base


def ledger(cwd=None, session=None):
    return state_dir(cwd, session) / 'asks.md'


def open_asks(cwd=None, session=None):
    path = ledger(cwd, session)
    return OPEN.findall(path.read_text()) if path.exists() else []


def default_branch(cwd=None):
    head = git('symbolic-ref', '--short', 'refs/remotes/origin/HEAD', cwd=cwd)
    if head:
        return head.split('/', 1)[1]
    for name in ('main', 'master', 'trunk'):
        if git('rev-parse', '--verify', '--quiet', 'refs/heads/' + name, cwd=cwd):
            return name
    return 'main'


# ---- guard -----------------------------------------------------------------------------------

SEPARATORS = ('&&', '||', '$(', ';', '|', '&', '\n', '`', '(', ')', '{', '}')


def split_commands(command):
    """Split a shell line into simple commands at operators, subshells and command substitutions.
    Quoted text stays whole, except that $( and ` inside double quotes still start a new command."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            buf.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == '\\' and i + 1 < len(command):
            buf.append(command[i:i + 2])
            i += 2
            continue
        sep = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if quote == '"':
            if c == '"':
                quote = None
            elif sep in ('$(', '`'):
                parts.append(''.join(buf))
                buf, i = [], i + len(sep)
                continue
            buf.append(c)
            i += 1
            continue
        if c in '\'"':
            quote = c
        elif sep:
            parts.append(''.join(buf))
            buf, i = [], i + len(sep)
            continue
        buf.append(c)
        i += 1
    parts.append(''.join(buf))
    return [x for x in parts if x.strip()]
SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh')
PREFIX = ('sudo', 'env', 'command', 'time', 'nohup', 'exec', 'xargs', 'nice')
GIT_VALUE_OPTS = ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env')
PUSH_VALUE_OPTS = ('-o', '--push-option', '--repo', '--receive-pack', '--exec')
GH_VALUE_OPTS = ('-R', '--repo')


def command_words(words):
    """The words from the command's own name on: skips VAR=value, sudo, env and similar prefixes."""
    i = 0
    while i < len(words) and (re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[i]) or words[i] in PREFIX
                              or (i and words[i - 1] in PREFIX and words[i].startswith('-'))):
        i += 1
    return words[i:]


def skip_options(rest, value_opts):
    """Drop leading options; an option in value_opts without '=' also drops its value."""
    while rest and rest[0].startswith('-') and rest[0] != '--':
        rest = rest[2:] if rest[0] in value_opts else rest[1:]  # -Ro/r and --repo=o/r carry their value
    return rest


def gh_reason(rest, main):
    rest = skip_options(rest, GH_VALUE_OPTS)
    if rest[:1] == ['pr'] and skip_options(rest[1:], GH_VALUE_OPTS)[:1] == ['merge']:
        return 'gh pr merge'
    if rest[:1] != ['api']:
        return None
    flat = ' '.join(rest)
    if re.search(r'/merges?\b', flat) or 'mergePullRequest' in flat or 'enablePullRequestAutoMerge' in flat:
        return 'a GitHub API merge'
    method = 'GET'
    for i, w in enumerate(rest):
        if w in ('-X', '--method') and i + 1 < len(rest):
            method = rest[i + 1].upper()
        elif w.startswith('--method='):
            method = w.split('=', 1)[1].upper()
        elif w.startswith('-X') and len(w) > 2:
            method = w[2:].upper()
        elif method == 'GET' and w in ('-f', '-F', '--field', '--raw-field', '--input'):
            method = 'POST'
    if method == 'GET':
        return None
    m = re.escape(main)
    if re.search(rf'git/refs/heads/{m}(?![\w./-])', flat) or re.search(rf'\bref=refs/heads/{m}(?![\w./-])', flat):
        return f'a GitHub API write to {main}'
    if re.search(rf'/branches/{m}/rename\b', flat):
        return f'a rename of {main}'
    if '/contents/' in flat and re.search(rf'\bbranch={m}(?![\w./-])', flat):
        return f'a GitHub API commit to {main}'
    return None


def git_reason(rest, main, current, cwd):
    rest = skip_options(rest, GIT_VALUE_OPTS)
    if rest[:1] != ['push']:
        return None
    rest = rest[1:]
    if '--mirror' in rest:
        return 'a mirror push (it overwrites every branch, the default one included)'
    if ('--all' in rest or '--branches' in rest) and git('rev-parse', '--verify', '--quiet', 'refs/heads/' + main, cwd=cwd):
        return f'a push of all branches, {main} included'
    args, explicit_repo, i = [], False, 0
    while i < len(rest):
        w = rest[i]
        if w in PUSH_VALUE_OPTS:
            explicit_repo = explicit_repo or w == '--repo'
            i += 2
            continue
        if w.startswith('--repo='):
            explicit_repo = True
        if not w.startswith('-'):
            args.append(w)
        i += 1
    refs = args if explicit_repo else args[1:]
    if not refs and current == main and '--tags' not in rest:
        return f'a push of {main}'
    for ref in refs:
        dst = ref.lstrip('+').split(':')[-1]
        dst = dst[len('refs/heads/'):] if dst.startswith('refs/heads/') else dst
        if dst in ('HEAD', '@'):
            dst = current
        if dst == main or '*' in dst:
            return f'a push to {main}'
    return None


def merge_reason(command, cwd=None):
    """A reason when the command merges into, pushes to or deletes the default branch; else None."""
    for part in split_commands(command):
        try:
            words = shlex.split(part)
        except ValueError:  # an unbalanced quote, as in the tail of "$(git push origin main)"
            words = [w.strip('"\'()') for w in part.split()]
        words = command_words(words)
        if not words:
            continue
        name = os.path.basename(words[0])
        if name == 'cd' and len(words) > 1:  # later parts run in that folder
            cwd = str((Path(cwd or os.getcwd()) / os.path.expanduser(words[1])).resolve())
            continue
        if name in SHELLS:
            for i, w in enumerate(words[1:-1], 1):
                if re.fullmatch(r'-[A-Za-z]*c', w):
                    inner = merge_reason(words[i + 1], cwd)
                    if inner:
                        return inner
                    break
            continue
        if name == 'eval':
            inner = merge_reason(' '.join(words[1:]), cwd)
            if inner:
                return inner
            continue
        main = default_branch(cwd)
        if name == 'gh':
            reason = gh_reason(words[1:], main)
        elif name == 'git':
            reason = git_reason(words[1:], main, git('branch', '--show-current', cwd=cwd), cwd)
        else:
            reason = None
        if reason:
            return reason
    return None


def hook_pre_tool_use(event):
    if event.get('tool_name') != 'Bash':
        return
    tool_input = event.get('tool_input')
    command = tool_input.get('command') if isinstance(tool_input, dict) else ''
    if not isinstance(command, str):
        return
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    try:
        reason = merge_reason(command, cwd)
    except Exception:  # never fail open on a command that may merge or push
        reason = 'a merge or push the guard could not read' if re.search(r'\b(merge|push)\b', command) else None
    if reason:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
            'permissionDecisionReason': f'Orchestra: {reason} is the one step only the owner takes. '
                                        'Push your branch and open a PR instead; the owner merges.'}}))


# ---- goal ------------------------------------------------------------------------------------

def goal_file(cwd=None, session=None):
    return state_dir(cwd, session) / 'goal.json'


def hook_stop(event):
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    gf = goal_file(cwd, session)
    if session and not gf.exists():
        # A goal set where Bash had no CLAUDE_CODE_SESSION_ID lands in the shared folder: enforce it rather than drop it.
        shared = state_dir(cwd) / 'goal.json'
        if shared.exists() and json.loads(shared.read_text()).get('state') == 'active':
            gf, session = shared, None
    asks = open_asks(cwd, session)
    if gf.exists():
        goal = json.loads(gf.read_text())
        if goal.get('state') != 'active':
            return
        goal['continues'] = goal.get('continues', 0) + 1
        if goal['continues'] > MAX_CONTINUES:
            goal['state'] = 'capped'
            gf.write_text(json.dumps(goal))
            return
        missing = []
        if asks:
            missing.append('open asks in the ledger: ' + ', '.join(a[1] for a in asks))
        elif not ledger(cwd, session).exists():
            missing.append(f'no ask ledger yet at {ledger(cwd, session)}')
        if not missing:
            branch = git('branch', '--show-current', cwd=cwd)
            dirty = git('status', '--porcelain', '--untracked-files=no', cwd=cwd)
            if dirty:
                missing.append('uncommitted changes')
            if git('remote', cwd=cwd):
                if not branch:
                    missing.append('HEAD is detached: check out a feature branch, commit there and push it')
                elif branch == default_branch(cwd):
                    missing.append(f'the work is on {branch}, which only the owner merges into: '
                                   f'create a feature branch here (git switch -c NAME), push it and open a PR')
                else:
                    upstream = git('rev-parse', '--abbrev-ref', '@{upstream}', cwd=cwd)
                    ahead = git('rev-list', '--count', '@{upstream}..HEAD', cwd=cwd) if upstream else ''
                    if not upstream or ahead not in ('', '0'):
                        missing.append(f'branch {branch} is not pushed')
        if missing:
            gf.write_text(json.dumps(goal))
            print(json.dumps({'decision': 'block', 'reason': 'Goal not done: ' + '; '.join(missing) +
                              '. Keep going: start every remaining independent ask now, in parallel. '
                              'If only the owner can unblock it, run: python3 "' + __file__ + '" goal stop REASON'}))
            return
        goal['state'] = 'done'
        gf.write_text(json.dumps(goal))
        return
    # No goal: remind once per stop chain when this session's asks are still open, never loop.
    if asks and not event.get('stop_hook_active'):
        print(json.dumps({'decision': 'block', 'reason': 'The ask ledger still has open asks: ' + ', '.join(a[1] for a in asks) +
                          '. Finish them, or mark each [~] with a reason, then stop.'}))


def hook_session_start(event):
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    print(f'Orchestra is on. Ask ledger: {ledger(cwd, session)}. CLI: python3 "{__file__}".\n'
          'For any prompt with more than one ask, load the orchestra skill first and follow it: split the asks, '
          'start every independent one at once, review once at the end. Only merging into the default branch is blocked.')


def run_bounded(seconds, cmd):
    import signal, time
    posix = hasattr(os, 'killpg')
    p = subprocess.Popen(cmd, start_new_session=posix)

    def kill(sig):
        try:
            os.killpg(p.pid, sig) if posix else p.kill()
        except OSError:
            pass

    def on_signal(signum, frame):  # the caller was stopped: take the child's whole group down too
        kill(signal.SIGKILL if posix else None)
        sys.exit(128 + signum)

    for name in ('SIGTERM', 'SIGINT', 'SIGHUP'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), on_signal)
    try:
        return p.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        kill(signal.SIGTERM if posix else None)
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            kill(signal.SIGKILL if posix else None)
        if posix:
            kill(signal.SIGKILL)  # children that outlived the group leader
        p.wait()
        print(f'TIMEOUT: {" ".join(cmd)} ran over {seconds}s and was stopped. A test or command hangs; '
              'find which one (run files one by one, each bounded) instead of rerunning the whole suite.', file=sys.stderr)
        return 124


# ---- check: a pre-PR scan of the branch diff -----------------------------------------------------

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
    if re.search(r'\.lock$|^package-lock\.json$|\.min\.', name) or {'dist', 'build'} & set(path.split('/')[:-1]):
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
        for n, t in info['add']:
            for kind, rx, why in LINE_RULES:
                if re.search(rx, t):
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


def usage():
    print(__doc__, file=sys.stderr)
    return 2


def main():
    args = sys.argv[1:]
    if args[:1] == ['run']:
        if '--' not in args or args.index('--') != 2 or len(args) < 4:
            return usage()
        try:
            seconds = float(args[1])
        except ValueError:
            return usage()
        try:
            return run_bounded(seconds, args[3:])
        except OSError as e:
            print(f'run: cannot start {args[3]}: {e}', file=sys.stderr)
            return 127
    if args[:1] == ['hook']:
        handlers = {'session-start': hook_session_start, 'pre-tool-use': hook_pre_tool_use, 'stop': hook_stop}
        if len(args) < 2 or args[1] not in handlers:
            return usage()
        try:
            event = json.loads(sys.stdin.read() or '{}')
        except ValueError:
            return 0
        if isinstance(event, dict):
            handlers[args[1]](event)
        return 0
    if args[:1] == ['check']:
        return run_check(args[1:])
    if args[:1] == ['ledger']:
        print(ledger())
        return 0
    if args[:2] == ['goal', 'set']:
        gf = state_dir(create=True) / 'goal.json'
        gf.write_text(json.dumps({'state': 'active', 'text': ' '.join(args[2:]), 'continues': 0,
                                  'session': os.environ.get(SESSION_ENV, '')}))
        print(f'Goal set. Write the asks to {ledger()} now.')
        if git('branch', '--show-current') == default_branch():
            print(f'You are on {default_branch()}: create a feature branch first (git switch -c NAME); '
                  'the goal ends when that branch is pushed.')
        return 0
    if args[:2] == ['goal', 'stop']:
        gf = state_dir(create=True) / 'goal.json'
        goal = json.loads(gf.read_text()) if gf.exists() else {}
        goal.update(state='stopped', reason=' '.join(args[2:]))
        gf.write_text(json.dumps(goal))
        print('Goal stopped:', goal['reason'])
        return 0
    if args[:2] == ['goal', 'status']:
        gf = goal_file()
        print(gf.read_text() if gf.exists() else 'no goal')
        print('open asks:', ', '.join(a[1] for a in open_asks()) or 'none')
        return 0
    return usage()


if __name__ == '__main__':
    sys.exit(main())
