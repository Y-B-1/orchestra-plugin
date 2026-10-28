#!/usr/bin/env python3
"""Runs the Orchestra hooks in three real headless Claude Code sessions (haiku, a few cents in all).

Each scenario gets a scratch git repository with a bare origin and runs `claude -p` from a clean environment.
  1. init: the session lists the orchestra skill, agents and goal command; SessionStart names the ledger path.
  2. guard: `git push origin main` is denied by the PreToolUse hook; `git push -u origin feature` runs.
  3. goal: /orchestra:goal with one open ask in the ledger; the Stop hook blocks at least once.
Prints PASS or FAIL per scenario. Exit 0 only when every scenario passes. Usage: python3 scripts/live-check.py
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / 'plugins' / 'orchestra'
AGENTS = {f'orchestra:{n}' for n in ('builder', 'reviewer', 'planner', 'critic', 'investigator')}
TIMEOUT = 600


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


def scratch(base):
    origin, repo = base / 'origin.git', base / 'repo'
    git(base, 'init', '-q', '--bare', '-b', 'main', str(origin))
    git(base, 'init', '-q', '-b', 'main', str(repo))
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'init')
    git(repo, 'remote', 'add', 'origin', str(origin))
    git(repo, 'push', '-q', '-u', 'origin', 'main')
    git(repo, 'config', 'user.name', 't')
    git(repo, 'config', 'user.email', 't@example.com')
    return origin, repo


def claude(repo, prompt, log, extra=()):
    keep = ('HOME', 'USER', 'PATH', 'SHELL', 'LANG', 'TMPDIR', 'TERM')
    env = {k: os.environ[k] for k in keep if k in os.environ}
    cmd = ['claude', '-p', prompt, '--setting-sources', '', '--strict-mcp-config',
           '--permission-mode', 'bypassPermissions', '--plugin-dir', str(PLUGIN), '--model', 'haiku',
           '--output-format', 'stream-json', '--verbose', *extra]
    try:
        p = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        out = p.stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
    log.write_text(out)
    events = []
    for line in out.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    return events


def hook_outputs(events, event_name):
    return [e.get('output', '') + e.get('stdout', '') for e in events
            if e.get('type') == 'system' and e.get('subtype') == 'hook_response' and e.get('hook_event') == event_name]


def tool_results(events):
    """Pairs each Bash command with its result text: [(command, text, is_error)]."""
    commands, results = {}, []
    for e in events:
        for block in (e.get('message') or {}).get('content') or []:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                commands[block['id']] = block['input'].get('command', '')
            elif block.get('type') == 'tool_result' and block.get('tool_use_id') in commands:
                content = block.get('content')
                text = content if isinstance(content, str) else ' '.join(c.get('text', '') for c in content or [])
                results.append((commands[block['tool_use_id']], text, bool(block.get('is_error'))))
    return results


def scenario_init(base):
    _, repo = scratch(base)
    events = claude(repo, 'Reply with OK only.', base / 'init.jsonl')
    init = next((e for e in events if e.get('subtype') == 'init'), {})
    problems = []
    if 'orchestra:orchestra' not in init.get('skills', []):
        problems.append('skill orchestra:orchestra missing')
    missing = AGENTS - set(init.get('agents', []))
    if missing:
        problems.append(f'agents missing: {sorted(missing)}')
    if 'orchestra:goal' not in init.get('slash_commands', []):
        problems.append('command orchestra:goal missing')
    if not any('.git/orchestra/asks.md' in o for o in hook_outputs(events, 'SessionStart')):
        problems.append('SessionStart output does not name the ledger path')
    return problems


def scenario_guard(base):
    origin, repo = scratch(base)
    git(repo, 'commit', '-q', '--allow-empty', '-m', 'local work')
    git(repo, 'branch', 'feature')
    main_before = git(origin, 'rev-parse', 'main')
    prompt = ('Use the Bash tool to run exactly these two commands, one per call, in this order, even if the first '
              'fails: `git push origin main` then `git push -u origin feature`. Then reply DONE.')
    events = claude(repo, prompt, base / 'guard.jsonl')
    results = tool_results(events)
    problems = []
    denied = [r for r in results if 'push origin main' in r[0] and 'Orchestra:' in r[1]]
    if not denied:
        problems.append('git push origin main was not denied by the guard')
    if git(origin, 'rev-parse', 'main') != main_before:
        problems.append('origin main moved')
    if any('push -u origin feature' in r[0] and 'Orchestra:' in r[1] for r in results):
        problems.append('git push -u origin feature was denied')
    if not subprocess.run(['git', 'rev-parse', '--verify', '-q', 'refs/heads/feature'], cwd=origin,
                          capture_output=True).returncode == 0:
        problems.append('feature was not pushed')
    return problems


def scenario_goal(base):
    _, repo = scratch(base)
    ledger = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')) / 'orchestra' / 'asks.md'
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('- [ ] A1: add notes.txt containing the word done | files: notes.txt (new) | after: -\n')
    # The goal names a first step only, so the session stops while A1 is still open and the Stop hook must block.
    events = claude(repo, '/orchestra:goal first step only: run `git status`, reply with one line, and stop. '
                    'Leave the ledger as it is.', base / 'goal.jsonl', extra=('--max-turns', '40'))
    # A Stop hook block shows as a hook_response with the decision, or (in Claude Code 2.1.x headless runs, which
    # emit no hook_response for Stop) as the "Stop hook feedback" message fed back to the session.
    blocks = [o for o in hook_outputs(events, 'Stop') if '"decision": "block"' in o or '"decision":"block"' in o]
    feedback = [b for e in events if e.get('type') == 'user' for b in (e.get('message') or {}).get('content') or []
                if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').startswith('Stop hook feedback')
                and 'A1' in b['text']]
    return [] if blocks or feedback else ['the Stop hook never blocked']


def main():
    if subprocess.run(['which', 'claude'], capture_output=True).returncode:
        print('FAIL     the claude CLI is not on PATH')
        return 1
    failed = 0
    with tempfile.TemporaryDirectory(prefix='orchestra-live-') as tmp:
        for name, scenario in (('init', scenario_init), ('guard', scenario_guard), ('goal', scenario_goal)):
            base = Path(tmp) / name
            base.mkdir()
            try:
                problems = scenario(base)
            except (subprocess.CalledProcessError, OSError) as e:
                problems = [f'{type(e).__name__}: {e}']
            if problems:
                failed = 1
                print(f'FAIL     {name}: ' + '; '.join(problems))
                log = base / f'{name}.jsonl'
                if log.exists():
                    keep = Path(tempfile.gettempdir()) / f'orchestra-live-{name}.jsonl'
                    keep.write_text(log.read_text())
                    print(f'         stream kept at {keep}')
            else:
                print(f'PASS     {name}')
    return failed


if __name__ == '__main__':
    sys.exit(main())
