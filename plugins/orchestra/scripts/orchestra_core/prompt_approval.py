"""The UserPromptSubmit approval hook: the owner types "approved" in a session and the stopped run's pull requests get a
receipt (order, head, merge commands) that the merge guard then enforces. Best effort for a cooperating agent: the
payload does not prove a human typed the prompt. It writes state only through `Engine.record_owner_approval`."""
import hashlib
import json
import time
from pathlib import Path

from . import portable
from .approval import (APPROVAL_PROMPT, LIST_FIELDS, LIST_LIMIT, GhError, _default_branches, _default_name, _entries,
                       run_gh)

RETARGET = ('If a later pull request still shows a run branch as its base after its parent merged, run '
            'gh pr edit N --base %s first, then the printed command.')


def _reply(text):
    return {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': text}}


def _lock_free(state_dir, wait):
    """True when the state lock can be taken within `wait` seconds. The engine's stale check blocks on a held lock,
    and a prompt hook must not hang."""
    end = time.monotonic() + wait
    with (Path(state_dir) / 'state.lock').open('a+') as handle:
        while True:
            try:
                portable.lock(handle, exclusive=False, blocking=False)
            except OSError:
                if time.monotonic() >= end:
                    return False
                time.sleep(0.05)
                continue
            portable.unlock(handle)
            return True


def _sort(entries, live, trunk):
    """(included receipt rows, excluded rows): bottom of the stack first. A pull request joins once its live base is a
    default branch or the head of one already placed; what never joins is a cycle or has an unknown base."""
    excluded, rest = [], []
    for entry in entries:
        found = live.get(entry.get('number'))
        reason = None
        if found is None:
            reason = 'unreachable: gh did not list it'
        elif found.get('state') == 'MERGED':
            reason = 'already merged'
        elif found.get('state') != 'OPEN':
            reason = 'closed'
        elif found.get('headRefOid') != entry.get('head_sha'):
            reason = 'head moved since it was recorded; record it again, then approve again'
        elif entry.get('reviewed') is not True:
            reason = 'unreviewed head: the current head has no clean review'
        if reason:
            excluded.append(dict(number=entry['number'], reason=reason))
        else:
            rest.append((entry, found))
    heads, placed = set(), []
    while rest:
        step = [(e, f) for e, f in rest if f.get('baseRefName') in trunk or f.get('baseRefName') in heads]
        if not step:
            break
        for entry, found in step:
            placed.append((entry, found))
            heads.add(entry.get('head_ref'))
            rest.remove((entry, found))
    for entry, found in rest:
        excluded.append(dict(number=entry['number'], reason='cycle or unknown base (%s)' % found.get('baseRefName')))
    prs = [dict(order=i, number=e['number'], repo=e['repo'], url=e['url'], head_ref=e['head_ref'], head_sha=e['head_sha'],
                base_ref=f['baseRefName']) for i, (e, f) in enumerate(placed, 1)]
    return prs, sorted(excluded, key=lambda row: row['number'])


def handle_prompt(payload, state_dir, repo, gh=None, engine=None):
    """The reply dict for one UserPromptSubmit payload: `{}` for a prompt that is not the approval word or a repository
    with no run, else `additionalContext` naming what was recorded or the first condition that failed."""
    prompt = payload.get('prompt') if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not APPROVAL_PROMPT.fullmatch(prompt):
        return {}
    state_file = Path(state_dir) / 'state.json'
    try:
        state = json.loads(state_file.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return _reply('Approval not recorded: the run state is unreadable; run orchestra.py status.')
    if not isinstance(state, dict):
        return _reply('Approval not recorded: the run state is unreadable; run orchestra.py status.')
    session = payload.get('session_id')
    bound = (state.get('session') or {}).get('harness_session') if isinstance(state.get('session'), dict) else None
    from .engine import Engine, EngineError, StateBusy
    from .hooks import LOCK_WAIT
    busy = _reply('Approval not recorded: state busy, type approved again.')
    try:
        if engine is None:
            from .paths import load_policy
            engine = Engine(Path(state_dir), repo, policy=load_policy(state_dir), lock_wait=LOCK_WAIT)
        if not _lock_free(state_dir, engine.lock_wait if engine.lock_wait is not None else LOCK_WAIT):
            return busy
        stopped_here = engine.stop_stale_autonomy(session if isinstance(session, str) else '')
        state = json.loads(state_file.read_text())
        auto = state.get('autonomy') if isinstance(state.get('autonomy'), dict) else {}
        if auto.get('active') is True:
            return _reply('Approval not recorded: autonomy is active; the run is still working. Approve after it stops.')
        if stopped_here and isinstance(session, str) and session and session == bound:
            return _reply('Approval not recorded: this prompt stopped the run in the same call, from the session bound to '
                          'it. Type approved again once you have read the report.')
        receipt = state.get('approval') if isinstance(state.get('approval'), dict) else {}
        if 'report' not in auto and not (receipt.get('run') is not None and receipt.get('run') == state.get('run_id')):
            return _reply('Approval not recorded: the run never stopped, so there is nothing to approve.')
        entries = [e for e in _entries(state) if e.get('autonomous') is True and isinstance(e.get('number'), int)
                   and isinstance(e.get('repo'), str)]
        live = {}
        if entries:
            slug = sorted({e['repo'] for e in entries})[0]
            try:
                listing = json.loads((gh or run_gh)(['pr', 'list', '--state', 'all', '-R', slug, '--json', LIST_FIELDS,
                                                     '--limit', str(LIST_LIMIT)], str(repo)))
                live = {p['number']: p for p in listing if isinstance(p, dict) and type(p.get('number')) is int}
            except (GhError, ValueError, TypeError, KeyError) as exc:
                return _reply('Approval not recorded: gh could not list the pull requests (%s); fix that, then type '
                              'approved again.' % exc)
        prs, excluded = _sort(entries, live, _default_branches(state))
        evidence = dict(event='UserPromptSubmit', session_id=session if isinstance(session, str) else None,
                        prompt_id=payload.get('prompt_id') if isinstance(payload.get('prompt_id'), str) else None,
                        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
        engine.record_owner_approval(prs, excluded, evidence)
    except StateBusy:
        return busy
    except (EngineError, OSError, ValueError, KeyError, TypeError) as exc:
        return _reply('Approval not recorded: %s' % exc)
    lines = ['Approval recorded for run %s. Merge in this order, one command at a time:' % state.get('run_id')]
    lines += ['  %d. gh pr merge %d --merge --delete-branch --match-head-commit %s' % (p['order'], p['number'], p['head_sha'])
              for p in prs] or ['  (no pull request to merge)']
    if excluded:
        lines.append('Not approved: ' + '; '.join('#%d %s' % (e['number'], e['reason']) for e in excluded) + '.')
    lines.append(RETARGET % _default_name(state, dict(base_ref=None)))
    return _reply('\n'.join(lines))
