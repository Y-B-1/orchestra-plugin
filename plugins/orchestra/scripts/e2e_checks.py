"""e2e checks around the gate (see docs/hooks.md): the skip refusal, the left-out note and `lean.py e2e-doctor`."""
import os, re, sys
from pathlib import Path

import lean
from gate_scope import config_path, runner_words, scopes, script_words

SETUP = 'npx e2e init --yes, then npm install --save-dev e2e @e2e-dev/web ai@^7'  # .agents/skills/e2e/references/setup.md
KEY = re.compile(r'\b[A-Z][A-Z0-9_]*_API_KEY\b')


def rel(path, cwd):
    return os.path.relpath(os.path.realpath(path), os.path.realpath(cwd or '.'))


def refuse_skip(cwd):
    """True (after printing why) when `gate skip e2e` meets an e2e config and the owner has not set ORCHESTRA_E2E_SKIP=1."""
    cfg = config_path([], cwd)
    if cfg and os.environ.get('ORCHESTRA_E2E_SKIP') != '1':
        print(f'gate: this repo has an e2e config ({rel(cfg, cwd)}), so e2e runs scoped instead of skipped: '
              'gate e2e -- e2e run --changed-since <base>. The owner allows a skip with ORCHESTRA_E2E_SKIP=1.', file=sys.stderr)
        return True
    return False


def note(n):
    return (f'gate: this --changed-since run left out no test ({n} of {n} ran). The filter may have failed open: '
            'check the model key and `filters` (lean.py e2e-doctor).')


def left_out(cmd, cwd):
    """{'left_out': 0} (after printing the note) when a run scoped only by --changed-since of the agentic runner ran every test in its report; else {}."""
    words = runner_words(script_words(cmd, cwd) or [])
    if words[:2] != ['e2e', 'run'] or scopes(cmd, cwd) != {'--changed-since'}:
        return {}
    out = next((w[9:] if w.startswith('--output=') else words[i + 1] for i, w in enumerate(words)
                if w.startswith('--output=') or w == '--output' and i + 1 < len(words)), None)
    cfg = config_path(words, cwd)
    report = Path(cwd or '.') / out if out else cfg.parent / '.e2e' if cfg else None
    results = ((lean.read_json(report / 'report.json').get('run') or {}).get('results') if report else None) or []
    if len(results) < 2 or not all(isinstance(r, dict) and r.get('selected') is True for r in results):
        return {}
    print(note(len(results)), file=sys.stderr)
    return {'left_out': 0, 'ran': len(results)}


def status_note(runs, head):
    """Print the note for a recorded run at head that left out no test."""
    for r in runs:
        if r.get('head') == head and r.get('left_out') == 0 and isinstance(r.get('ran'), int):
            print(note(r['ran']))
            return


def doctor(args, cwd=None):
    """`lean.py e2e-doctor [--config PATH]`: local file checks of the e2e setup, one `ok` or `gap` line each; exit 0, 1 on a gap, 2 on bad usage."""
    if args and not (len(args) == 2 and args[0] == '--config'):
        return lean.usage()
    cfg = config_path(args, cwd)
    if not cfg or not cfg.is_file():
        print(f'gap no e2e config found (e2e.config.ts, .mts, .js or .mjs). Set up: {SETUP}')
        return 1
    text, folder, lines = cfg.read_text(errors='replace'), cfg.parent, []
    lines.append(f'ok config {rel(cfg, cwd)}')
    lines.append(('ok' if 'filters' in text else 'gap') + ' filters in the config' + ('' if 'filters' in text else ': without it --changed-since runs every test'))
    pkg = lean.read_json(folder / 'package.json')
    deps = {k for d in ('dependencies', 'devDependencies') if isinstance(pkg.get(d), dict) for k in pkg[d]}
    for name in ('e2e', '@e2e-dev/decision'):
        lines.append(('ok' if name in deps else 'gap') + f' package {name} in package.json')
    env = {k for f in folder.glob('.env*.local') if f.is_file() for k in re.findall(r'^\s*(?:export\s+)?(\w+)\s*=', f.read_text(errors='replace'), re.M)}
    for name in sorted(set(KEY.findall(text))) or [None]:
        lines.append('ok no API key named in the config' if name is None else
                     ('ok' if os.environ.get(name) or name in env else 'gap') + f' key {name} (set in the environment or a .env*.local file)')
    top = lean.git('rev-parse', '--show-toplevel', cwd=cwd) or str(cwd or '.')
    skill = Path(top) / '.agents' / 'skills' / 'e2e' / 'SKILL.md'
    lines.append(('ok' if skill.is_file() else 'gap') + ' project skill .agents/skills/e2e/SKILL.md')
    print('\n'.join(lines))
    return 1 if any(x.startswith('gap') for x in lines) else 0
