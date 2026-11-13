"""The test gate: `lean.py gate ...` (see docs/hooks.md). State is <git common dir>/orchestra/gate.json (the folder's
.orchestra outside a repository), keyed by branch: {branch: {"full": {"head", "exit", "cmd"}, "skips": {kind: {"reason", "head"}},
"runs": {kind: [{"head", "cmd", "exit", "time", and for an e2e run that left out no test "left_out", "ran"} ...]}, "claim": {"pid", "start", "limit"}}, plus a top-level
"runner": {kind: true} set when a run of that kind is first recorded and never cleared; runs keep only HEAD's latest
record per command; the claim marks the running full unit run and is dropped when it ends."""
import contextlib, os, shlex, sys, time
from pathlib import Path

import e2e_checks, lean
from procs import alive, exclusive
from gate_scope import e2e_scoped, filters_missing, nothing_to_gate, refuse_empty

KINDS = ('unit', 'e2e')
SECONDS = 600.0


def file(cwd=None):
    common = lean.git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=cwd)
    return (Path(common) / 'orchestra' if common else Path(cwd or os.getcwd()) / '.orchestra') / 'gate.json'


def branch_of(cwd):
    return lean.git('branch', '--show-current', cwd=cwd) or 'HEAD'


@contextlib.contextmanager
def locked(f):
    f.parent.mkdir(parents=True, exist_ok=True)
    with exclusive(f.with_name(f.name + '.lock')):
        yield


def runner_of(cwd):
    runner = lean.read_json(file(cwd)).get('runner')
    return {k: isinstance(runner, dict) and runner.get(k) is True for k in KINDS}


def record(cwd, update, kind=None):
    f = file(cwd)
    with locked(f):
        data = lean.read_json(f)
        if kind:
            data['runner'] = {**(data['runner'] if isinstance(data.get('runner'), dict) else {}), kind: True}
        entry = data.get(branch_of(cwd))
        entry = entry if isinstance(entry, dict) else {}
        update(entry)
        data[branch_of(cwd)] = entry
        lean.write_json(f, data)


def live(h, cwd):
    """True when commit h is in HEAD's history and not reachable from the default branch (the branch's own work)."""
    head = lean.git('rev-parse', 'HEAD', cwd=cwd)
    seen = lambda ref: lean.git('merge-base', h, ref, cwd=cwd) == h
    d = lean.default_branch(cwd)
    return not h if not head else bool(h) and seen(head) and not (seen('refs/heads/' + d) or seen('refs/remotes/origin/' + d))


def fresh(entry, cwd):
    """(full, skips) of a branch entry, without those whose head is gone or already on the default branch."""
    full, skips = entry.get('full'), entry.get('skips')
    return (full if isinstance(full, dict) and live(full.get('head'), cwd) else {},
            {k: v for k, v in skips.items() if isinstance(v, dict) and live(v.get('head'), cwd)} if isinstance(skips, dict) else {})


def entry_of(cwd):
    entry = lean.read_json(file(cwd)).get(branch_of(cwd))
    entry = entry if isinstance(entry, dict) else {}
    runs = entry.get('runs') if isinstance(entry.get('runs'), dict) else {}
    runs = {k: [r for r in runs[k] if isinstance(r, dict)] if isinstance(runs.get(k), list) else [] for k in KINDS}
    full, skips = fresh(entry, cwd)
    return {'full': full, 'skips': skips, 'runs': runs,
            'runner': runner_of(cwd)}


def latest(runs, head):
    return {r.get('cmd'): r.get('exit') for r in runs if r.get('head') == head}


def green(runs, head):
    """True when HEAD has a run and the latest run of every distinct command at HEAD exited 0."""
    return bool(latest(runs, head)) and all(x == 0 for x in latest(runs, head).values())


def missing(cwd):
    """What the pre-PR gate still lacks for HEAD; empty when it holds."""
    if nothing_to_gate(cwd):
        return []
    e, head = entry_of(cwd), lean.git('rev-parse', 'HEAD', cwd=cwd)
    out = []
    skipped = lambda k: k in e['skips'] and not e['runner'][k]  # a repository with a runner of that kind never skips it
    hint = lambda k: '' if e['runner'][k] else f' (or gate skip {k} REASON)'
    if not skipped('unit'):
        if not e['full']:
            out.append('no full unit run recorded for the branch: gate unit --full -- CMD' + hint('unit'))
        elif not green(e['runs']['unit'], head):
            out.append('no green unit run at the current head (every command run there must pass): gate unit --scoped -- CMD')
    if not skipped('e2e') and not green(e['runs']['e2e'], head):
        out.append('no green e2e run at the current head (every command run there must pass): gate e2e -- CMD with a scope flag' + hint('e2e'))
    if out and e['full'].get('exit') not in (0, None):
        out.append(f"the full unit run was red (exit {e['full']['exit']}): {e['full'].get('cmd')}")
    return ['test gate: ' + m for m in out]


def take(entry, seconds, cwd=None):
    """Under the lock, claim the full run; the refusal text when taken. A claim counts while its pid lives and now <= start + limit + 30 s."""
    c = entry.get('claim')
    try:
        c = c if time.time() <= c['start'] + c['limit'] + 30 and alive(c['pid']) else None
    except (KeyError, TypeError):
        c = None
    entry['full'], entry['skips'] = fresh(entry, cwd)
    if entry['full']:
        return 'a full run is already recorded for this branch; run scoped (gate unit --scoped -- CMD)'
    if c:
        return f"a full run is running for this branch (started {time.strftime('%H:%M:%S', time.localtime(c['start']))}); run scoped"
    entry['claim'] = {'pid': os.getpid(), 'start': int(time.time()), 'limit': seconds}


def run(kind, mode, seconds, cmd, cwd=None):
    """Run cmd bounded and record it; returns its exit code, or 3 for a refusal."""
    if mode == 'full':
        if refuse_empty(cwd):
            return 3
        busy = []
        record(cwd, lambda entry: busy.append(take(entry, seconds, cwd)))
        if busy[0]:
            print('gate: ' + busy[0], file=sys.stderr)
            return 3
    cfg = filters_missing(cmd, cwd) if kind == 'e2e' else ''
    if kind == 'e2e' and os.environ.get('ORCHESTRA_E2E_FULL') != '1' and (cfg or not e2e_scoped(cmd, cwd)):  # the owner allows a full run
        print(f'gate: {cfg} has no `filters`, so --changed-since runs every test. Fix: add `filters` to it, or scope with --grep, --tag or a test file.' if cfg else
              'gate: this e2e command is not scoped. Add --changed-since REF, --grep, --tag or a test file path; the owner allows a full run with ORCHESTRA_E2E_FULL=1.', file=sys.stderr)
        return 3
    started = time.time()
    try:
        rc = lean.run_bounded(seconds, cmd)
    except OSError as err:
        print(f'gate: cannot start {cmd[0]}: {err}', file=sys.stderr)
        return 127
    head, left = lean.git('rev-parse', 'HEAD', cwd=cwd), e2e_checks.left_out(cmd, cwd, started) if kind == 'e2e' else {}

    def update(entry):
        text = shlex.join(cmd)
        runs = entry['runs'] = entry['runs'] if isinstance(entry.get('runs'), dict) else {}
        old = runs.get(kind) if isinstance(runs.get(kind), list) else []
        runs[kind] = [r for r in old if isinstance(r, dict) and r.get('head') == head and r.get('cmd') != text]
        runs[kind].append({'head': head, 'cmd': text, 'exit': rc, 'time': int(time.time()), **left})
        if mode == 'full':
            entry.pop('claim', None)  # a timeout or kill leaves no claim and no record: a new full run may start
            if rc not in (124, 126, 127) and rc <= 128:  # a timeout, a kill or a command that did not start leaves no verdict
                entry['full'] = {'head': head, 'exit': rc, 'cmd': text}

    record(cwd, update, kind)
    return rc


def main(args, cwd=None):
    if args[:1] == ['status']:
        lack = missing(cwd)
        print('\n'.join(lack) if lack else 'test gate holds for HEAD')
        e2e_checks.status_note(entry_of(cwd)['runs']['e2e'], lean.git('rev-parse', 'HEAD', cwd=cwd))
        return 1 if lack else 0
    if args[:1] == ['skip']:
        if len(args) < 3 or args[1] not in KINDS:
            return lean.usage()
        if refuse_empty(cwd):
            return 3
        if args[1] == 'e2e' and e2e_checks.refuse_skip(cwd):
            return 3
        if runner_of(cwd)[args[1]]:
            print(f'gate: this repository has a {args[1]} runner: runs are recorded; a skip is for a repo with no runner', file=sys.stderr)
            return 3
        skip = {'reason': ' '.join(args[2:]), 'head': lean.git('rev-parse', 'HEAD', cwd=cwd)}
        record(cwd, lambda entry: entry.__setitem__('skips', {**fresh(entry, cwd)[1], args[1]: skip}))
        return 0
    if args[:1] and args[0] in KINDS and '--' in args:
        opts, cmd = args[1:(i := args.index('--'))], args[i + 1:]
        mode, seconds = None, SECONDS
        while opts:
            if opts[0] in ('--full', '--scoped') and args[0] == 'unit':
                mode = opts[0][2:]
            elif opts[0] == '--seconds' and len(opts) > 1:
                try:
                    seconds = float(opts[1])
                except ValueError:
                    return lean.usage()
                opts = opts[1:]
            else:
                return lean.usage()
            opts = opts[1:]
        if cmd and seconds > 0 and seconds != float('inf') and (mode or args[0] == 'e2e'):
            return run(args[0], mode, seconds, cmd, cwd)
    return lean.usage()
