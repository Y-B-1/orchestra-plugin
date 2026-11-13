"""The test gate: `lean.py gate ...` (see docs/hooks.md). State is <git common dir>/orchestra/gate.json (the folder's
.orchestra outside a repository), keyed by branch: {branch: {"full": {"head", "exit"}, "skips": {kind: reason},
"runs": {kind: [{"head", "cmd", "exit", "time"} ...]}, "claim": {"pid", "start", "limit"}}}; runs keep only HEAD's latest
record per command; the claim marks the running full unit run and is dropped when it ends."""
import contextlib, os, re, shlex, sys, time
from pathlib import Path

try:
    import fcntl
except ImportError:  # no flock here: the unique temp file in lean.write_json still keeps the file whole
    fcntl = None

import lean

KINDS = ('unit', 'e2e')
SCOPE_FLAGS = ('--changed-since', '--grep', '-g', '--tag', '--last-failed', '--shard', '--only-changed', '--spec')
VALUE_FLAGS = ('--config', '-c', '--project')
TEST_FILE = re.compile(r'\.(e2e|spec|test|cy)\.\w+$')
SECONDS = 600.0
RUNNERS = ('npm', 'pnpm', 'yarn', 'bun')


def file(cwd=None):
    common = lean.git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=cwd)
    return (Path(common) / 'orchestra' if common else Path(cwd or os.getcwd()) / '.orchestra') / 'gate.json'


def branch_of(cwd):
    return lean.git('branch', '--show-current', cwd=cwd) or 'HEAD'


def script_words(cmd, cwd, depth=0):
    """cmd, with a package script replaced by the words of its package.json text; None when the script is unknown."""
    if len(cmd) < 2 or cmd[0] not in RUNNERS:
        return cmd
    if cmd[1] in ('run', 'run-script'):
        rest = cmd[2:]
    elif cmd[0] != 'npm' or cmd[1] == 'test':
        rest = cmd[1:]
    else:
        return cmd
    scripts = lean.read_json(Path(cwd or '.') / 'package.json').get('scripts')
    text = scripts.get(rest[0]) if rest and isinstance(scripts, dict) else None
    if not isinstance(text, str) or depth > 3:
        return None
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return None
    if any(set(w) <= set(';&|()') for w in words):
        return None  # a chained or substituted script: one scope flag proves nothing about the rest
    extra = rest[1:]
    if cmd[0] == 'npm':  # npm keeps flags before `--` for itself; only what follows `--` reaches the script
        extra = extra[extra.index('--') + 1:] if '--' in extra else []
    return script_words(words + [a for a in extra if a != '--'], cwd, depth + 1)


def e2e_scoped(cmd, cwd=None):
    skip = False
    for a in script_words(cmd, cwd) or ():
        if skip:
            skip = False
        elif a in VALUE_FLAGS:
            skip = True
        elif a.split('=')[0] in SCOPE_FLAGS or (not a.startswith('-') and TEST_FILE.search(a)):
            return True
    return False


@contextlib.contextmanager
def locked(f):
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f.with_name(f.name + '.lock'), 'a') as lock:
        if fcntl:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX)
            except OSError:  # no lock support here (a network filesystem): the unique temp file still keeps the file whole
                pass
        yield


def record(cwd, update):
    f = file(cwd)
    with locked(f):
        data = lean.read_json(f)
        entry = data.get(branch_of(cwd))
        entry = entry if isinstance(entry, dict) else {}
        update(entry)
        data[branch_of(cwd)] = entry
        lean.write_json(f, data)


def entry_of(cwd):
    entry = lean.read_json(file(cwd)).get(branch_of(cwd))
    entry = entry if isinstance(entry, dict) else {}
    runs = entry.get('runs') if isinstance(entry.get('runs'), dict) else {}
    return {'full': entry['full'] if isinstance(entry.get('full'), dict) else {},
            'skips': entry['skips'] if isinstance(entry.get('skips'), dict) else {},
            'runs': {k: [r for r in runs[k] if isinstance(r, dict)] if isinstance(runs.get(k), list) else [] for k in KINDS}}


def green(runs, head):
    """True when HEAD has a run and the latest run of every distinct command at HEAD exited 0."""
    latest = {r.get('cmd'): r.get('exit') for r in runs if r.get('head') == head}
    return bool(latest) and all(x == 0 for x in latest.values())


def missing(cwd):
    """What the pre-PR gate still lacks for HEAD; empty when it holds."""
    e, head = entry_of(cwd), lean.git('rev-parse', 'HEAD', cwd=cwd)
    out = []
    if 'unit' not in e['skips']:
        if not e['full']:
            out.append('no full unit run recorded for the branch: gate unit --full -- CMD (or gate skip unit REASON)')
        elif not green(e['runs']['unit'], head):
            out.append('no green unit run at the current head (every command run there must pass): gate unit --scoped -- CMD')
    if 'e2e' not in e['skips'] and not green(e['runs']['e2e'], head):
        out.append('no green e2e run at the current head (every command run there must pass): gate e2e -- CMD with a scope flag (or gate skip e2e REASON)')
    return ['test gate: ' + m for m in out]


def take(entry, seconds):
    """Under the lock, claim the full run; the refusal text when taken. A claim counts while its pid lives and now <= start + limit + 30 s."""
    c = entry.get('claim')
    try:
        c = c if time.time() <= c['start'] + c['limit'] + 30 and not os.kill(c['pid'], 0) else None
    except (OSError, KeyError, TypeError) as err:
        c = c if isinstance(err, PermissionError) else None  # a pid owned by someone else still exists
    if entry.get('full'):
        return 'a full run is already recorded for this branch; run scoped (gate unit --scoped -- CMD)'
    if c:
        return f"a full run is running for this branch (started {time.strftime('%H:%M:%S', time.localtime(c['start']))}); run scoped"
    entry['claim'] = {'pid': os.getpid(), 'start': int(time.time()), 'limit': seconds}


def run(kind, mode, seconds, cmd, cwd=None):
    """Run cmd bounded and record it; returns its exit code, or 3 for a refusal."""
    if mode == 'full':
        busy = []
        record(cwd, lambda entry: busy.append(take(entry, seconds)))
        if busy[0]:
            print('gate: ' + busy[0], file=sys.stderr)
            return 3
    if kind == 'e2e' and not e2e_scoped(cmd, cwd) and os.environ.get('ORCHESTRA_E2E_FULL') != '1':
        print('gate: this e2e command is not scoped. Add --changed-since REF, --grep, --tag, --last-failed, --shard or a test file path; the owner allows a full run with ORCHESTRA_E2E_FULL=1.', file=sys.stderr)
        return 3
    try:
        rc = lean.run_bounded(seconds, cmd)
    except OSError as err:
        print(f'gate: cannot start {cmd[0]}: {err}', file=sys.stderr)
        return 127
    head = lean.git('rev-parse', 'HEAD', cwd=cwd)

    def update(entry):
        text = shlex.join(cmd)
        runs = entry['runs'] = entry['runs'] if isinstance(entry.get('runs'), dict) else {}
        old = runs.get(kind) if isinstance(runs.get(kind), list) else []
        runs[kind] = [r for r in old if isinstance(r, dict) and r.get('head') == head and r.get('cmd') != text]
        runs[kind].append({'head': head, 'cmd': text, 'exit': rc, 'time': int(time.time())})
        if mode == 'full':
            entry.pop('claim', None)  # a timeout or kill leaves no claim and no record: a new full run may start
            if rc != 124 and rc <= 128:  # a timeout or a signal kill leaves no verdict
                entry['full'] = {'head': head, 'exit': rc}

    record(cwd, update)
    return rc


def main(args, cwd=None):
    if args[:1] == ['status']:
        lack = missing(cwd)
        print('\n'.join(lack) if lack else 'test gate holds for HEAD')
        return 1 if lack else 0
    if args[:1] == ['skip']:
        if len(args) < 3 or args[1] not in KINDS:
            return lean.usage()
        record(cwd, lambda entry: entry.setdefault('skips', {}).__setitem__(args[1], ' '.join(args[2:])))
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
            return run(args[0], mode, seconds, cmd, cwd)
    return lean.usage()
