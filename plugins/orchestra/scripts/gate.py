"""The test gate: `lean.py gate ...` (see docs/hooks.md). State is gate.json beside goal.json, keyed by branch:
{branch: {"full": {"head", "exit"}, "runs": {"unit"|"e2e": {"head", "exit"}}, "skips": {"unit"|"e2e": reason}}}."""
import os, re, sys

import lean

KINDS = ('unit', 'e2e')
SCOPE_FLAGS = ('--changed-since', '--grep', '--tag', '--last-failed', '--shard')
TEST_FILE = re.compile(r'\.(e2e|spec|test)\.\w+$')
SECONDS = 600.0


def file(cwd=None, session=None):
    return lean.state_dir(cwd, session) / 'gate.json'


def branch_of(cwd):
    return lean.git('branch', '--show-current', cwd=cwd) or 'HEAD'


def e2e_scoped(cmd):
    return any(a.split('=')[0] in SCOPE_FLAGS or (not a.startswith('-') and TEST_FILE.search(a)) for a in cmd)


def completed(rc):
    return rc != 124 and rc <= 128  # a timeout or a signal kill leaves no verdict


def record(cwd, session, update):
    f = file(cwd, session)
    data = lean.read_json(f)
    entry = data.get(branch_of(cwd))
    entry = entry if isinstance(entry, dict) else {}
    update(entry)
    data[branch_of(cwd)] = entry
    lean.state_dir(cwd, session, create=True)
    lean.write_json(f, data)


def entry_of(cwd, session):
    entry = lean.read_json(file(cwd, session)).get(branch_of(cwd))
    entry = entry if isinstance(entry, dict) else {}
    return {k: entry[k] if isinstance(entry.get(k), dict) else {} for k in ('full', 'runs', 'skips')}


def missing(cwd, session):
    """What the pre-PR gate still lacks for HEAD; empty when it holds."""
    e, head = entry_of(cwd, session), lean.git('rev-parse', 'HEAD', cwd=cwd)
    green = {k: (e['runs'].get(k) or {}) for k in KINDS}
    green = {k: r.get('head') == head and r.get('exit') == 0 for k, r in green.items()}
    out = []
    if 'unit' not in e['skips']:
        if not e['full']:
            out.append('no full unit run recorded for the branch: gate unit --full -- CMD (or gate skip unit REASON)')
        elif not green['unit']:
            out.append('no green unit run at the current head: gate unit --scoped -- CMD')
    if 'e2e' not in e['skips'] and not green['e2e']:
        out.append('no green e2e run at the current head: gate e2e -- CMD with a scope flag (or gate skip e2e REASON)')
    return ['test gate: ' + m for m in out]


def run(kind, mode, seconds, cmd, cwd=None, session=None):
    """Run cmd bounded and record it; returns its exit code, or 3 for a refusal."""
    e = entry_of(cwd, session)
    if mode == 'full' and e['full']:
        print('gate: a full run is already recorded for this branch; run scoped (gate unit --scoped -- CMD)', file=sys.stderr)
        return 3
    if kind == 'e2e' and not e2e_scoped(cmd) and os.environ.get('ORCHESTRA_E2E_FULL') != '1':
        print('gate: this e2e command is not scoped. Add --changed-since REF, --grep, --tag, --last-failed, --shard or a '
              'test file path; the owner allows a full run with ORCHESTRA_E2E_FULL=1.', file=sys.stderr)
        return 3
    try:
        rc = lean.run_bounded(seconds, cmd)
    except OSError as err:
        print(f'gate: cannot start {cmd[0]}: {err}', file=sys.stderr)
        return 127
    head = lean.git('rev-parse', 'HEAD', cwd=cwd)

    def update(entry):
        entry.setdefault('runs', {})[kind] = {'head': head, 'exit': rc}
        if mode == 'full' and completed(rc):
            entry['full'] = {'head': head, 'exit': rc}

    record(cwd, session, update)
    return rc


def main(args, cwd=None, session=None):
    session = session or os.environ.get(lean.SESSION_ENV) or None
    if args[:1] == ['status']:
        lack = missing(cwd, session)
        print('\n'.join(lack) if lack else 'test gate holds for HEAD')
        return 1 if lack else 0
    if args[:1] == ['skip']:
        if len(args) < 3 or args[1] not in KINDS:
            return lean.usage()
        record(cwd, session, lambda entry: entry.setdefault('skips', {}).__setitem__(args[1], ' '.join(args[2:])))
        return 0
    if args[:1] and args[0] in KINDS and '--' in args:
        i = args.index('--')
        opts, cmd = args[1:i], args[i + 1:]
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
            return run(args[0], mode, seconds, cmd, cwd, session)
    return lean.usage()
