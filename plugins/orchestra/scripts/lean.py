#!/usr/bin/env python3
"""Orchestra: hooks and the small CLI behind /goal.

Hooks (stdin JSON from Claude Code):
  lean.py hook session-start   prints the session context
  lean.py hook pre-tool-use    denies merging into the default branch; allows everything else
  lean.py hook stop            keeps a /goal session going until its asks are done and the branch is pushed

CLI:
  lean.py run SECONDS -- CMD   runs CMD, stops its process group after SECONDS (exit 124; a child that started its own session is not reached)
  lean.py ledger               prints the ask ledger path
  lean.py goal set [--limit N] TEXT   starts a goal (N stop attempts, default 60; or set ORCHESTRA_GOAL_LIMIT)
  lean.py goal stop [--session ID] REASON   ends a goal; from a terminal with no session id it ends every active goal
  lean.py goal status
  lean.py check [--base REF] [--max-lines N] [--json]   scans the branch diff; findings never block (docs/check.md)

State is per session: <git common dir>/orchestra/sessions/<session id>/ holds asks.md and goal.json. The folder is
created when something is written. The ledger may start with "base: <ref> (<sha>) | branch: <name>".
The session id comes from the hook event, or from CLAUDE_CODE_SESSION_ID in a Bash command.
"""
import fnmatch, hashlib, json, math, os, re, shlex, subprocess, sys, time
from pathlib import Path

MAX_CONTINUES = 60
LIVE_WORKER_SECONDS = 600  # an unfinished worker turn with no transcript write for this long counts as gone
JOURNAL_SECONDS = 3600  # a Workflow journal is written only when an agent starts or ends, so it gets a longer window
OPEN = re.compile(r'^\s*[-*] +\[( |>)\] *([^\s:]+)', re.M)
ASK = re.compile(r'^\s*[-*] +\[[ >x~]\] *[^\s:]+', re.M)
REVIEWED = re.compile(r'^\s*[-*] +\[x\] *review\b', re.M)
BASE = re.compile(r'^base: (\w\S*)', re.M)
SESSION_ENV = 'CLAUDE_CODE_SESSION_ID'


def git(*args, cwd=None):
    try:
        p = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, errors='replace')
    except OSError:  # a cwd that no longer exists, or no git
        return ''
    return p.stdout.strip() if p.returncode == 0 else ''


def state_dir(cwd=None, session=None, create=False):
    """The session's state folder; it is created only when create is set. A ledger or goal written under
    <folder>/.orchestra before the folder became a Git repository is still found."""
    session = session or os.environ.get(SESSION_ENV) or ''
    session = re.sub(r'[^A-Za-z0-9._-]', '', session)
    rel = Path('sessions') / session if session else Path()
    common = git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=cwd)
    base = (Path(common) / 'orchestra' if common else Path(cwd or os.getcwd()) / '.orchestra') / rel
    if common and not any((base / n).exists() for n in ('asks.md', 'goal.json')):
        old = Path(git('rev-parse', '--show-toplevel', cwd=cwd) or '.') / '.orchestra' / rel
        if any((old / n).exists() for n in ('asks.md', 'goal.json')):
            return old
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base


def read_json(f):
    """A JSON object from a file; {} when it is missing, damaged or not an object."""
    try:
        data = json.loads(Path(f).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(f, data):
    tmp = Path(f).with_name(Path(f).name + '.tmp')
    tmp.write_text(json.dumps(data))
    os.replace(tmp, f)


def ledger(cwd=None, session=None):
    return state_dir(cwd, session) / 'asks.md'


def ledger_text(cwd=None, session=None):
    try:
        return ledger(cwd, session).read_text(errors='replace')
    except OSError:
        return ''


def open_asks(cwd=None, session=None):
    return OPEN.findall(ledger_text(cwd, session))


def repo_state(cwd=None, opts=()):
    """(default branch, current branch, local branches) from one git process. opts are git's -C, --git-dir
    and --work-tree words. The default branch is the target of origin/HEAD, else the first of main, master, trunk."""
    default, current, branches = '', '', set()
    prefix = 'refs/remotes/origin/'
    for line in git(*opts, 'for-each-ref', '--format=%(refname) %(symref) %(HEAD)',
                    'refs/remotes/origin/HEAD', 'refs/heads', cwd=cwd).splitlines():
        ref, symref, head = (line.split(' ') + ['', ''])[:3]
        if ref == prefix + 'HEAD' and symref.startswith(prefix):
            default = symref[len(prefix):]
        elif ref.startswith('refs/heads/'):
            branches.add(ref[len('refs/heads/'):])
            if head == '*':
                current = ref[len('refs/heads/'):]
    default = default or next((n for n in ('main', 'master', 'trunk') if n in branches), 'main')
    return default, current, branches


def default_branch(cwd=None):
    return repo_state(cwd)[0]


# ---- guard -----------------------------------------------------------------------------------

SEPARATORS = ('&&', '||', '$(', ';', '|', '&', '\n', '`', '(', ')', '{', '}')
HEREDOC = re.compile(r'<<(-?)[ \t]*(?:\'([^\']*)\'|"([^"]*)"|(\\?)([A-Za-z_][A-Za-z0-9_]*))')
SUBSTITUTION = re.compile(r'\$\(([^)]*)\)|`([^`]*)`')


def skip_heredocs(command, i, pending, shell):
    """From the newline at i, skip the bodies of the pending heredocs. Returns (text still to scan, index of the
    end of the last terminator line). A quoted body is plain text unless a shell reads it; an unquoted one can
    still run its $( ) and backtick spans."""
    j, scan = i + 1, []
    for dash, quoted, delim in pending:
        start = j
        while j < len(command):
            end = command.find('\n', j)
            end = len(command) if end < 0 else end
            if (command[j:end].lstrip('\t') if dash else command[j:end]) == delim:
                break
            j = end + 1
        body = command[start:j]
        if shell:
            scan.append(body)
        elif not quoted:
            scan.extend(m.group(1) or m.group(2) for m in SUBSTITUTION.finditer(body))
        end = command.find('\n', j)
        j = len(command) if end < 0 else end
    return scan, j


def split_commands(command):
    """Split a shell line into simple commands at operators, subshells and command substitutions.
    Quoted text stays whole, except that $( and ` inside double quotes still start a new command.
    Heredoc bodies are not commands; ${...} is one word."""
    command = command.replace('\\\n', '')
    parts, buf, quote, sub, pending, i = [], [], None, False, [], 0
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
        if c == '<' and command.startswith('<<', i) and not command.startswith('<<<', i) and (quote is None or sub):
            m = HEREDOC.match(command, i)
            if m:
                pending.append((m.group(1) == '-', m.group(2) is not None or m.group(3) is not None or bool(m.group(4)),
                                m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None else m.group(5)))
                buf.append(m.group())
                i = m.end()
                continue
        if c == '\n' and pending:
            line = command[command.rfind('\n', 0, i) + 1:i]
            scan, i = skip_heredocs(command, i, pending, bool(re.search(r'\b(sh|bash|zsh|dash|ksh)\b', line)))
            pending = []
            parts.append(''.join(buf))
            buf = []
            for text in scan:
                parts.extend(split_commands(text))
            continue
        sep = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if quote == '"':
            if c == '"':
                quote, sub = None, False
            elif sep in ('$(', '`'):
                parts.append(''.join(buf))
                buf, sub, i = [], True, i + len(sep)
                continue
            buf.append(c)
            i += 1
            continue
        if c == '$' and command.startswith('${', i) and command.find('}', i) > 0:
            end = command.find('}', i) + 1
            buf.append(command[i:end])
            i = end
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
KEYWORDS = ('if', 'then', 'elif', 'else', 'do', 'while', 'until', '!')
PREFIX = ('sudo', 'env', 'command', 'time', 'nohup', 'exec', 'xargs', 'nice', 'timeout', 'npx', 'bunx', 'pnpx')
PREFIX_VALUE_OPTS = {'sudo': ('-u', '-g', '-h', '-p', '-C', '-D', '-R', '-T', '-U'), 'env': ('-u', '-C', '-S'),
                     'nice': ('-n',), 'xargs': ('-n', '-I', '-P', '-L', '-s', '-d', '-E', '-a'),
                     'timeout': ('-s', '--signal', '-k', '--kill-after'), 'npx': ('-p', '--package', '-c')}
GIT_VALUE_OPTS = ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env')
PUSH_VALUE_OPTS = ('-o', '--push-option', '--repo', '--receive-pack', '--exec')
GH_VALUE_OPTS = ('-R', '--repo')
API_VALUE_OPTS = ('-X', '--method', '-f', '-F', '--field', '--raw-field', '-H', '--header', '--jq', '-q', '--input',
                  '-t', '--template', '--hostname', '-p', '--preview', '--cache')


def tool_name(word):
    return re.sub(r'\.exe$', '', os.path.basename(word).lower())


def command_words(words):
    """The words from the command's own name on: skips VAR=value, shell keywords, wrappers (sudo, env, nice,
    timeout, npx ...) with their options and values, and the plugin's `lean.py run SECONDS --`."""
    i = 0
    while i < len(words):
        w, name = words[i], tool_name(words[i])
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', w) or w in KEYWORDS:
            i += 1
        elif name in PREFIX:
            i += 1
            while i < len(words) and words[i].startswith('-'):
                i += 1 if words[i] == '--' else 2 if words[i] in PREFIX_VALUE_OPTS.get(name, ()) else 1
            i += name == 'timeout'  # its duration
        elif re.fullmatch(r'python[\d.]*', name):
            j = i + 1
            while j < len(words) and words[j].startswith('-'):
                j += 1
            if words[j + 1:j + 2] == ['run'] and tool_name(words[j]) == 'lean.py' and '--' in words[j + 2:]:
                i = j + 2 + words[j + 2:].index('--') + 1
            else:
                break
        else:
            break
    return words[i:]


def skip_options(rest, value_opts):
    """Drop leading options; an option in value_opts without '=' also drops its value."""
    while rest and rest[0].startswith('-') and rest[0] != '--':
        rest = rest[2:] if rest[0] in value_opts else rest[1:]  # -Ro/r and --repo=o/r carry their value
    return rest


def drop_redirects(words):
    """Remove redirections (`> file`, `2>&1`, `< in`) so a target is not read as an argument."""
    out, i = [], 0
    while i < len(words):
        if re.fullmatch(r'\d*(>>?|<<?<?|>&|&>>?)', words[i]):
            i += 2
        elif re.match(r'\d*[<>]', words[i]):
            i += 1
        else:
            out.append(words[i])
            i += 1
    return out


def api_endpoint(args):
    i = 0
    while i < len(args):
        if not args[i].startswith('-'):
            return args[i]
        i += 2 if args[i] in API_VALUE_OPTS else 1
    return ''


def gh_reason(rest, main):
    """main is a function: the default branch is looked up only for an API write."""
    rest = skip_options(rest, GH_VALUE_OPTS)
    if rest[:1] == ['pr'] and skip_options(rest[1:], GH_VALUE_OPTS)[:1] == ['merge']:
        return 'gh pr merge'
    if rest[:1] != ['api']:
        return None
    endpoint = api_endpoint(rest[1:])
    flat = ' '.join(rest)
    if endpoint == 'graphql' and any(w.startswith('query=') and ('mergePullRequest' in w or 'enablePullRequestAutoMerge' in w)
                                     for w in rest):
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
    if re.search(r'/merges?/?$', endpoint.split('?')[0]):
        return 'a GitHub API merge'
    m = re.escape(main())
    if re.search(rf'git/refs/heads/{m}(?![\w./-])', flat) or re.search(rf'\bref=refs/heads/{m}(?![\w./-])', flat):
        return f'a GitHub API write to {main()}'
    if re.search(rf'/branches/{m}/rename\b', flat):
        return f'a rename of {main()}'
    if '/contents/' in flat and re.search(rf'\bbranch={m}(?![\w./-])', flat):
        return f'a GitHub API commit to {main()}'
    return None


def git_options(rest):
    """(git's repository-selecting options, the words after the global options)."""
    opts = []
    while rest and rest[0].startswith('-') and rest[0] != '--':
        n = 2 if rest[0] in GIT_VALUE_OPTS else 1
        if rest[0] in ('-C', '--git-dir', '--work-tree') or rest[0].startswith(('-C', '--git-dir=', '--work-tree=')):
            opts += rest[:n]
        rest = rest[n:]
    return opts, rest


def git_reason(rest, state):
    """state(opts) is a function: (default branch, current branch, local branches) of the repository git selects."""
    opts, rest = git_options(rest)
    if rest[:1] != ['push']:
        return None
    main, current, branches = state(tuple(opts))
    rest = rest[1:]
    if '--mirror' in rest:
        return 'a mirror push (it overwrites every branch, the default one included)'
    if ('--all' in rest or '--branches' in rest) and main in branches:
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
        if dst == main or fnmatch.fnmatchcase(main, dst) or fnmatch.fnmatchcase('refs/heads/' + main, dst):
            return f'a push to {main}'
    return None


def merge_reason(command, cwd=None, cache=None):
    """A reason when the command merges into, pushes to or deletes the default branch; else None.
    Git runs at most once per repository, and not at all for a command with no git or gh word."""
    if not re.search(r'\b(git|gh)\b', command):
        return None
    cache = {} if cache is None else cache
    for part in split_commands(command):
        try:
            words = shlex.split(part)
        except ValueError:  # an unbalanced quote, as in the tail of "$(git push origin main)"
            words = [w.strip('"\'()') for w in part.split()]
        words = command_words([w for w in words if w])
        if not words:
            continue
        name = tool_name(words[0])
        if name in ('cd', 'pushd') and len(words) > 1:  # later parts run in that folder
            cwd = str((Path(cwd or os.getcwd()) / os.path.expanduser(words[1])).resolve())
            continue
        if name in SHELLS:
            for i, w in enumerate(words[1:-1], 1):
                if re.fullmatch(r'-[A-Za-z]*c[A-Za-z]*', w):
                    inner = merge_reason(words[i + 1], cwd, cache)
                    if inner:
                        return inner
                    break
            continue
        if name == 'eval':
            inner = merge_reason(' '.join(words[1:]), cwd, cache)
            if inner:
                return inner
            continue

        def state(opts=(), cwd=cwd):
            if (cwd, opts) not in cache:
                cache[cwd, opts] = repo_state(cwd, opts)
            return cache[cwd, opts]
        if name == 'gh':
            reason = gh_reason(drop_redirects(words[1:]), lambda: state()[0])
        elif name == 'git':
            reason = git_reason(drop_redirects(words[1:]), state)
        else:
            reason = None
        if reason:
            return reason
    return None


MERGE_TOOL = re.compile(r'^mcp__.*merge_pull_request$')


def hook_pre_tool_use(event):
    tool = event.get('tool_name')
    if isinstance(tool, str) and MERGE_TOOL.match(tool):
        reason = 'an MCP pull-request merge'
    elif tool in ('Bash', 'PowerShell'):
        tool_input = event.get('tool_input')
        command = tool_input.get('command') if isinstance(tool_input, dict) else ''
        if not isinstance(command, str):
            return
        cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
        try:
            reason = merge_reason(command, cwd)
        except Exception:  # never fail open on a command that may merge or push
            reason = 'a merge or push the guard could not read' if re.search(r'\b(merge|push)\b', command) else None
    else:
        return
    if reason:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
            'permissionDecisionReason': f'Orchestra: {reason} is the one step only the owner takes. '
                                        'Push your branch and open a PR instead; the owner merges.'}}))


# ---- goal ------------------------------------------------------------------------------------

def goal_file(cwd=None, session=None):
    return state_dir(cwd, session) / 'goal.json'


def turn_open(f):
    """True when the last assistant record of a transcript did not end its turn (it stopped for a tool call)."""
    with open(f, 'rb') as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - 65536))
        lines = fh.read().decode(errors='replace').splitlines()
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get('message') if isinstance(row, dict) else None
        if row.get('type') == 'assistant' and isinstance(message, dict):
            return message.get('stop_reason') != 'end_turn'
    return True  # started, no assistant turn yet


def journal_running(f):
    """True when a Workflow journal has an agent that started and has no result or failed record."""
    ended, started = set(), []
    for line in Path(f).read_text(errors='replace').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get('type') == 'started':
            started.append((row.get('key'), row.get('agentId')))
        elif row.get('type') in ('result', 'failed'):
            ended.update((row.get('key'), row.get('agentId')))
    return any(k not in ended and a not in ended for k, a in started)


def worker_running(event):
    """True when a subagent or Workflow agent of this session is still working: an agent transcript whose last
    assistant record did not end the turn and was written in the last LIVE_WORKER_SECONDS, or a Workflow journal with
    an agent that started and has no result yet. The app wakes the session when a background worker finishes, so a
    Stop while one runs needs no prompt. A worker that just finished does not count."""
    path = event.get('transcript_path')
    if not isinstance(path, str) or not path.endswith('.jsonl'):
        return False
    now = time.time()
    try:
        for f in (Path(path[:-len('.jsonl')]) / 'subagents').rglob('*.jsonl'):
            age = now - f.stat().st_mtime
            if f.name == 'journal.jsonl':
                if age < JOURNAL_SECONDS and journal_running(f):
                    return True
            elif f.name.startswith('agent-') and age < LIVE_WORKER_SECONDS and turn_open(f):
                return True
    except OSError:
        return False
    return False


def progress(cwd, session, missing):
    """A fingerprint of the work: what is missing, HEAD, the working tree and the ledger. Equal means nothing moved."""
    root = git('rev-parse', '--show-toplevel', cwd=cwd)
    untracked = []
    for name in git('ls-files', '--others', '--exclude-standard', cwd=root or cwd).splitlines()[:500]:
        try:
            st = (Path(root) / name).stat()
            untracked.append(f'{name} {st.st_size} {st.st_mtime_ns}')
        except OSError:
            pass
    parts = [repr(missing), git('rev-parse', 'HEAD', cwd=cwd), git('status', '--porcelain', cwd=cwd),
             git('diff', 'HEAD', cwd=cwd), '\n'.join(untracked), ledger_text(cwd, session)]
    return hashlib.sha256('\0'.join(parts).encode()).hexdigest()


UNKNOWN = 'unknown'


def pr_head(cwd, branch):
    """The head commit of the open pull request for BRANCH, None when there is none, or UNKNOWN when it cannot be
    read: the remote is not GitHub, gh is missing or not signed in, or gh is slow. UNKNOWN never holds a goal open."""
    if 'github.com' not in git('remote', 'get-url', 'origin', cwd=cwd):
        return UNKNOWN
    try:
        p = subprocess.run(['gh', 'pr', 'view', branch, '--json', 'state,headRefOid'], cwd=cwd, capture_output=True,
                           text=True, timeout=6)
    except (OSError, subprocess.TimeoutExpired):
        return UNKNOWN
    if p.returncode != 0:
        return None if 'no pull requests found' in p.stderr.lower() else UNKNOWN
    try:
        view = json.loads(p.stdout)
    except ValueError:
        return UNKNOWN
    return view.get('headRefOid') if view.get('state') == 'OPEN' else None


def ends_with_question(event):
    text = event.get('last_assistant_message')
    return isinstance(text, str) and '?' in text[-600:]


def commits_ahead(cwd, text):
    """How many commits HEAD holds beyond the work's base: the ledger header's base, else the default branch."""
    main = default_branch(cwd)
    base = BASE.search(text)
    for ref in ([base.group(1)] if base else []) + ['refs/remotes/origin/' + main, 'refs/heads/' + main]:
        if git('rev-parse', '--verify', '--quiet', ref + '^{commit}', cwd=cwd):
            return int(git('rev-list', '--count', ref + '..HEAD', cwd=cwd) or 0)
    return 0


def goal_missing(cwd, session, asks):
    """What a goal still lacks. Asks with no commits and no changes need nothing but their marks."""
    text = ledger_text(cwd, session)
    if asks:
        return ['open asks in the ledger: ' + ', '.join(a[1] for a in asks)]
    if not ledger(cwd, session).exists():
        return [f'no ask ledger yet at {ledger(cwd, session)}']
    if not ASK.search(text):
        return ['the ledger has no ask lines; write one per ask as "- [ ] A1: text"']
    missing = []
    branch = git('branch', '--show-current', cwd=cwd)
    if git('status', '--porcelain', '--untracked-files=no', cwd=cwd):
        missing.append('uncommitted changes')
    if not commits_ahead(cwd, text):
        return missing
    if not REVIEWED.search(text):
        missing.append('no independent review recorded: when it is clean, add "- [x] review: clean" to the ledger')
    if not git('remote', cwd=cwd):
        return missing
    if not branch:
        missing.append('HEAD is detached: check out a feature branch, commit there and push it')
    elif branch == default_branch(cwd):
        missing.append(f'the work is on {branch}, which only the owner merges into: '
                       f'create a feature branch here (git switch -c NAME), push it and open a PR')
    elif git('rev-parse', '--verify', '--quiet', 'refs/remotes/origin/' + branch, cwd=cwd) != git('rev-parse', 'HEAD', cwd=cwd):
        missing.append(f'branch {branch} is not pushed: git push -u origin {branch}')
    else:
        head = pr_head(cwd, branch)
        if head is None:
            missing.append(f'no open pull request for {branch}: open one with gh pr create')
        elif head != UNKNOWN and head != git('rev-parse', 'HEAD', cwd=cwd):
            missing.append(f'the pull request for {branch} does not hold the current head: push it')
    return missing


def hook_stop(event):
    """Keep a /goal session going, but never spam: stay quiet while a worker runs (the app wakes the session when it
    finishes), and never send the same prompt twice for work that has not changed since the last one."""
    if worker_running(event):
        return
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    gf = goal_file(cwd, session)
    if session and not gf.exists():
        # A goal set where Bash had no CLAUDE_CODE_SESSION_ID lands in the shared folder: enforce it rather than drop it.
        shared = state_dir(cwd) / 'goal.json'
        if read_json(shared).get('state') == 'active':
            gf, session = shared, None
    asks = open_asks(cwd, session)
    if gf.exists():
        goal = read_json(gf)
        if goal.get('state') != 'active':
            return
        goal['continues'] = goal.get('continues', 0) + 1
        limit = goal.get('limit') if isinstance(goal.get('limit'), int) else MAX_CONTINUES
        if goal['continues'] > limit:
            goal['state'] = 'capped'
            write_json(gf, goal)
            print(json.dumps({'systemMessage': f'Orchestra goal: the limit of {limit} stop attempts is reached, so the goal is '
                              'capped and the session may stop' + (' with open asks: ' + ', '.join(a[1] for a in asks) if asks else '') +
                              '. Run lean.py goal set again to continue.'}))
            return
        missing = goal_missing(cwd, session, asks)
        if missing:
            mark = progress(cwd, session, missing)
            if mark == goal.get('progress'):
                # Nothing moved since the last prompt: repeating it only makes the session repeat itself.
                goal['continues'] -= 1
                quiet = goal.get('quiet') == mark
                goal['quiet'] = mark
                write_json(gf, goal)
                if not quiet:
                    print(json.dumps({'systemMessage': 'Orchestra goal: nothing changed since the last prompt (' +
                                      '; '.join(missing) + '). Orchestra stays quiet until the work changes: a finished background task or your reply wakes the session.'}))
                return
            goal['progress'] = mark
            write_json(gf, goal)
            ask = (' Do not wait for an answer: decide, write the decision and its reason in the ledger, and continue.'
                   if ends_with_question(event) else '')
            print(json.dumps({'decision': 'block', 'reason': 'Goal not done: ' + '; '.join(missing) + '.' + ask +
                              ' Keep going: start every remaining independent ask now, in parallel. '
                              'If only the owner can unblock it, run: python3 "' + __file__ + '" goal stop REASON'}))
            return
        goal['state'] = 'done'
        write_json(gf, goal)
        return
    # No goal: remind once per state of the ledger when this session's asks are still open, never loop.
    if asks and not event.get('stop_hook_active'):
        seen = state_dir(cwd, session) / 'reminded'
        mark = hashlib.sha256(ledger_text(cwd, session).encode()).hexdigest()
        if seen.exists() and seen.read_text() == mark:
            return
        seen.write_text(mark)
        print(json.dumps({'decision': 'block', 'reason': 'The ask ledger still has open asks: ' + ', '.join(a[1] for a in asks) +
                          '. Finish them, or mark each [~] with a reason, then stop.'}))


def hook_session_start(event):
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    main = default_branch(cwd)
    branch = (f' On {main}, work starts on a new branch.'
              if git('branch', '--show-current', cwd=cwd) == main else '')
    print(f'Orchestra is on. Ask ledger: {ledger(cwd, session)}. CLI: python3 "{__file__}".\n'
          'The orchestra skill handles a prompt with more than one ask. Only merging into the default branch is blocked.' + branch)


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
        rc = p.wait(timeout=seconds)
        return 128 - rc if rc < 0 else rc  # killed by signal N: the conventional 128+N
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
        if not math.isfinite(seconds) or seconds <= 0:
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
            try:
                handlers[args[1]](event)
            except Exception as e:  # a hook that exits with a traceback is a hook error; say what failed and let the turn go on
                print(f'orchestra hook {args[1]} failed: {type(e).__name__}: {e}', file=sys.stderr)
        return 0
    if args[:1] == ['check']:
        from check import run_check  # loaded only for this command
        return run_check(args[1:])
    if args[:1] == ['ledger']:
        state_dir(create=True)
        print(ledger())
        return 0
    if args[:2] == ['goal', 'set']:
        rest, limit = args[2:], os.environ.get('ORCHESTRA_GOAL_LIMIT', '')
        if rest[:1] == ['--limit'] and len(rest) > 1:
            limit, rest = rest[1], rest[2:]
        limit = int(limit) if limit.isdigit() and int(limit) > 0 else MAX_CONTINUES
        write_json(state_dir(create=True) / 'goal.json', {'state': 'active', 'text': ' '.join(rest), 'continues': 0,
                                                          'limit': limit, 'session': os.environ.get(SESSION_ENV, '')})
        print(f'Goal set; it ends after {limit} stop attempts. Write the asks to {ledger()} now.')
        if git('branch', '--show-current') == default_branch():
            print(f'You are on {default_branch()}: create a feature branch first (git switch -c NAME); '
                  'the goal ends when that branch is pushed.')
        return 0
    if args[:2] == ['goal', 'stop']:
        rest, session = args[2:], os.environ.get(SESSION_ENV, '')
        if rest[:1] == ['--session'] and len(rest) > 1:
            session, rest = rest[1], rest[2:]
        reason = ' '.join(rest)
        if session:
            files = [state_dir(session=session, create=True) / 'goal.json']
        else:  # an owner at a terminal knows no session id: end every active goal of the repository
            base = state_dir()
            files = [base / 'goal.json', *sorted((base / 'sessions').glob('*/goal.json'))]
        stopped = 0
        for gf in files:
            goal = read_json(gf)
            if session or goal.get('state') == 'active':
                write_json(gf, {**goal, 'state': 'stopped', 'reason': reason})
                stopped += 1
        print(f'Goal stopped: {reason} (stopped {stopped})')
        return 0
    if args[:2] == ['goal', 'status']:
        gf = goal_file()
        print(gf.read_text() if gf.exists() else 'no goal')
        print('open asks:', ', '.join(a[1] for a in open_asks()) or 'none')
        return 0
    return usage()


if __name__ == '__main__':
    sys.exit(main())
