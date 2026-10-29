#!/usr/bin/env python3
"""Benchmark runner: run one arm on one task in a clean headless Claude Code session, then score it.

Usage:
  bench.py run ARM TASK REP          run one session (writes runs/ARM-TASK-REP/)
  bench.py score RUNDIR              hidden tests, checks, stream metrics (score.json)
  bench.py judge RUNDIR              blind rubric judge (judge.json)
  bench.py queue ARM:TASK:REP ...    run + score + judge each, one at a time
  bench.py report                    table of every scored run
"""
import json, re, os, shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path

B = Path(__file__).resolve().parent
FIXTURE, ORIGIN, TASKS, RUNS = B / 'fixture', B / 'origin.git', B / 'tasks', B / 'runs'
ARMS = {
    'plain': None,
    'orchestra': B.parent / 'plugins/orchestra',
    'orchestra-2.15.3': B / 'arms/orchestra-2.15.3',
    'pocock': B / 'arms/pocock',
    'pstack': B / 'arms/pstack-src/plugins/pstack',
    'pstack47': B / 'arms/pstack47',
}
MODEL, TIMEOUT, BUDGET, MIN_FREE_GB = 'claude-opus-5-5', 110 * 60, '80', 4.0
CLAUDE = shutil.which('claude')


def clean_env():
    keep = ('HOME', 'USER', 'PATH', 'SHELL', 'LANG', 'TMPDIR', 'TERM')
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env['SHELL'] = '/bin/zsh'
    return env


def sh(cmd, cwd=None, timeout=900, env=None):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True,
                       timeout=timeout, env=env)
    return p.returncode, (p.stdout + p.stderr)


def free_gb():
    s = os.statvfs(str(B))
    return s.f_bavail * s.f_frsize / 1e9


def task_of(run):
    """Run directories are ARM-TASK-REP and an arm name may hold dashes, so count from the right."""
    return Path(run).name.rsplit('-', 2)[1]


def ensure_fixture():
    """Install the fixture's dependencies once and create the bare origin from the fixture on first use."""
    if not (FIXTURE / 'node_modules').exists():
        code, out = sh('npm ci --no-audit --no-fund', cwd=FIXTURE, timeout=1800)
        if code:
            sys.exit('npm ci failed in the fixture:\n' + out[-2000:])
    if ORIGIN.exists():
        return
    work = B / 'origin-work'
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    try:
        sh('tar -c --exclude=node_modules --exclude=dist . | tar -x -C "%s"' % work, cwd=FIXTURE)
        git = ['git', '-c', 'user.email=bench@example.com', '-c', 'user.name=Bench']
        for cmd in (['git', 'init', '-q', '-b', 'main'], ['git', 'add', '-A'], git + ['commit', '-q', '-m', 'Pulse fixture'],
                    ['git', 'init', '-q', '--bare', '-b', 'main', str(ORIGIN)],
                    ['git', 'push', '-q', str(ORIGIN), 'main']):
            code, out = sh(cmd, cwd=work)
            if code:
                shutil.rmtree(ORIGIN, ignore_errors=True)
                sys.exit('creating the origin failed: ' + out[-500:])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def setup(run):
    ensure_fixture()
    run.mkdir(parents=True)
    sh(['git', 'clone', '-q', '--bare', str(ORIGIN), str(run / 'origin.git')])
    sh(['git', 'clone', '-q', str(run / 'origin.git'), str(run / 'repo')])
    sh(['git', '-C', str(run / 'repo'), 'config', 'user.email', 'bench@example.com'])
    sh(['git', '-C', str(run / 'repo'), 'config', 'user.name', 'Bench'])
    # APFS clone: node_modules costs no disk until a file changes.
    sh(['cp', '-c', '-R', str(FIXTURE / 'node_modules'), str(run / 'repo/node_modules')])


def run_session(arm, task, rep):
    if free_gb() < MIN_FREE_GB:
        sys.exit(f'only {free_gb():.1f} GB free; stopping')
    run = RUNS / f'{arm}-{task}-{rep}'
    if run.exists():
        sys.exit(f'{run} exists')
    setup(run)
    prompt = (TASKS / task / 'prompt.md').read_text()
    cmd = [CLAUDE, '-p', prompt, '--output-format', 'stream-json', '--verbose', '--model', MODEL,
           '--setting-sources', '', '--strict-mcp-config', '--permission-mode', 'bypassPermissions',
           '--max-budget-usd', BUDGET, '--include-hook-events']
    if ARMS[arm]:
        cmd += ['--plugin-dir', str(ARMS[arm])]
    meta = dict(arm=arm, task=task, rep=rep, started=datetime.now().isoformat(), model=MODEL)
    t0 = time.time()
    with open(run / 'stream.jsonl', 'w') as out, open(run / 'stderr.txt', 'w') as err:
        try:
            p = subprocess.run(cmd, cwd=run / 'repo', stdout=out, stderr=err, env=clean_env(), timeout=TIMEOUT)
            meta['exit'] = p.returncode
        except subprocess.TimeoutExpired:
            meta['exit'], meta['timeout'] = 'timeout', True
    meta['wall_s'] = round(time.time() - t0, 1)
    (run / 'meta.json').write_text(json.dumps(meta, indent=1))
    return run


def transcript_spans(run):
    """(start, end) of every subagent, Agent tool and Workflow alike, from the session transcripts on disk."""
    slug = re.sub(r'[^A-Za-z0-9]', '-', str((run / 'repo').resolve()))
    spans = {}
    for f in Path.home().glob('.claude/projects/%s/*/subagents/**/agent-*.jsonl' % slug):
        ts = []
        for line in open(f, errors='replace'):
            try:
                v = json.loads(line).get('timestamp')
            except ValueError:
                continue
            if v:
                ts.append(datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp())
        if ts:
            spans[f.stem] = (min(ts), max(ts))
    return spans


def stream_metrics(run):
    spans, tools, result, t_start, t_end, cost = {}, {}, {}, None, None, 0.0
    first_dispatch = last_push = None
    for line in open(run / 'stream.jsonl'):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        ts = r.get('timestamp')
        t = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp() if ts else None
        if t and t_start is None:
            t_start = t
        if t:
            t_end = t
        if r.get('type') == 'result':
            result = r
            cost = max(cost, r.get('total_cost_usd') or 0)
        pid = r.get('parent_tool_use_id')
        if pid and t:
            s = spans.setdefault(pid, [t, t])
            s[0], s[1] = min(s[0], t), max(s[1], t)
        if r.get('type') == 'assistant':
            for c in r['message'].get('content', []):
                if c.get('type') == 'tool_use':
                    name = c['name']
                    key = ('main:' if not pid else 'sub:') + name
                    tools[key] = tools.get(key, 0) + 1
                    if name == 'Bash' and 'git push' in (c.get('input') or {}).get('command', '') and t and t_start:
                        last_push = round(t - t_start, 1)
                    if not pid and name in ('Agent', 'Task', 'Workflow') and first_dispatch is None and t and t_start:
                        first_dispatch = round(t - t_start, 1)
    file_spans = transcript_spans(run)
    if file_spans:  # subagent transcripts include Workflow agents, which the stream does not show
        spans = file_spans
    meta = json.loads((run / 'meta.json').read_text()) if (run / 'meta.json').exists() else {}
    wall = meta.get('wall_s') or ((t_end - t_start) if t_start and t_end else (result.get('duration_ms') or 0) / 1000)
    busy = sum(min(e, t_start + (last_push or 1e12)) - s for s, e in spans.values() if s)
    events = sorted([(s, 1) for s, _ in spans.values()] + [(e, -1) for _, e in spans.values()])
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    done = last_push or wall
    return dict(wall_s=round(wall, 1), done_s=done, cost_usd=round(cost, 2), turns=result.get('num_turns'),
                is_error=result.get('is_error'), subtype=result.get('subtype'), agents=len(spans),
                agent_busy_s=round(busy, 1), parallelism=round(busy / (last_push or wall), 2) if wall else None,
                peak_agents=peak, first_dispatch_s=first_dispatch, tools=tools,
                final_message=(result.get('result') or '')[-4000:])


def score(run):
    run = Path(run).resolve()  # vitest runs in the run's folder; a relative report path would land inside it
    s = dict(stream=stream_metrics(run))
    org = run / 'origin.git'
    _, refs = sh(['git', '-C', str(org), 'for-each-ref', '--sort=-committerdate', '--format=%(refname:short)', 'refs/heads'])
    branches = [b for b in refs.split() if b != 'main']
    s['pushed_branch'] = branches[0] if branches else None
    _, st = sh(['git', '-C', str(run / 'repo'), 'status', '--porcelain'])
    s['uncommitted_files'] = len([l for l in st.splitlines() if 'node_modules' not in l])
    sc = run / 'score'
    if sc.exists():
        shutil.rmtree(sc)
    ref = s['pushed_branch'] or 'main'
    sh(['git', 'clone', '-q', '-b', ref, str(org), str(sc)])
    _, diffstat = sh(['git', '-C', str(sc), 'diff', '--shortstat', 'origin/main...HEAD'] if branches else ['true'])
    s['diffstat'] = diffstat.strip()
    _, names = sh(['git', '-C', str(sc), 'diff', '--name-only', '--diff-filter=AM', 'origin/main...HEAD'] if branches else ['true'])
    sizes = {n: len((sc / n).read_text(errors='replace').splitlines()) for n in names.split()
             if n.startswith('src/') and n.endswith(('.ts', '.tsx')) and (sc / n).is_file()}
    s['largest_changed_file'] = max(sizes.items(), key=lambda kv: kv[1]) if sizes else None
    _, n = sh(['git', '-C', str(sc), 'rev-list', '--count', 'origin/main..HEAD'] if branches else ['echo', '0'])
    s['commits'] = int(n.strip() or 0)
    sh(['cp', '-c', '-R', str(FIXTURE / 'node_modules'), str(sc / 'node_modules')])
    if (sc / 'package.json').read_text() != (FIXTURE / 'package.json').read_text():
        s['npm_install'] = sh('npm install --prefer-offline --no-audit --no-fund', cwd=sc, timeout=900)[0]
    s['checks'] = {c: sh(f'npm run {c}', cwd=sc, timeout=900)[0] for c in ('typecheck', 'lint', 'test', 'build')}
    hb = sc / 'src/__bench__'
    hb.mkdir(parents=True, exist_ok=True)
    for f in (TASKS / task_of(run) / 'hidden').iterdir():
        shutil.copy(f, hb / f.name)
    rep = sc / 'bench-report.json'
    sh(f'npx vitest run src/__bench__ --reporter=json --outputFile={rep}', cwd=sc, timeout=900)
    tests = []
    if rep.exists():
        for f in json.loads(rep.read_text()).get('testResults', []):
            for a in f.get('assertionResults', []):
                tests.append(dict(name=a.get('title'), status=a.get('status')))
    s['hidden'] = dict(total=len(tests), passed=sum(t['status'] == 'passed' for t in tests),
                       failed=[t['name'] for t in tests if t['status'] != 'passed'])
    _, diff = sh(['git', '-C', str(sc), 'diff', 'origin/main...HEAD', '--', '.', ':!package-lock.json'] if branches else ['true'])
    (run / 'solution.diff').write_text(diff)
    (run / 'score.json').write_text(json.dumps(s, indent=1))
    return s


JUDGE = """You are a blind senior reviewer scoring one solution to a benchmark task. You do not know which tool produced it.
Read the task spec and rubric below, the hidden test results, the final message the agent wrote, and the full diff.
Work only from these inputs; do not run anything. Score as the product owner who wrote the prompt.

Return ONLY a JSON object, no prose, with this shape:
{"asks": [{"id": "A1", "score": 0|1|2, "note": "..."}],
 "defects": [{"ask": "A1 or general", "what": "...", "fix_size": "S|M|L"}],
 "quality": {"test_debt_left": int, "new_suppressions": int, "type_soundness": 0|1|2, "follows_agents_md": 0|1|2},
 "summary": "two sentences"}
Score 2 = done as the spec says; 1 = partly or with a visible flaw; 0 = missing or wrong.
A defect is any change still needed before you would merge: missing asks, bugs, regressions, test debt, sloppy code. fix_size: S under 10 minutes, M under an hour, L more.

## Spec
{spec}

## Rubric
{rubric}

## Hidden test results
{hidden}

## Agent's final message
{final}

## Diff (main...solution)
{diff}
"""


def judge(run):
    run = Path(run)
    s = json.loads((run / 'score.json').read_text())
    task = task_of(run)
    diff = (run / 'solution.diff').read_text()
    if len(diff) > 400_000:
        diff = diff[:400_000] + '\n[diff truncated]'
    parts = dict(spec=(TASKS / task / 'spec.md').read_text(), rubric=(TASKS / task / 'rubric.md').read_text(),
                 hidden=json.dumps(s['hidden']), final=s['stream']['final_message'], diff=diff or '(no diff pushed)')
    prompt = JUDGE
    for k, v in parts.items():
        prompt = prompt.replace('{' + k + '}', v)
    pf = run / 'judge-prompt.md'
    pf.write_text(prompt)
    cmd = [CLAUDE, '-p', 'Score the solution described in the file judge-prompt.md in the current folder. Read it fully, then output only the JSON.',
           '--output-format', 'json', '--model', MODEL, '--setting-sources', '', '--strict-mcp-config',
           '--permission-mode', 'bypassPermissions', '--no-session-persistence', '--allowedTools', 'Read']
    p = subprocess.run(cmd, cwd=run, capture_output=True, text=True, env=clean_env(), timeout=1800)
    out = json.loads(p.stdout).get('result', '')
    i, j = out.find('{'), out.rfind('}')
    data = json.loads(out[i:j + 1])
    (run / 'judge.json').write_text(json.dumps(data, indent=1))
    return data


def repair_work(s, j):
    size = {'S': 1, 'M': 3, 'L': 8}
    fails = sum(1 for v in s['checks'].values() if v != 0)
    return (s['hidden']['total'] - s['hidden']['passed']) + sum(size.get(d.get('fix_size'), 3) for d in j.get('defects', [])) + 3 * fails


def cleanup(run):
    for d in ('score/node_modules', 'repo/node_modules'):
        p = Path(run) / d
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    # Worktrees an arm created inside or beside the repo hold node_modules too.
    _, wt = sh(['git', '-C', str(Path(run) / 'repo'), 'worktree', 'list', '--porcelain'])
    for line in wt.splitlines():
        if line.startswith('worktree ') and line[9:] != str(Path(run) / 'repo'):
            shutil.rmtree(Path(line[9:]) / 'node_modules', ignore_errors=True)


def rubric_rows(task, asks):
    """Fold the judge's ask scores onto the rubric table rows, so a judge that splits one row ("F12 to F17") into
    six scores, or merges six into one, gives the same weight. Returns (points, max)."""
    rows = []
    for line in (TASKS / task / 'rubric.md').read_text().splitlines():
        m = re.match(r'\|\s*([A-Z])(\d+)(?:\s*(?:to|-)\s*[A-Z]?(\d+))?\b', line)
        if m:
            lo = int(m.group(2)); hi = int(m.group(3) or lo)
            rows.append((m.group(1), lo, hi))
    if not rows:
        return sum(a.get('score', 0) for a in asks), 2 * len(asks)
    got = {r: [] for r in rows}
    for a in asks:
        m = re.match(r'([A-Z])(\d+)(?:\s*(?:to|-)\s*[A-Z]?(\d+))?', str(a.get('id', '')))
        if not m:
            continue
        lo = int(m.group(2)); hi = int(m.group(3) or lo)
        for r in rows:
            if r[0] == m.group(1) and r[1] <= lo and hi <= r[2]:
                got[r].append(a.get('score', 0))
                break
    pts = sum(sum(v) / len(v) for v in got.values() if v)
    return round(pts, 1), 2 * len(rows)


def report():
    rows = []
    for run in sorted(RUNS.iterdir()) if RUNS.exists() else []:
        if not (run / 'judge.json').exists():
            continue
        s, j = json.loads((run / 'score.json').read_text()), json.loads((run / 'judge.json').read_text())
        asks = j.get('asks', [])
        rows.append(dict(run=run.name, done_min=round(s['stream']['done_s'] / 60, 1), wall_min=round(s['stream']['wall_s'] / 60, 1), cost=s['stream']['cost_usd'],
                         par=s['stream']['parallelism'], peak=s['stream']['peak_agents'],
                         hidden=f"{s['hidden']['passed']}/{s['hidden']['total']}",
                         rubric='%s/%s' % rubric_rows(run.name.rsplit('-', 2)[1], asks),
                         checks=''.join('ok'[0] if v == 0 else 'x' for v in s['checks'].values()),
                         repair=repair_work(s, j), pushed=bool(s['pushed_branch']),
                         largest=(s.get('largest_changed_file') or [None, 0])[1]))
    print(json.dumps(rows, indent=1))
    return rows


def queue(items):
    for it in items:
        try:
            queue_one(it)
        except Exception as e:  # never loop on a broken run: two failures mark it skipped
            run = RUNS / '-'.join(it.split(':'))
            run.mkdir(parents=True, exist_ok=True)
            fails = run / 'failures'
            n = int(fails.read_text()) + 1 if fails.exists() else 1
            fails.write_text(str(n))
            print(datetime.now().strftime('%H:%M'), 'FAILED', run.name, f'({n})', repr(e)[:300], flush=True)
            if n >= 2:
                (run / 'skip').write_text(repr(e))


def queue_one(it):
    if True:
        arm, task, rep = it.split(':')
        if arm not in ARMS:
            raise KeyError(f'unknown arm {arm}; add it to ARMS')
        run = RUNS / f'{arm}-{task}-{rep}'
        if not run.exists():
            print(datetime.now().strftime('%H:%M'), 'run', run.name, flush=True)
            run_session(arm, task, rep)
        if not (run / 'score.json').exists():
            print(datetime.now().strftime('%H:%M'), 'score', run.name, flush=True)
            score(run)
        if not (run / 'judge.json').exists():
            print(datetime.now().strftime('%H:%M'), 'judge', run.name, flush=True)
            try:
                judge(run)
            except Exception as e:
                print('judge failed', run.name, e, flush=True)
        cleanup(run)
        print(datetime.now().strftime('%H:%M'), 'done', run.name, f'{free_gb():.1f} GB free', flush=True)


def queue_file(path):
    """Run items from a file, one at a time; the file is re-read before each item, so it can be edited live."""
    path = Path(path)
    while True:
        items = [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.startswith('#')]
        todo = [i for i in items if not (RUNS / '-'.join(i.split(':')) / 'judge.json').exists()
                and not (RUNS / '-'.join(i.split(':')) / 'skip').exists()]
        if not todo:
            print(datetime.now().strftime('%H:%M'), 'queue empty', flush=True)
            return
        import threading
        ensure_fixture()  # once, before the pair: two threads must not run npm ci in the fixture at the same time
        pair = todo[:2]
        threads = [threading.Thread(target=queue, args=([it],)) for it in pair]
        for th in threads:
            th.start()
            time.sleep(5)
        for th in threads:
            th.join()


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'run':
        run_session(*args)
    elif cmd == 'score':
        print(json.dumps(score(args[0]), indent=1))
    elif cmd == 'judge':
        print(json.dumps(judge(args[0]), indent=1))
    elif cmd == 'queue':
        queue(args)
    elif cmd == 'queue-file':
        queue_file(args[0])
    elif cmd == 'report':
        report()
