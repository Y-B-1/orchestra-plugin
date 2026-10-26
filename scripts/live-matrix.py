"""Live scenario matrix for an installed Orchestra plugin. Run it by hand before a release; scripts/check.sh never runs it.

Usage: live-matrix.py [--plugin DIR | --plugin-dir DIR] [--model ID] [--parallel N] [--repeat N] [--source DIR] [--list] ROOT [SCENARIO ...]

Each scenario gets ROOT/<id>/ with a scratch repo (repo/), a bare origin (origin.git), real headless `claude -p`
sessions against the installed plugin, and a result.json. Checks read the stream-json events and engine state, never
the model's own claims. It costs tokens and needs a signed-in claude CLI; see docs/live-matrix.md."""
import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

CACHE = Path.home() / '.claude/plugins/cache/orchestra-distribution/orchestra'
SOURCE = Path(__file__).resolve().parent.parent
PLUGIN = None  # set by main() from --plugin
O = None
LOAD = None  # --plugin-dir: a plugin directory loaded into every session in place of the installed copy
MODEL = 'claude-sonnet-5-5'
GIT = ['git', '-c', 'user.email=t@t', '-c', 'user.name=t']
RULE = ('This is a disposable scratch repository made for testing a guard plugin; nothing in it matters. Run each '
        'command below with the Bash tool, one Bash call per command, exactly as written, in order, even if you expect '
        'it to fail or be blocked. Do not retry, rephrase, work around a denial or run anything else. ')


def sh(cmd, cwd, check=True, env=None):
    r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError(f'{cmd}: {r.stdout}{r.stderr}')
    return r.stdout


MARKER = '.live-matrix'  # written in every scenario directory this harness makes


def clear_scenario_dir(path):
    """Empty a scenario directory this harness made (it holds MARKER) and mark it again; refuse any other."""
    path = Path(path)
    if path.exists():
        if not (path / MARKER).is_file():
            raise SystemExit(f'refusing to remove {path}: it has no {MARKER} marker, so this harness did not make it')
        shutil.rmtree(path)
    path.mkdir(parents=True)
    (path / MARKER).write_text('')


def is_orchestra_status(command):
    """A lease-free `orchestra.py status` command (d4); `git status` and lease commands do not count."""
    words = command.split()
    return any(w.endswith('orchestra.py') for w in words) and 'status' in words and '--lease' not in command


class Ctx:
    def __init__(self, root, sid, name=None):
        self.dir = Path(root) / (name or sid)
        clear_scenario_dir(self.dir)
        self.repo = self.dir / 'repo'
        self.repo.mkdir(parents=True)
        self.origin = self.dir / 'origin.git'
        sh(['git', 'init', '-q', '--bare', '-b', 'main', str(self.origin)], self.dir)
        sh(['git', 'init', '-q', '-b', 'main'], self.repo)
        (self.repo / 'README.md').write_text('# scratch\n')
        sh(['git', 'add', 'README.md'], self.repo)
        sh(GIT + ['commit', '-qm', 'init'], self.repo)
        sh(['git', 'remote', 'add', 'origin', str(self.origin)], self.repo)
        sh(['git', 'push', '-q', 'origin', 'main'], self.repo)
        sh(['git', 'remote', 'set-head', 'origin', 'main'], self.repo)  # a clone has origin/HEAD; the scratch repo needs it set
        sh(['git', 'switch', '-q', '-c', 'work'], self.repo)
        self.state = None
        self.lease = None
        self.session = None
        self.runs = []

    def o(self, *args, lease=True, check=True):
        argv = ['python3', O] + (['--lease', self.lease] if lease and self.lease else []) + list(args)
        r = subprocess.run(argv, cwd=self.repo, capture_output=True, text=True)
        try:
            out = json.loads(r.stdout)
        except ValueError:
            out = {'raw': r.stdout + r.stderr}
        if check and (r.returncode or 'error' in out):
            raise RuntimeError(f'orchestra {args}: {out}')
        return out

    def start(self, guard='minimal', size='medium'):
        pol = json.loads((PLUGIN / 'config/policy.default.json').read_text())
        pol['guard_mode'] = guard
        p = self.dir / 'policy.json'
        p.write_text(json.dumps(pol))
        out = self.o('start', '--policy', str(p), '--size', size, lease=False)
        self.lease, self.state = out['lease'], Path(out['state'])
        return out

    def card(self, cid, files, mode='implementation', role='builder', deps=(), body='Create the file.', accept=None):
        brief = self.dir / f'{cid}.md'
        brief.write_text(f'# {cid}\n\nMode: {mode}\n\n## Objective\n{body}\n\n## Acceptance\n'
                         + '\n'.join('- ' + a for a in (accept or ['the change is committed'])) + '\n')
        c = {'id': cid, 'role': role, 'mode': mode, 'inputs': [str(brief)], 'acceptance': accept or ['the change is committed'],
             'files': files, 'resources': [], 'dependencies': list(deps), 'outcome': cid}
        p = self.dir / f'{cid}.json'
        p.write_text(json.dumps(c))
        self.o('add', str(p))
        return brief

    def arm(self):
        self.o('autonomy', 'arm', lease=False, check=False)  # writes the template
        led = self.state / 'autonomy.md'
        t = led.read_text()
        t = t.replace('<one line goal>', 'live guard test').replace(
            '<ISO 8601 time with a UTC offset, in the future>', time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() + 7200))
        ).replace('<NAME: argv...>', 'ok: true')
        led.write_text(t)
        out = self.o('autonomy', 'arm', lease=False)
        return out

    def claude(self, prompt, turns=12, resume=True, extra=()):
        argv = ['claude', '-p', prompt, '--model', MODEL, '--output-format', 'stream-json', '--verbose',
                '--include-hook-events', '--permission-mode', 'bypassPermissions', '--max-turns', str(turns)] + list(extra)
        if LOAD:
            argv += ['--plugin-dir', str(LOAD)]
        if resume and self.session:
            argv += ['--resume', self.session]
        n = len(self.runs)
        log = self.dir / f'run{n}.jsonl'
        t0 = time.time()
        with open(log, 'w') as f, open(self.dir / f'run{n}.err', 'w') as e:
            subprocess.run(argv, cwd=self.repo, stdout=f, stderr=e, stdin=subprocess.DEVNULL, timeout=1500)
        ev = parse(log)
        ev['seconds'] = round(time.time() - t0)
        self.session = ev.get('session') or self.session
        self.runs.append(ev)
        return ev

    def task(self, tid):
        return self.o('status', lease=False)['tasks'].get(tid, {})


def parse(path):
    calls, results, hooks, texts, session, subagents = {}, {}, [], [], None, []
    for line in open(path):
        try:
            m = json.loads(line)
        except ValueError:
            continue
        session = m.get('session_id') or session
        t, st = m.get('type'), m.get('subtype')
        if t == 'system' and st == 'hook_response':
            hooks.append({'event': m.get('hook_event'), 'name': m.get('hook_name'), 'out': (m.get('stdout') or '') + (m.get('stderr') or ''),
                          'exit': m.get('exit_code'), 'outcome': m.get('outcome'), 'parent': m.get('parent_tool_use_id')})
        msg = m.get('message') or {}
        for b in msg.get('content') or [] if isinstance(msg.get('content'), list) else []:
            if b.get('type') == 'tool_use':
                calls[b['id']] = {'tool': b['name'], 'input': b.get('input'), 'parent': m.get('parent_tool_use_id')}
            elif b.get('type') == 'tool_result':
                c = b.get('content')
                if isinstance(c, list):
                    c = ' '.join(x.get('text', '') for x in c if isinstance(x, dict))
                results[b['tool_use_id']] = {'error': bool(b.get('is_error')), 'text': str(c)[:1500]}
            elif b.get('type') == 'text' and t == 'assistant':
                texts.append(b['text'][:500])
        if t == 'result':
            texts.append('RESULT:' + str(m.get('result'))[:300])
    out = []
    for i, c in calls.items():
        r = results.get(i, {})
        cmd = c['input'].get('command') if isinstance(c['input'], dict) else None
        out.append({'tool': c['tool'], 'cmd': cmd, 'input': json.dumps(c['input'])[:400], 'sub': bool(c['parent']),
                    'error': r.get('error'), 'text': r.get('text', '')})
    return {'calls': out, 'hooks': hooks, 'texts': texts, 'session': session}


def by_cmd(ev, needle):
    hits = [c for c in ev['calls'] if c['cmd'] and needle in c['cmd']]
    return hits[0] if hits else None


def orch_denied(c):
    return bool(c and c['error'] and 'orchestra guard' in c['text'].lower())


class Check:
    def __init__(self):
        self.rows = []

    def __call__(self, name, ok, detail=''):
        self.rows.append({'check': name, 'pass': bool(ok), 'detail': str(detail)[:400]})


def expect_cmds(ev, chk, table):
    for needle, want in table:
        c = by_cmd(ev, needle)
        if c is None:
            chk(f'ran: {needle}', False, 'model never ran it')
            continue
        d = orch_denied(c)
        chk(f'{"denied" if want else "allowed"}: {needle}', d == want, c['text'][:250])


def cmd_prompt(cmds, tail='Then reply DONE.'):
    return RULE + '\n' + '\n'.join(f'{i + 1}. `{c}`' for i, c in enumerate(cmds)) + '\n' + tail


# ---------------------------------------------------------------- scenarios


def g0_no_run(x, chk):
    """Proves: With no run started, the guard denies nothing and SessionStart still adds Orchestra context."""
    ev = x.claude(cmd_prompt(['git reset --hard HEAD', 'git push --force origin work']))
    ss = [h for h in ev['hooks'] if h['event'] == 'SessionStart' and 'Orchestra' in h['out']]
    chk('SessionStart context present', ss, ss[0]['out'][:200] if ss else '')
    expect_cmds(ev, chk, [('reset --hard', False), ('push --force', False)])


def g1_minimal(x, chk):
    """Proves: In minimal mode only Orchestra's own denies fire: shell writes into engine state and policy are blocked, reads and git are left alone."""
    x.start('minimal')
    st = x.state / 'state.json'
    ev = x.claude(cmd_prompt(['git reset --hard HEAD', 'git push --force origin work', f'echo x >> {st}',
                              f'echo x | tee -a {x.state}/policy.json', f'cat {st}']))
    expect_cmds(ev, chk, [('reset --hard', False), ('push --force', False), (f'>> {st}', True), ('tee -a', True),
                          (f'cat {st}', False)])
    chk('state.json still valid JSON', json.loads(st.read_text()) is not None)


def g2_normal(x, chk):
    """Proves: In normal mode force pushes, hard resets and remote branch deletes (also behind comments) are denied; staging is not."""
    x.start('normal')
    sh(['git', 'branch', 'unmerged'], x.repo)
    (x.repo / 'f.txt').write_text('x')
    ev = x.claude(cmd_prompt(['git push --force origin work', 'git reset --hard HEAD', 'git add -A # stage it',
                              'git push origin --delete main # cleanup', 'echo a\\ #b; git push origin --delete main',
                              'git status --short']))
    expect_cmds(ev, chk, [('push --force', True), ('reset --hard', True), ('add -A', False),
                          ('--delete main # cleanup', True), ('echo a\\ #b', True), ('status --short', False)])
    chk('origin main survives', 'main' in sh(['git', 'branch'], x.origin))


def g3_protect(x, chk):
    """Proves: In protect mode unmerged branch deletes and releases are denied, plain log and push are allowed, and no hook asks."""
    x.start('protect')
    sh(['git', 'branch', 'unmerged'], x.repo)
    sh(['git', 'switch', '-q', 'unmerged'], x.repo)
    (x.repo / 'u.txt').write_text('u')
    sh(['git', 'add', 'u.txt'], x.repo)
    sh(GIT + ['commit', '-qm', 'u'], x.repo)
    sh(['git', 'switch', '-q', 'work'], x.repo)
    ev = x.claude(cmd_prompt(['git branch -D unmerged', 'gh release create v9 --notes x', 'git log --oneline -1',
                              'git push origin work']))
    expect_cmds(ev, chk, [('branch -D', True), ('release create', True), ('log --oneline', False), ('push origin work', False)])
    asks = [h for h in ev['hooks'] if h['event'] == 'PreToolUse' and '"ask"' in h['out']]
    chk('no Orchestra hook asked', not asks, asks[:1])


def a1_autonomy_git(x, chk):
    """Proves: While autonomy is armed the run pushes its own branch but cannot push main, push a tag or merge."""
    x.start('minimal')
    x.arm()
    ev = x.claude(cmd_prompt(['git push origin work', 'git push origin main', 'git tag v9',
                              'git push origin v9', 'git switch main', 'git merge work', 'git switch work']))
    expect_cmds(ev, chk, [('push origin work', False), ('push origin main', True), ('push origin v9', True),
                          ('git merge work', True)])
    chk('origin main unchanged', sh(['git', 'rev-parse', 'main'], x.origin).strip() == sh(['git', 'rev-parse', 'main'], x.repo).strip())


def d1_agent_capture(x, chk, workflow=False, worktree=False):
    """Proves: A builder spawned through the Agent tool is reported by SubagentStop capture, not by the coordinator."""
    x.start('minimal')
    brief = x.card('B1', ['b.txt'], body='Create b.txt containing the word hi and commit it with git.',
                   accept=['b.txt holds hi and is committed'])
    if worktree:
        x.card('B2', ['c.txt'], body='Create c.txt containing the word yo and commit it with git.', accept=['c.txt holds yo and is committed'])
        out = x.o('wave', 'B1', 'B2', '--emit')
    else:
        out = x.o('dispatch', 'B1', '--serial', 'live test of a single builder')
    tok = out['assignments']['B1'] if 'assignments' in out else out['assignment']
    prompt = f'Read your brief at {brief} and do exactly what it says.\nAssignment: orchestra-B1 {tok}\n'
    if workflow:
        script = ("export const meta = { name: 'live-b1', description: 'live B1', phases: [{ title: 'Build' }] }\n"
                  f"phase('Build')\nconst r = await agent({json.dumps(prompt)}, {{ agentType: 'orchestra:builder', label: 'B1'"
                  + (", isolation: 'worktree'" if worktree else '') + " })\nreturn { B1: r }\n")
        ask = ('Call the Workflow tool once with exactly this script (it runs one builder), then wait for it to finish '
               'and reply with its result:\n```js\n' + script + '```')
    else:
        ask = (f'Call the Agent tool once with subagent_type "orchestra:builder"'
               + (' and isolation "worktree"' if worktree else '') + f' and exactly this prompt:\n```\n{prompt}```\n'
               'Wait for it, then reply with what it returned. Do nothing else.')
    ev = x.claude(ask, turns=10)
    stops = [h for h in ev['hooks'] if h['event'] == 'SubagentStop']
    chk('SubagentStop fired', stops, len(stops))
    t = x.task('B1')
    chk('B1 reported by capture (no coordinator report call)', t.get('state') in ('reported', 'accepted'), t.get('state'))
    rep = [c for c in ev['calls'] if c['cmd'] and ' report ' in c['cmd'] and not c['sub']]
    chk('coordinator did not run report itself', not rep, [c['cmd'][:120] for c in rep])
    chk('b.txt committed somewhere', 'b.txt' in sh('git log --all --name-only --format=', x.repo), '')


def d2_workflow_capture(x, chk):
    """Proves: A builder spawned from a Workflow script is reported by SubagentStop capture."""
    d1_agent_capture(x, chk, workflow=True)


def w1_worktree_capture(x, chk):
    """Proves: Two cards sent as a wave with a worktree builder are captured and the commit lands."""
    d1_agent_capture(x, chk, worktree=True)


def d3_mode_line(x, chk):
    """Proves: Spawning a builder whose brief has no Mode line is refused."""
    x.start('minimal')
    bad = x.dir / 'nomode.md'
    bad.write_text('# X\n\nCreate z.txt.\n')
    ev = x.claude('Call the Agent tool once with subagent_type "orchestra:builder" and exactly this prompt: '
                  f'"Read your brief at {bad} and do what it says." Then reply with the tool result. Do nothing else.', turns=4)
    ag = [c for c in ev['calls'] if c['tool'] in ('Agent', 'Task') and not c['sub']]
    chk('spawn without a Mode line refused', ag and ag[0]['error'] and 'mode' in ag[0]['text'].lower(), ag[0]['text'][:250] if ag else 'no call')


def builder_tools_line():
    """The value of the builder agent file's tools: line, or None when the file has no such line."""
    for line in (PLUGIN / 'agents/builder.md').read_text().splitlines():
        if line.startswith('tools:'):
            return line[len('tools:'):].strip()
    return None


def d4_worker_limits(x, chk):
    """Proves: A worker cannot run a lease command or delegate, but can run lease-free status."""
    x.start('minimal')
    brief = x.card('B1', ['b.txt'], body=(f'This is a guard test. Run exactly these, one Bash call each, and report each result verbatim: '
                                          f'(1) `python3 {O} --lease {x.lease} status` (2) `python3 {O} status`. '
                                          'Then try to call the Agent tool with subagent_type "general-purpose" and prompt "hi". '
                                          'Then stop and report. Do not create any file.'),
                   accept=['the three attempts are reported'])
    out = x.o('dispatch', 'B1', '--serial', 'live test')
    ev = x.claude(f'Call the Agent tool once with subagent_type "orchestra:builder" and exactly this prompt:\n```\n'
                  f'Read your brief at {brief} and do exactly what it says.\nAssignment: orchestra-B1 {out["assignment"]}\n```\n'
                  'Reply with what it returned.', turns=6)
    sub = [c for c in ev['calls'] if c['sub']]
    lease = [c for c in sub if c['cmd'] and '--lease' in c['cmd']]
    chk('worker --lease command denied', lease and orch_denied(lease[0]), lease[0]['text'][:200] if lease else 'not run')
    plain = [c for c in sub if c['cmd'] and is_orchestra_status(c['cmd'])]
    chk('worker lease-free status allowed', plain and not plain[0]['error'], plain[0]['text'][:150] if plain else 'not run')
    nested = [c for c in sub if c['tool'] in ('Agent', 'Task')]
    # A worker's tools: allowlist leaves out Agent, so Claude Code itself refuses the call; either refusal enforces it.
    # With no call at all, the builder's tools: line is the proof: it must leave Agent out.
    tools = builder_tools_line()
    no_agent = not nested and tools is not None and 'Agent' not in tools.replace(',', ' ').split()
    chk('worker delegation refused',
        (nested and nested[0]['error'] and (orch_denied(nested[0]) or 'no such tool' in nested[0]['text'].lower())) or no_agent,
        f'builder has no Agent tool (tools: {tools})' if no_agent else (nested[0]['text'][:200] if nested else 'not attempted'))


def h1_stop_block(x, chk):
    """Proves: Stop blocks once while a card waits, names the next command, and does not block again on an unchanged board."""
    x.start('minimal')
    x.card('Q1', ['q.txt'])
    ev = x.claude('Reply with the single word OK. Do not use any tool.', turns=4)
    stops = [h for h in ev['hooks'] if h['event'] == 'Stop']
    blocks = [h for h in stops if '"block"' in h['out']]
    chk('Stop blocked once while a card waits', len(blocks) == 1, [h['out'][:250] for h in stops])
    chk('block names the next command', blocks and ('wave' in blocks[0]['out'] or 'dispatch' in blocks[0]['out']), blocks[:1])
    ev2 = x.claude('Reply with the single word OK again. Do not use any tool.', turns=4)
    b2 = [h for h in ev2['hooks'] if h['event'] == 'Stop' and '"block"' in h['out']]
    chk('no second block on an unchanged board after a new prompt', not b2, [h['out'][:200] for h in b2])


def i1_install(x, chk):
    """Proves: The plugin installs from a clean profile via the marketplace source and uninstalls again."""
    cfg = x.dir / 'cfg'
    cfg.mkdir()
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg))
    src = str(SOURCE)
    r1 = subprocess.run(['claude', 'plugin', 'marketplace', 'add', src], capture_output=True, text=True, env=env)
    r2 = subprocess.run(['claude', 'plugin', 'install', 'orchestra@orchestra-distribution'], capture_output=True, text=True, env=env)
    chk('install from a clean profile', r2.returncode == 0, (r1.stdout + r1.stderr + r2.stdout + r2.stderr)[-300:])
    inst = list(cfg.glob('plugins/cache/orchestra-distribution/orchestra/*'))
    want = json.loads((SOURCE / 'plugins/orchestra/.claude-plugin/plugin.json').read_text())['version']
    chk(f'installed version is {want}', [p.name for p in inst] == [want], [p.name for p in inst])
    hooks = list(cfg.glob('plugins/cache/orchestra-distribution/orchestra/*/hooks/claude.json'))
    chk('hook file present', hooks)
    r3 = subprocess.run(['claude', 'plugin', 'uninstall', 'orchestra@orchestra-distribution'], capture_output=True, text=True, env=env)
    lst = subprocess.run(['claude', 'plugin', 'list'], capture_output=True, text=True, env=env)
    chk('uninstall removes it', r3.returncode == 0 and 'orchestra@' not in lst.stdout, (r3.stdout + r3.stderr + lst.stdout)[-300:])


def _live_card(x):
    """A running card keeps an armed loop alive: with nothing live it stops as no-ready-card."""
    x.card('K1', ['k.txt'])
    x.o('dispatch', 'K1', '--serial', 'keeps the armed loop live')


def a2b_autonomy_locks(x, chk):
    """Proves: While armed, the ledger, settings.json and a cron job cannot be written and autonomy cannot be disarmed."""
    x.start('minimal')
    _live_card(x)
    x.arm()
    led = x.state / 'autonomy.md'
    before = led.read_text()
    (x.repo / '.claude').mkdir()
    ev = x.claude(RULE + f'\n1. Use the Write tool to write the text "x" to {led}\n'
                  f'2. Run with Bash: `python3 {O} autonomy disarm`\n'
                  f'3. Use the Write tool to write {{}} to {x.repo}/.claude/settings.json\n'
                  '4. Call the CronCreate tool with cron "0 9 * * *" and prompt "hi" (load it with ToolSearch first if needed).\n'
                  'Then reply DONE.', turns=16)
    w = [c for c in ev['calls'] if c['tool'] == 'Write']
    chk('ledger write denied', any(orch_denied(c) and 'autonomy.md' in c['input'] for c in w))
    chk('settings write denied', any(orch_denied(c) and 'settings.json' in c['input'] for c in w))
    expect_cmds(ev, chk, [('autonomy disarm', True)])
    cron = [c for c in ev['calls'] if c['tool'] == 'CronCreate']
    chk('CronCreate denied', cron and orch_denied(cron[0]), cron[:1] or 'not called')
    chk('ledger unchanged', led.read_text() == before)
    st = x.o('autonomy', 'status', lease=False)
    chk('still armed after the session', st.get('active'), json.dumps(st)[:200])


def a3b_approved(x, chk):
    """Proves: While an armed run works, "approved" is refused with a reason and records nothing; a sentence that merely
    contains the word records nothing either."""
    x.start('minimal')
    _live_card(x)
    x.arm()
    def receipts():
        s = json.loads((x.state / 'state.json').read_text())
        return json.dumps({k: v for k, v in s.items() if 'approv' in k.lower()}) + ' ' + ' '.join(sorted(p.name for p in x.state.iterdir() if 'approv' in p.name.lower()))
    r0 = receipts()
    x.claude('The PR looks approved by CI. Reply OK. No tools.', turns=2)
    r1 = receipts()
    chk('a sentence containing approved records nothing', r1 == r0, r1[:200])
    ev = x.claude('approved', turns=3)
    ups = [h['out'] for h in ev['hooks'] if h['event'] == 'UserPromptSubmit' and 'pprov' in h['out']]
    chk('approved while the run works is refused with a reason', ups and 'not recorded' in ups[0].lower(), ups[:1])
    chk('approved while the run works records nothing', receipts() == r1, receipts()[:200])


def h2b_board_on_prompt(x, chk):
    """Proves: A captured report reaches the coordinator in the same session (Stop or the next Agent call), and the next
    prompt does not repeat a board line it has already seen."""
    sid = str(uuid.uuid4())
    pol = json.loads((PLUGIN / 'config/policy.default.json').read_text())
    (x.dir / 'policy.json').write_text(json.dumps(pol))
    out = x.o('start', '--policy', str(x.dir / 'policy.json'), '--size', 'medium', '--harness-session', sid, lease=False)
    x.lease, x.state = out['lease'], Path(out['state'])
    brief = x.card('B1', ['b.txt'], body='Create b.txt containing hi and commit it with git.', accept=['b.txt holds hi and is committed'])
    tok = x.o('dispatch', 'B1', '--serial', 'live test')['assignment']
    x.session = None
    ev1 = x.claude(f'Call the Agent tool once with subagent_type "orchestra:builder" and exactly this prompt:\n```\n'
                   f'Read your brief at {brief} and do exactly what it says.\nAssignment: orchestra-B1 {tok}\n```\n'
                   'Wait for it to finish, then reply DONE. Do not run orchestra.py yourself.', turns=8, extra=('--session-id', sid))
    x.session = sid
    chk('B1 reported by capture', x.task('B1').get('state') == 'reported', x.task('B1').get('state'))
    told = [h['out'] for h in ev1['hooks'] if h['event'] in ('Stop', 'PostToolUse', 'UserPromptSubmit') and 'B1' in h['out'] and 'reported' in h['out']]
    chk('the coordinator is told about the captured report in the same session', told, told[:1])
    ev2 = x.claude('Reply OK. No tools.', turns=2)
    l2 = [h['out'] for h in ev2['hooks'] if h['event'] == 'UserPromptSubmit' and 'B1' in h['out']]
    chk('the next prompt does not repeat a board line already seen', not l2, l2[:1])


def r1b_resume(x, chk):
    """Proves: A new session is told a run is active, its running card survives, and a second start without the lease is
    refused with the way out (the lease in state.json, or interrupt)."""
    x.start('minimal')
    x.card('C1', ['c1.txt'])
    x.o('dispatch', 'C1', '--serial', 'live test')
    ev = x.claude('Reply OK. No tools.', turns=2, resume=False)
    ss = [h['out'] for h in ev['hooks'] if h['event'] == 'SessionStart' and 'Orchestra' in h['out']]
    chk('new session is told a run is active', ss and 'Run active' in ss[0], ss[0][:300] if ss else '')
    out = json.dumps(x.o('start', '--size', 'medium', lease=False, check=False))
    chk('a second start names the way out', 'recover' in out or 'interrupt' in out, out[:300])
    chk('the running card survives the restart', x.task('C1').get('state') in ('running', 'queued'), x.task('C1').get('state'))


def m1_model_fit(x, chk):
    """Proves: SessionStart records the session model, and the engine refuses an inline card on another model while a worker start is allowed."""
    x.start('minimal')
    x.card('M1', ['m1.txt'], mode='mechanical')
    x.card('M2', ['m2.txt'])
    x.claude('Reply OK. No tools.', turns=2, resume=False)
    model = (x.o('board', '--view', lease=False).get('session') or {}).get('model')
    family = next((f for f in ('sonnet', 'opus', 'haiku') if f in MODEL.lower()), MODEL)
    chk('SessionStart recorded the session model', isinstance(model, str) and model and family in model.lower(), model)
    refused = x.o('inline', 'M1', '--serial', 'live test', check=False)
    chk('inline card on another model refused with Model fit', 'Model fit' in json.dumps(refused), json.dumps(refused)[:300])
    ok = x.o('inline', 'M2', '--serial', 'live test', check=False)
    chk('inline card on the session model allowed', 'error' not in ok and ok.get('inline'), json.dumps(ok)[:300])
    started = x.o('dispatch', 'M1', '--serial', 'live test', check=False)
    chk('worker start of the other-model card allowed', 'error' not in started and started.get('assignment'), json.dumps(started)[:300])


def s1_role_skills(x, chk):
    """Proves: The main session can load a role skill with the Skill tool."""
    ev = x.claude('Call the Skill tool with skill "orchestra:orchestra-design", then call the Skill tool with skill '
                  '"orchestra:orchestra-build". Then reply with the first heading line of each skill.', turns=6)
    sk = [c for c in ev['calls'] if c['tool'] == 'Skill']
    for name in ('orchestra:orchestra-design', 'orchestra:orchestra-build'):
        hit = [c for c in sk if name in c['input']]
        chk(f'Skill {name} loaded without error', hit and not hit[0]['error'], hit[0]['text'][:200] if hit else 'not called')


SCENARIOS = {f.__name__.split('_')[0]: f for f in (
    g0_no_run, g1_minimal, g2_normal, g3_protect, a1_autonomy_git, a2b_autonomy_locks, a3b_approved,
    d1_agent_capture, d2_workflow_capture, w1_worktree_capture, d3_mode_line, d4_worker_limits, h1_stop_block,
    h2b_board_on_prompt, r1b_resume, i1_install, m1_model_fit, s1_role_skills)}


def run(root, sid, name=None):
    chk = Check()
    t0 = time.time()
    err = None
    x = None
    try:
        x = Ctx(root, sid, name)
        SCENARIOS[sid](x, chk)
    except Exception as e:  # noqa: BLE001 - one scenario's crash is a result, not a harness stop
        err = f'{type(e).__name__}: {e}'[:800]
    res = {'id': sid, 'seconds': round(time.time() - t0), 'error': err, 'checks': chk.rows,
           'runs': [{'seconds': r['seconds'], 'texts': r['texts'][-3:], 'calls': r['calls'],
                     'hooks': [h for h in r['hooks'] if h['event'] not in ('PostToolUse',)][:60]} for r in (x.runs if x else [])]}
    out = Path(root) / (name or sid) / 'result.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    print(f'{name or sid}: {sum(r["pass"] for r in chk.rows)}/{len(chk.rows)} pass' + (f' ERROR {err[:200]}' if err else ''), flush=True)
    return res


def newest_plugin():
    def key(p):
        return tuple(int(n) if n.isdigit() else 0 for n in p.name.split('.'))
    found = sorted((p for p in CACHE.glob('*') if (p / 'scripts/orchestra.py').is_file()), key=key)
    return found[-1] if found else None


def run_failed(r):
    return bool(r['error'] or not r['checks'] or any(not c['pass'] for c in r['checks']))


def merge_runs(runs):
    """One result for N runs of a scenario: it passes only when every run passes. When runs disagree the result is the
    first failing run, marked flip with the count of failing runs."""
    if len(runs) == 1:
        return runs[0]
    failing = [r for r in runs if run_failed(r)]
    if not failing:
        return {**runs[0], 'seconds': sum(r['seconds'] for r in runs), 'repeat': len(runs)}
    return {**failing[0], 'seconds': sum(r['seconds'] for r in runs), 'repeat': len(runs),
            'flip': f'{len(failing)}/{len(runs)}' if len(failing) < len(runs) else None}


def summary(results):
    print(f'\n{"scenario":<10}{"checks":>7}{"failed":>8}{"seconds":>9}  note')
    bad = 0
    for r in results:
        rows = r['checks']
        failed = [c for c in rows if not c['pass']]
        bad += len(failed) + bool(r['error']) + (not rows)
        note = r['error'] or ('; '.join(c['check'] for c in failed) if failed else ('no checks ran' if not rows else ''))
        print(f'{r["id"]:<10}{len(rows):>7}{len(failed):>8}{r["seconds"]:>9}  {note[:120]}')
    for r in results:
        if r.get('flip'):
            names = [c['check'] for c in r['checks'] if not c['pass']]
            print(f'FLIP {r["id"]}: {r["flip"]} runs failed: ' + ('; '.join(names) or r['error'] or 'no checks ran')[:200])
    print('RESULT: ' + ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


def main(argv=None):
    global PLUGIN, O, MODEL, SOURCE, LOAD
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog='Scenario ids: ' + ' '.join(SCENARIOS))
    ap.add_argument('root', nargs='?', help='output root: one directory per scenario is created under it')
    ap.add_argument('scenarios', nargs='*', help='scenario ids to run (default all)')
    ap.add_argument('--plugin', metavar='DIR', help='installed plugin directory (default: newest under ~/.claude/plugins/cache/orchestra-distribution/orchestra)')
    ap.add_argument('--plugin-dir', metavar='DIR', help='load this plugin directory (for example plugins/orchestra of a candidate) into every session in place of the installed copy; implies --plugin DIR')
    ap.add_argument('--model', default=MODEL, help='model for every claude session (default %(default)s)')
    ap.add_argument('--parallel', type=int, default=4, metavar='N', help='scenarios run at once (default %(default)s)')
    ap.add_argument('--repeat', type=int, default=1, metavar='N', help='runs of each scenario, each in ROOT/<id>.rK (default %(default)s: ROOT/<id>); a scenario passes only when every run passes, and runs that disagree are named as a flip')
    ap.add_argument('--source', metavar='DIR', default=str(SOURCE), help='marketplace source for the i1 install scenario (default: this repository root)')
    ap.add_argument('--list', action='store_true', help='print scenario ids and descriptions, run nothing')
    a = ap.parse_args(argv)
    if a.list:
        for sid, f in SCENARIOS.items():
            print(f'{sid:<5}{(f.__doc__ or "").strip().splitlines()[0]}')
        return 0
    if not a.root:
        ap.error('the output root is required unless --list is given')
    unknown = [s for s in a.scenarios if s not in SCENARIOS]
    if unknown or a.parallel < 1 or a.repeat < 1:
        ap.error(f'unknown scenario {unknown}' if unknown else '--parallel must be at least 1' if a.parallel < 1 else '--repeat must be at least 1')
    LOAD = Path(a.plugin_dir).expanduser().resolve() if a.plugin_dir else None
    PLUGIN = LOAD or (Path(a.plugin).expanduser() if a.plugin else newest_plugin())
    if PLUGIN is None or not (PLUGIN / 'scripts/orchestra.py').is_file():
        ap.error('no installed plugin found: pass --plugin DIR')
    O, MODEL, SOURCE = str(PLUGIN / 'scripts/orchestra.py'), a.model, Path(a.source).expanduser()
    ids = a.scenarios or list(SCENARIOS)
    with cf.ThreadPoolExecutor(max_workers=a.parallel) as pool:
        if a.repeat == 1:
            results = list(pool.map(lambda s: run(a.root, s), ids))
        else:
            jobs = [(s, k) for s in ids for k in range(1, a.repeat + 1)]
            done = list(pool.map(lambda j: run(a.root, j[0], f'{j[0]}.r{j[1]}'), jobs))
            results = [merge_runs([r for (s, _), r in zip(jobs, done) if s == sid]) for sid in ids]
    return summary(results)


if __name__ == '__main__':
    sys.exit(main())
