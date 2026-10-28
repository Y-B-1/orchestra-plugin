#!/usr/bin/env python3
"""Orchestra Lean: hooks and the small CLI behind /goal.

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
"""
import json, os, re, shlex, subprocess, sys
from pathlib import Path

MAX_CONTINUES = 60
OPEN = re.compile(r'^\s*- \[( |>)\] +(\S+)', re.M)


def git(*args, cwd=None):
    p = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ''


def state_dir(cwd=None):
    common = git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=cwd)
    base = Path(common) / 'orchestra' if common else Path(cwd or os.getcwd()) / '.orchestra-lean'
    base.mkdir(parents=True, exist_ok=True)
    return base


def ledger(cwd=None):
    return state_dir(cwd) / 'asks.md'


def open_asks(cwd=None):
    path = ledger(cwd)
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

SPLIT = re.compile(r'&&|\|\||;|\||\n|\$\(|`')


def merge_reason(command, cwd=None):
    """A reason when the command merges into, pushes to or deletes the default branch; else None."""
    main = default_branch(cwd)
    current = git('branch', '--show-current', cwd=cwd)
    for part in SPLIT.split(command):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        for i, w in enumerate(words[:-1]):  # sh -c '...', bash -c "..."
            if w == '-c' and i and os.path.basename(words[i - 1]) in ('sh', 'bash', 'zsh'):
                inner = merge_reason(words[i + 1], cwd)
                if inner:
                    return inner
        names = [os.path.basename(w) for w in words]
        if 'gh' in names:
            rest = words[names.index('gh') + 1:]
            if 'pr' in rest[:3] and 'merge' in rest[rest.index('pr') + 1:rest.index('pr') + 4]:
                return 'gh pr merge'
            flat = ' '.join(rest)
            if 'api' in rest[:3] and (re.search(r'/merges?\b', flat) or 'mergePullRequest' in flat
                                      or 'enablePullRequestAutoMerge' in flat):
                return 'a GitHub API merge'
        if 'git' in names:
            rest = words[names.index('git') + 1:]
            while rest[:1] and rest[0] in ('-C', '-c'):
                rest = rest[2:]
            if rest[:1] != ['push']:
                continue
            args = [a for a in rest[1:] if not a.startswith('-')]
            refs = args[1:]
            if not refs and current == main and '--all' not in rest and '--tags' not in rest:
                return f'a push of {main}'
            for ref in refs:
                dst = ref.lstrip('+').split(':')[-1]
                dst = dst[len('refs/heads/'):] if dst.startswith('refs/heads/') else dst
                if dst == 'HEAD':
                    dst = current
                if dst == main:
                    return f'a push to {main}'
    return None


def hook_pre_tool_use(event):
    if event.get('tool_name') != 'Bash':
        return
    command = (event.get('tool_input') or {}).get('command') or ''
    reason = merge_reason(command, event.get('cwd'))
    if reason:
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
            'permissionDecisionReason': f'Orchestra: {reason} is the one step only the owner takes. '
                                        'Push your branch and open a PR instead; the owner merges.'}}))


# ---- goal ------------------------------------------------------------------------------------

def goal_file(cwd=None):
    return state_dir(cwd) / 'goal.json'


def hook_stop(event):
    cwd = event.get('cwd')
    gf = goal_file(cwd)
    asks = open_asks(cwd)
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
        elif not ledger(cwd).exists():
            missing.append(f'no ask ledger yet at {ledger(cwd)}')
        branch = git('branch', '--show-current', cwd=cwd)
        if not missing:
            dirty = git('status', '--porcelain', '--untracked-files=no', cwd=cwd)
            upstream = git('rev-parse', '--abbrev-ref', '@{upstream}', cwd=cwd)
            ahead = git('rev-list', '--count', '@{upstream}..HEAD', cwd=cwd) if upstream else ''
            if dirty:
                missing.append('uncommitted changes')
            if git('remote', cwd=cwd) and (not upstream or ahead not in ('', '0')):
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
    # No goal: remind once per stop chain when asks are still open, never loop.
    if asks and not event.get('stop_hook_active'):
        print(json.dumps({'decision': 'block', 'reason': 'The ask ledger still has open asks: ' + ', '.join(a[1] for a in asks) +
                          '. Finish them, or mark each [~] with a reason, then stop.'}))


def hook_session_start(event):
    cwd = event.get('cwd')
    print(f'Orchestra Lean is on. Ask ledger: {ledger(cwd)}. CLI: python3 "{__file__}".\n'
          'For any prompt with more than one ask, load the orchestra skill first and follow it: split the asks, '
          'start every independent one at once, review once at the end. Only merging into the default branch is blocked.')


def run_bounded(seconds, cmd):
    import signal, time
    p = subprocess.Popen(cmd, start_new_session=True)
    try:
        return p.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(p.pid, sig)
            except OSError:
                break
            if sig == signal.SIGTERM:
                time.sleep(2)
        p.wait()
        print(f'TIMEOUT: {" ".join(cmd)} ran over {seconds}s and was stopped. A test or command hangs; '
              'find which one (run files one by one, each bounded) instead of rerunning the whole suite.', file=sys.stderr)
        return 124


def main():
    args = sys.argv[1:]
    if args[:1] == ['run'] and '--' in args:
        i = args.index('--')
        return run_bounded(float(args[1]), args[i + 1:])
    if args[:1] == ['hook']:
        event = json.loads(sys.stdin.read() or '{}')
        {'session-start': hook_session_start, 'pre-tool-use': hook_pre_tool_use, 'stop': hook_stop}[args[1]](event)
        return 0
    if args[:1] == ['ledger']:
        print(ledger())
        return 0
    if args[:2] == ['goal', 'set']:
        goal_file().write_text(json.dumps({'state': 'active', 'text': ' '.join(args[2:]), 'continues': 0}))
        print(f'Goal set. Write the asks to {ledger()} now.')
        return 0
    if args[:2] == ['goal', 'stop']:
        gf = goal_file()
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
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
