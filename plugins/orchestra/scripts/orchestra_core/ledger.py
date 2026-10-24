"""BUILD-LEDGER style rows and a reviewer package, written from engine facts. Reads run state; edits no repository file."""
import json

from . import briefs
from .engine import EngineError
from .paths import atomic

HEADER = ['| Card | Role | Commit | Evidence | Status |', '| --- | --- | --- | --- | --- |']


def _cell(text):
    return ' '.join(str(text).split()).replace('|', '/')


def _checks(task):
    review = task.get('self_review')
    if not review:
        return 'report only'
    checks = review['checks']
    red = sum(c['exit_code'] != 0 for c in checks)
    return '%d check%s, %s' % (len(checks), '' if len(checks) == 1 else 's', 'exit 0' if not red else '%d red first' % red)


def _verdict(reviews, task_id):
    covering = [r for r in reviews if task_id in r['tasks']]
    return 'no review' if not covering else 'review ' + ('BLOCKED' if covering[-1]['findings'] else 'CLEAN')


def rows(engine, ids=None):
    """The ledger table for accepted cards, in the order they were added; `ids` narrows it and each must be accepted."""
    state = engine.status()
    tasks = state['tasks']
    for task_id in ids or []:
        if task_id not in tasks:
            raise EngineError('Unknown task: ' + task_id)
        if tasks[task_id]['state'] != 'accepted':
            raise EngineError('Card %s is not accepted' % task_id)
    chosen = sorted((t for t in tasks.values() if t['state'] == 'accepted' and (not ids or t['id'] in ids)), key=lambda t: t['seq'])
    lines = list(HEADER)
    for task in chosen:
        evidence = '; '.join(p for p in (task.get('outcome'), _checks(task), _verdict(state['reviews'], task['id'])) if p)
        status = 'accepted (ruled)' if task.get('ruling') else 'accepted'
        lines.append('| %s | %s | %s | %s | %s |' % (_cell(task['id']), _cell(task['role'] + ' ' + task['mode']),
                                                     task['report_sha'][:7] if task.get('report_sha') else '-',
                                                     _cell(evidence), status))
    return '\n'.join(lines)


def package(engine, task_id):
    """Write <state>/packages/TASK/ (brief, report, self-review, diff stat of the reported commit) and return its path."""
    task = engine.status()['tasks'].get(task_id)
    if task is None:
        raise EngineError('Unknown task: ' + str(task_id))
    if not task.get('report'):
        raise EngineError('Card %s has no report to package' % task_id)
    out = engine.state_dir / 'packages' / task_id
    sha = task.get('report_sha')
    stat = (engine._git('show', '--stat', '--format=%H %s', sha).decode() if sha
            else 'No commit is named on the ARTIFACT line of this report.\n')
    files = {'brief.md': briefs.text_of(engine, task)[0], 'report.md': task['report'],
             'self-review.json': json.dumps(task.get('self_review'), indent=2) + '\n', 'diffstat.txt': stat}
    for name, text in files.items():
        atomic(out / name, text.encode())
    return out
