"""Brief skeletons and launch calls written from card facts: `card` and `wave --emit`. Nothing here changes run state."""
import json
import re
from pathlib import Path

from . import now
from .engine import PACKAGE_ROOT, EngineError, KEEP_REMOVE
from .paths import atomic

RUN_STATE = 'Run state now: %s (read it only when you need to know what other cards are doing).'
DEFAULT_KEEP = 'Every existing test and public behavior the acceptance lines do not name.'


def dispatch_for(task):
    """(agent type, model override) for a card, read from config/models.json. A preset that differs from its role is its
    own agent file (`orchestra:role-preset`); a `dispatch: override` preset (the repair card) keeps the role's agent and
    names the model to override with. The card's mode names the preset; a `variant` key picks another (a reviewer lens)."""
    models = json.loads((PACKAGE_ROOT / 'config/models.json').read_text())['claude']
    role, matrix = task['role'], models.get(task['role'])
    if matrix is None:
        raise EngineError('No agent for role ' + str(role))
    presets = matrix.get('presets', {})
    name = task['variant'] if 'variant' in task else task['mode']
    if 'variant' in task and (not isinstance(name, str) or name not in presets):
        raise EngineError('Unknown variant %r for role %s: use one of %s' % (name, role, ', '.join(sorted(presets)) or 'none'))
    preset = presets.get(name)
    if preset is None or ((preset['model'], preset['effort']) == (matrix['model'], matrix['effort']) and preset.get('dispatch') != 'override'):
        return 'orchestra:' + role, None
    if preset.get('dispatch') == 'override':
        return 'orchestra:' + role, preset['model']
    return 'orchestra:%s-%s' % (role, name), None


def _lines(items, empty):
    return '\n'.join('- ' + i for i in items) if items else empty


def render(task, repo, base, prep=()):
    """The brief skeleton for a card: Mode line, objective, ownership, numbered acceptance lines repeated as the
    SELF_REVIEW criteria skeleton, Keep and Remove for a builder, the plugin root, the base commit and the report contract."""
    builder = task['role'] == 'builder'
    objective = task.get('outcome') or task.get('objective') or 'Complete card ' + task['id'] + '.'
    parts = ['# Card %s: %s %s' % (task['id'], task['role'], task['mode']), '', 'Mode: ' + task['mode'], '',
             '## Objective', objective, '', 'Inputs:', _lines(task['inputs'], '- none'), '',
             '## Ownership', 'Edit only these files:', _lines(task['files'], '- none: this card edits no file'), '',
             'Resources:', _lines(task['resources'], '- none'), '',
             '## Acceptance',
             'Each line is done when it holds; copy it verbatim as one SELF_REVIEW criterion text (the engine compares them).']
    parts += ['%d. %s' % (n, line) for n, line in enumerate(task['acceptance'], 1)]
    if builder:
        parts += ['', KEEP_REMOVE[0], _lines(task.get('keep') or [DEFAULT_KEEP], '- none'),
                  '', KEEP_REMOVE[1], _lines(task.get('remove') or [], 'none')]
    if prep:
        parts += ['', '## Prep notes']
        for prep_id, note in prep:
            parts += ['', '### ' + prep_id, note]
    parts += ['', '## Run state',
              RUN_STATE % "the run's NOW.md in the state directory that `orchestra.py where` prints"]
    parts += ['', '## Starting point', '- Repository: ' + str(repo), '- Base commit: ' + base,
              '- Plugin root: %s (skills under <root>/skills/, CLI <root>/scripts/orchestra.py)' % PACKAGE_ROOT, '',
              '## Report contract', 'STATUS: PASS|ISSUES|BLOCKED', 'ARTIFACT: <full commit sha> <clean, or dirty-tree fingerprint>']
    if builder:
        skeleton = dict(checks=[dict(command='<command>', exit_code=0)],
                        criteria=[dict(criterion=line, met=True, evidence='<evidence>') for line in task['acceptance']])
        parts += ['Then a short summary, then exactly one line:', 'SELF_REVIEW: ' + json.dumps(skeleton)]
    else:
        parts += ['Then a short summary of findings, evidence and unresolved gaps.']
    return '\n'.join(parts) + '\n'


def _head(engine):
    return engine._git('rev-parse', 'HEAD').decode().strip()


def _own_brief(engine, task):
    if 'brief' not in task:
        return None
    path = Path(task['brief'])
    return path if path.is_absolute() else engine.repo / path


def prep_notes(engine, task):
    """(card id, report text without its SELF_REVIEW line) for each accepted card whose prep_for names this card."""
    return [(t['id'], '\n'.join(l for l in t['report'].splitlines() if not l.startswith('SELF_REVIEW:')).strip())
            for t in engine.status()['tasks'].values()
            if t.get('prep_for') == task['id'] and t['state'] == 'accepted' and 'report' in t]


def text_of(engine, task):
    """(brief text, path of the card's own brief or None). Refuses a brief without its Mode line."""
    own = _own_brief(engine, task)
    text = own.read_text(errors='replace') if own is not None and own.is_file() else render(task, engine.repo, _head(engine), prep_notes(engine, task))
    if not re.search(r'^Mode:[ \t]+' + re.escape(task['mode']) + r'[ \t]*$', text, re.M):
        raise EngineError('Task brief must carry the line Mode: ' + task['mode'])
    return text, own


def prepare(engine, task_ids, inline=None):
    """Everything `wave --emit` needs, checked before the start so a refusal leaves every card queued."""
    ids = [inline, *task_ids] if inline is not None and inline not in task_ids else list(task_ids)
    tasks = engine.status()['tasks']
    plan = []
    for task_id in ids:
        if task_id in tasks:
            task = tasks[task_id]
            plan.append((task, text_of(engine, task), None if task_id == inline else dispatch_for(task)))
    return dict(plan=plan, size=len(ids), base=_head(engine))


def emit(engine, prepared, result):
    """One object per started card: the brief path (written under <state>/briefs/), the exact prompt and the agent() call."""
    entries = []
    for task, (text, own), dispatch in prepared['plan']:
        path = own if own is not None and own.is_file() else engine.state_dir / 'briefs' / (task['id'] + '.md')
        if path.parent == engine.state_dir / 'briefs':
            atomic(path, text.encode())
        worker, token = result['workers'][task['id']], result['assignments'][task['id']]
        entry = dict(task=task['id'], role=task['role'], mode=task['mode'], worker=worker, token=token,
                     inline=dispatch is None, brief=str(path))
        if dispatch is not None:
            agent_type, override = dispatch
            isolation = 'worktree' if task['role'] == 'builder' and prepared['size'] > 1 else None
            forward = 'git merge --ff-only ' + prepared['base'] if isolation else None
            prompt = 'Read your brief at %s and do exactly what it says.\nAssignment: %s %s\n' % (path, worker, token)
            prompt += RUN_STATE % (engine.state_dir / 'NOW.md') + '\n'
            if forward:
                prompt += ('First run `%s`, and check `git rev-parse HEAD` prints %s before any edit; stop BLOCKED if it does not.\n'
                           % (forward, prepared['base']))
            options = ["agentType: '%s'" % agent_type]
            if isolation:
                options.append("isolation: '%s'" % isolation)
            if override:
                options.append("model: '%s'" % override)
            entry.update(agent_type=agent_type, model_override=override, isolation=isolation, fast_forward=forward,
                         prompt=prompt, agent_call='agent(%s, {%s})' % (json.dumps(prompt), ', '.join(options)))
        entries.append(entry)
    now.refresh(engine)
    return entries


def card(engine, task_id):
    """The brief for one card (its own file when it has one, else the skeleton). Lease-free and read-only."""
    task = engine.status()['tasks'].get(task_id)
    if task is None:
        raise EngineError('Unknown task: ' + str(task_id))
    return text_of(engine, task)[0]
