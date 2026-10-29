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
import hashlib, json, os, re, shlex, subprocess, sys, time
from pathlib import Path

MAX_CONTINUES = 60
LIVE_WORKER_SECONDS = 600  # an unfinished worker turn with no transcript write for this long counts as gone
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


def worker_running(event):
    """True when a subagent or Workflow agent of this session is mid-turn: its last assistant record did not end the
    turn and it wrote its transcript in the last LIVE_WORKER_SECONDS. The app wakes the session when a background
    worker finishes, so a Stop while one runs needs no prompt. A worker that just finished does not count."""
    path = event.get('transcript_path')
    if not isinstance(path, str) or not path.endswith('.jsonl'):
        return False
    cutoff = time.time() - LIVE_WORKER_SECONDS
    try:
        for f in (Path(path[:-len('.jsonl')]) / 'subagents').rglob('*.jsonl'):
            if f.stat().st_mtime >= cutoff and turn_open(f):
                return True
    except OSError:
        return False
    return False


def progress(cwd, session, missing):
    """A fingerprint of the work: what is missing, HEAD, the working tree and the ledger. Equal means nothing moved."""
    lf = ledger(cwd, session)
    root = git('rev-parse', '--show-toplevel', cwd=cwd)
    untracked = []
    for name in git('ls-files', '--others', '--exclude-standard', cwd=cwd).splitlines()[:500]:
        try:
            st = (Path(root) / name).stat()
            untracked.append(f'{name} {st.st_size} {st.st_mtime_ns}')
        except OSError:
            pass
    parts = [repr(missing), git('rev-parse', 'HEAD', cwd=cwd), git('status', '--porcelain', cwd=cwd),
             git('diff', 'HEAD', cwd=cwd), '\n'.join(untracked), lf.read_text() if lf.exists() else '']
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
                    else:
                        head = pr_head(cwd, branch)
                        if head is None:
                            missing.append(f'no open pull request for {branch}: open one with gh pr create')
                        elif head != UNKNOWN and head != git('rev-parse', 'HEAD', cwd=cwd):
                            missing.append(f'the pull request for {branch} does not hold the current head: push it')
        if missing:
            mark = progress(cwd, session, missing)
            if mark == goal.get('progress'):
                # Nothing moved since the last prompt: repeating it only makes the session repeat itself.
                goal['continues'] -= 1
                quiet = goal.get('quiet') == mark
                goal['quiet'] = mark
                gf.write_text(json.dumps(goal))
                if not quiet:
                    print(json.dumps({'systemMessage': 'Orchestra goal: nothing changed since the last prompt (' +
                                      '; '.join(missing) + '). Orchestra stays quiet until the work changes: a finished background task or your reply wakes the session.'}))
                return
            goal['progress'] = mark
            gf.write_text(json.dumps(goal))
            ask = (' Do not wait for an answer: decide, write the decision and its reason in the ledger, and continue.'
                   if ends_with_question(event) else '')
            print(json.dumps({'decision': 'block', 'reason': 'Goal not done: ' + '; '.join(missing) + '.' + ask +
                              ' Keep going: start every remaining independent ask now, in parallel. '
                              'If only the owner can unblock it, run: python3 "' + __file__ + '" goal stop REASON'}))
            return
        goal['state'] = 'done'
        gf.write_text(json.dumps(goal))
        return
    # No goal: remind once per state of the ledger when this session's asks are still open, never loop.
    if asks and not event.get('stop_hook_active'):
        seen = state_dir(cwd, session) / 'reminded'
        mark = progress(cwd, session, [a[1] for a in asks])
        if seen.exists() and seen.read_text() == mark:
            return
        seen.write_text(mark)
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
        from check import run_check  # loaded only for this command
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
