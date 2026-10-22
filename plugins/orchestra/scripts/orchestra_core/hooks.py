"""Native hook adapter. Shell inspection and caller identity are best effort.

Reference wire contracts: https://learn.chatgpt.com/docs/hooks and
https://code.claude.com/docs/en/hooks (checked 2026-09-30).
"""
import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import sys
import subprocess
import time

from . import portable
from .approval import APPROVAL_PROMPT, MERGE_SEGMENT, merge_decision, raw_unattended
from .guards import RULES, Decision, _command_words, _pipelines, _segments, classify_command, guard_digest, runs_test_suite

_PROTECTED = RULES['protected']
_MARKER = RULES['marker']
_MOD_TOOLS = {'Bash', 'Edit', 'Write', 'MultiEdit'}  # The mod guards only these; any other tool needs Python.
_EDIT_TOOLS = set(RULES['tools']['edit'])
_SCHEDULERS = set(RULES['tools']['scheduler'])
_APPROVAL_TEXT_TOOLS = _SCHEDULERS | {'SendMessage'}  # a call to one of these must never carry the approval word alone
_SHELL_TOOLS = set(RULES['tools']['shell'])
_REBIND_SOURCES = ('clear', 'resume', 'fork')
STOP_LOCK_BUDGET = 8.0  # SPEC 5.16 item 4: seconds from hook start that a busy-state Stop waits for the lock
LOCK_WAIT = 2.0  # SPEC 5.16 item 3: seconds a hook read waits for the state lock
MISSING_CWD = 'Session directory no longer exists: cd to an existing directory, then retry'
BUSY = 'Orchestra state is busy; retry'
AGENT_GUARD = 'Orchestra run active: use an orchestra:* agent (investigator-code for search, builder for edits)'
_REVIEWER_TYPES = ('orchestra:code-reviewer', 'orchestra:critic')
SUBAGENT_GUARD = ('Orchestra run active: this agent is not an orchestra:* agent; stop and report. '
                  'Start Agent and Workflow workers with an orchestra:<role> type')


CONTEXT = (
    'Orchestra is enabled. You are the main coordinator. Read the orchestra skill '
    'before substantial work. Own assignments, bounded file reservations, exact '
    'artifact evidence, independent review and integration. Workers never delegate '
    'or change coordinator state. Session start injects context only; do not repair '
    'the repository, resume prior runs or arm autonomy without an explicit request. '
    'Release needs configured authorization and current evidence. Native hook '
    'identity and shell inspection are best effort, not hostile-worker isolation.'
)
WORKER_CONTEXT = 'Orchestra worker: follow the assigned brief, own only assigned files, return evidence, and never delegate or change coordinator state.'


@dataclass(frozen=True)
class HookResult:
    output: dict
    exit_code: int = 0


def _guarded(reason):
    """Name the source, so the model reads a policy decision, not a tool failure."""
    return reason if reason.startswith('Orchestra') else 'Orchestra guard: ' + reason


def _deny(reason, malformed=False):
    reason = _guarded(reason)
    return HookResult({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason}}, 2 if malformed else 0)


MARKER_KEEP_SECONDS = 24 * 3600  # a live session rewrites its marker every few seconds; older ones belong to ended sessions


def _prune_markers(current=None, now=None):
    """Delete the mod heartbeat markers of ended sessions (untouched for a day), so they do not pile up. Only
    `<session id>.json` files are touched, never the current session's; any error is ignored."""
    try:
        directory = _marker_dir()
        now = time.time() if now is None else now
        for path in directory.glob('*.json'):
            if (path.stem != current and re.fullmatch(_MARKER['session_id_pattern'], path.stem)
                    and path.is_file() and not path.is_symlink() and now - path.stat().st_mtime > MARKER_KEEP_SECONDS):
                path.unlink()
    except OSError:
        pass


def _marker_dir():
    from .paths import state_home
    return (state_home() / 'orchestra' / 'mods').resolve()


def _protected(path, cwd, state_dir):
    resolved = (Path(cwd) / path).resolve()
    if state_dir:
        state = Path(state_dir).expanduser().resolve()
        if resolved == state or state in resolved.parents:
            # Coordinator-authored notes at the state root stay writable (A8).
            return not (resolved.parent == state and resolved.name in _PROTECTED['state_root_exceptions'])
    marker = _marker_dir()
    if resolved == marker or marker in resolved.parents:
        return True
    fold = str.lower if portable.IS_WINDOWS else str  # Windows paths ignore case: `.CLAUDE\\Settings.json` is the same file
    parts = tuple(fold(part) for part in resolved.parts)
    if fold(_PROTECTED['component']) in parts:
        return True
    harness_dirs = {fold(d) for d in _PROTECTED['harness_dirs']}
    files = {fold(f) for f in _PROTECTED['files']}
    agents_prefixes = tuple(fold(x) for x in _PROTECTED['agents_prefixes'])
    # Every harness directory in the path counts, not only the first (B-F4).
    for i, part in enumerate(parts):
        if part in harness_dirs:
            tail = parts[i + 1:]
            if tail and (tail[0] in files or (tail[0] == 'agents' and any(x.startswith(agents_prefixes) for x in tail[1:]))):
                return True
    return False


def _is_ledger(path, cwd, state_dir):
    """True when `path` is the autonomy ledger of the run in `state_dir`."""
    try:
        return (Path(cwd) / path).resolve() == (Path(state_dir).expanduser() / 'autonomy.md').resolve()
    except (OSError, RuntimeError, ValueError):
        return False


_NEW_RUN = re.compile(r'\borchestra\.py\b[^|;&\n]*\bstart\b[^|;&\n]*--new-run\b')


def _runs_orchestra(command, pattern, hit):
    """True when a command runs `orchestra.py` with arguments `hit` accepts. Line continuations are removed and each
    segment is split into words, so the phrase inside a quoted argument (`echo '...'`, `rg ...`) does not count; a
    segment run through a shell (`sh -c`, `eval`) is searched with `pattern` as text, since the shell will run it."""
    joined = re.sub(r'\\\r?\n', '', command)
    for segment in re.split(r'[;&|\n]+', joined):
        try:
            words = shlex.split(segment)
        except ValueError:
            return bool(pattern.search(segment))  # Unbalanced quoting: read it as text
        if not words:
            continue
        if '-c' in words or Path(words[0]).name in {'sh', 'bash', 'zsh', 'dash', 'ksh', 'eval', 'source', '.'}:
            if pattern.search(' '.join(words)):
                return True
        for i, word in enumerate(words):
            if Path(word).name == 'orchestra.py' and hit(words[i + 1:]):
                return True
    return False


def _switches_autonomy(command, verbs=('arm', 'disarm')):
    """True when a command runs `orchestra.py autonomy` with one of `verbs`."""
    pattern = re.compile(r'\borchestra\.py\b[^|;&\n]*\bautonomy\s+(?:%s)\b' % '|'.join(verbs))
    return _runs_orchestra(command, pattern, lambda rest: any(a == 'autonomy' and b in verbs for a, b in zip(rest, rest[1:])))


def _starts_new_run(command):
    """True when a command runs `orchestra.py start --new-run`, which archives the state and its kept report."""
    return _runs_orchestra(command, _NEW_RUN, lambda rest: 'start' in rest and '--new-run' in rest[rest.index('start') + 1:])


# A release or repository delete on the provider (`gh release delete`, `gh repo delete`): the unattended lock denies it
# like a release. Local deletes (`rm`, `git tag -d`) keep their ordinary path after the owner's disarm.
_PROVIDER_DELETE = re.compile(r'\bgh\b[^|;&\n]*\b(?:%s)\b' % '|'.join(r'%s\s+%s' % tuple(pair) for pair in RULES['boundary']['gh']))


LEDGER_LOCKED = ('The autonomy ledger and the autonomy switch belong to the owner while autonomy is armed: '
                 'the owner changes them with /orchestra-autonomy off, then edits and arms again.')


UNATTENDED_LOCKED = ('The last autonomous run stopped and its work waits for the owner: releases, merges, scheduler tools and '
                     'settings edits stay denied. Type `approved` in the owner\'s session, or run '
                     '`orchestra.py autonomy disarm` in a terminal.')


def _ask(reason):
    return HookResult({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                        'permissionDecision': 'ask',
                        'permissionDecisionReason': reason}})


def _patch_paths(command):
    if not isinstance(command, str) or not command.startswith('*** Begin Patch\n') or not command.rstrip().endswith('*** End Patch'):
        raise ValueError('Malformed patch payload')
    paths = []
    for line in command.splitlines():
        match = re.fullmatch(r'\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)', line)
        if match:
            paths.append(match.group(1))
    if not paths:
        raise ValueError('Patch has no file operations')
    return paths


GUARD_MODES = ('normal', 'protect')
RELEASE_WORKFLOWS = ['release*', 'publish*', 'deploy*']  # the policy key `release_workflows` replaces these


def _guard_mode(state_dir):
    """The mode `policy.json` selects, read on every call with or without `state.json`: no file or no state directory
    is `normal`; `protect` and `normal` are themselves; a file that cannot be read or checked, or any other value, is
    `protect` (fail closed)."""
    if state_dir is None:
        return 'normal'
    try:
        from .paths import load_policy
        policy = load_policy(state_dir)
    except Exception:
        return 'protect'
    if policy is None:
        return 'normal'
    mode = policy.get('guard_mode', 'normal')
    return mode if isinstance(mode, str) and mode in GUARD_MODES else 'protect'


def handle_event(event, payload, *, harness='claude', state_dir=None, engine=None, armed=False, autonomy=False,
                 busy=False, missing_cwd=False, started=None, mode='protect', unattended=False):
    """`mode` is the guard mode (`normal` or `protect`; the default keeps every direct caller on the strict verdicts).
    `unattended` marks a stopped run whose report is kept without an owner receipt: it locks like an active run.
    A warning collected while deciding rides on an otherwise empty answer as `additionalContext`."""
    notes = []
    result = _decide(event, payload, notes, 'normal' if mode == 'normal' else 'protect', harness=harness, state_dir=state_dir,
                     engine=engine, armed=armed, autonomy=autonomy, busy=busy, missing_cwd=missing_cwd, started=started,
                     unattended=unattended is True)
    if notes and event == 'PreToolUse' and not result.output:
        return HookResult({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': ' '.join(notes)}})
    return result


def _decide(event, payload, notes, mode, *, harness, state_dir, engine, armed, autonomy, busy, missing_cwd, started,
            unattended=False):
    """Decide output; optional engine adapter owns locked state operations.

    `armed` marks a run whose state could not be loaded: release classes deny (fail closed).
    `autonomy` marks such a state whose raw autonomy flag is true or unreadable (O29): the
    autonomy-active column applies to every class. A loaded engine implies an armed run; neither means unarmed.
    `unattended` marks a stopped run with a kept report and no owner receipt: the effective mode is protect, and the
    autonomy column applies to release classes, a merge on the default branch, the autonomy switch, scheduler tools and
    settings edits.
    `busy` marks a state lock held past the read wait, `missing_cwd` a payload cwd that no longer exists: the
    delegated classes (release, release-multi, boundary) deny; the other classes keep their ordinary path.
    """
    if harness != 'claude':
        raise ValueError('Unsupported harness')
    if not isinstance(payload, dict):
        return _deny('Malformed hook payload', True) if event == 'PreToolUse' else HookResult({})
    if event == 'SessionStart':
        # Native agent_type, where supplied, is a routing hint, never authentication.
        agent_type = payload.get('agent_type')
        worker = (bool(agent_type) and agent_type not in ('orchestra:orchestrator', 'orchestra_orchestrator', 'orchestra-orchestrator')) or os.environ.get('ORCHESTRA_ROLE', 'main') != 'main'
        skill = Path(__file__).resolve().parents[2] / 'skills/orchestra/SKILL.md'
        context = WORKER_CONTEXT if worker else CONTEXT + ' Skill: ' + str(skill)
        session_id = payload.get('session_id')
        if not worker and harness == 'claude' and engine is not None and payload.get('source') in _REBIND_SOURCES \
                and isinstance(session_id, str) and session_id:
            try:
                engine.apply_harness_rebind(session_id)  # B-F5: the one SessionStart write
            except Exception:
                pass  # An unloadable state or changed contract never blocks the context
        if not worker and engine is not None:
            context += _report_context(engine)
            if _other_session(engine, session_id) and _run_active(engine):
                context += (' An Orchestra run is active in this repository but bound to another session, so this session is not '
                            'its coordinator and may use any agent type. If that session is gone, the owner recovers it with '
                            '`orchestra.py --actor main --lease L interrupt`, L read from session.lease in '
                            + str(engine.state_path) + '.')
        if not worker and isinstance(session_id, str) and session_id:
            context += ' Harness session id: ' + session_id + '. Pass --harness-session ' + session_id + ' to orchestra.py start.'
        return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': context}})
    if event == 'SubagentStart':
        # A11: only Orchestra agents get worker context.
        agent_type = payload.get('agent_type')
        if isinstance(agent_type, str) and agent_type.startswith('orchestra:'):
            return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': WORKER_CONTEXT}})
        if _run_active(engine):  # SubagentStart cannot block; the PreToolUse deny below enforces
            return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': SUBAGENT_GUARD}})
        return HookResult({})
    if event == 'SessionEnd':
        session_id = payload.get('session_id')
        if engine is None or not isinstance(session_id, str) or not session_id:
            return HookResult({})
        try:
            if payload.get('reason') in ('clear', 'resume'):
                engine.mark_harness_rebind(session_id)  # The process continues under a new id (O6)
            else:
                engine.end_harness_session(session_id)
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            if not _raw_session_active(engine.state_path):
                return HookResult({})  # O35: an ended run has nothing to record
            return HookResult({'systemMessage': 'Orchestra session end could not be recorded: ' + str(exc)})
        return HookResult({})
    if event == 'Interrupt':
        if engine is not None:
            try:
                engine.interrupt_active()
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                return HookResult({'systemMessage': 'Orchestra interruption could not be recorded: ' + str(exc)})
        return HookResult({})
    if event == 'Stop':
        if engine is None:
            return HookResult({})
        if busy:
            if not (_raw_autonomy_active(engine.state_path) and _raw_session_active(engine.state_path)):
                return HookResult({})  # Unarmed and busy: nothing to stop, nothing to write
            if not _wait_for_lock(engine.state_dir / 'state.lock', started):
                from .engine import write_busy_brief  # Lazy: tests replace the engine module
                try:
                    write_busy_brief(engine.state_dir, datetime.now(timezone.utc).isoformat(timespec='seconds'))
                except OSError:
                    pass
                return HookResult({})  # Allow the stop; autonomy.active stays true
        if _other_session(engine, payload.get('session_id')):
            return HookResult({})  # O37: a Stop from another harness session neither continues nor spends a pass
        try:
            reason = engine.hook_stop()
            return HookResult({'decision': 'block', 'reason': reason}) if isinstance(reason, str) and reason else HookResult({})
        except (OSError, ValueError, KeyError, RuntimeError, AttributeError):
            return HookResult({})  # Corrupt/unarmed state never creates continuation.
    if event != 'PreToolUse':
        return HookResult({})
    name, data = payload.get('tool_name'), payload.get('tool_input')
    if not isinstance(name, str) or not name or not isinstance(data, dict):
        return _deny('Malformed tool payload', True)
    if name in _APPROVAL_TEXT_TOOLS and _carries_approval_text(data):
        return _deny('A message or scheduled prompt that is only the approval word could record the owner\'s approval; '
                     'the owner types it in their own session')
    role = os.environ.get('ORCHESTRA_ROLE', 'main')  # Advisory, caller-controlled marker.
    if harness == 'claude' and isinstance(payload.get('agent_id'), str) and payload['agent_id']:
        role = 'subagent'  # Claude Code sets agent_id only for calls made inside a subagent.
    auto_on = (engine is not None and _autonomy_active(engine)) or (engine is None and armed and autonomy)
    locked = auto_on or unattended
    if locked:
        mode = 'protect'  # Only the autonomous run is careful: it never gets the normal relaxations, nor does its morning after
    unloaded_run = engine is None and armed and (state_dir is None or _raw_session_active(Path(state_dir) / 'state.json'))
    run_on = _run_active(engine) or unloaded_run
    if role != 'main' and name in {'Agent', 'Task', 'spawn_agent', 'create_thread', 'send_message_to_thread'}:
        # Row 31: normal denies only inside a run or for an Orchestra agent; protect always.
        if mode == 'protect' or run_on or str(payload.get('agent_type')).startswith('orchestra:'):
            return _deny('Workers do not delegate')
    bystander = _other_session(engine, payload.get('session_id'))  # A session the run is not bound to does not coordinate it
    if role == 'subagent' and _foreign_subagent(payload) and not bystander and run_on:
        if mode == 'protect':
            return _deny(SUBAGENT_GUARD)  # item 9: a Workflow agent never passes the Agent/Task check above it
        notes.append(SUBAGENT_GUARD)  # Row 32: normal warns
    if name in {'Agent', 'Task'} and not bystander and run_on:  # item 9, failing closed when busy or unloadable
        kind = data.get('subagent_type')
        if not (isinstance(kind, str) and kind.startswith('orchestra:')):
            if mode == 'protect':
                return _deny(AGENT_GUARD)
            notes.append(AGENT_GUARD)  # Row 33: normal warns
    if locked and name in _SCHEDULERS:
        return _deny(('Autonomy is active: ' if auto_on else UNATTENDED_LOCKED + ' ') + name + ' could schedule the run past its limits')
    if 'cwd' in payload:
        cwd = payload['cwd']
        if not isinstance(cwd, str):
            return _deny('Malformed cwd', True)
        if not cwd:
            cwd, missing_cwd = None, True  # An empty cwd is a missing one, as main() reads it
    else:
        try:
            cwd = os.getcwd()
        except OSError:  # The process cwd was removed: a missing cwd, never a crash that lets the call run
            cwd, missing_cwd = None, True
    if name in _EDIT_TOOLS:
        try:
            if name == 'apply_patch':
                paths = _patch_paths(data.get('command', data.get('patch')))
            else:
                path = data.get('file_path', data.get('path'))
                if not isinstance(path, str) or not path:
                    raise ValueError('Missing file path')
                paths = [path]
            if cwd is None and not all(os.path.isabs(path) for path in paths):
                return _deny(MISSING_CWD)
            if any(_protected(path, cwd or '/', state_dir) for path in paths):
                return _deny('Use the structured coordinator API for state; protect installed runtime configuration')
            if auto_on and state_dir and any(_is_ledger(path, cwd or '/', state_dir) for path in paths):
                return _deny(LEDGER_LOCKED)
            if locked and any(_autonomy_file(path, cwd or '/') for path in paths):
                return _deny(('Autonomy is active: ' if auto_on else UNATTENDED_LOCKED + ' ')
                             + 'the settings files belong to the owner')
        except (ValueError, OSError, RuntimeError) as exc:  # RuntimeError: a symlink loop on Python 3.11
            return _deny(str(exc), True)
    if name not in _SHELL_TOOLS:
        return HookResult({})
    command = data.get('command', data.get('cmd'))
    if not isinstance(command, str):
        return _deny('Missing shell command', True)
    decision = classify_command(command)
    klass = decision.klass
    if klass == 'deny':
        if mode != 'normal' or not decision.soften:
            return _deny(decision.reason, decision.category == 'malformed')
        # Rows 4, 10, 11, 12, 14, 15: the classifier kept the protect verdict; normal relaxes it for the softened
        # items only. The rest of the command is decided as a command of its own (R4).
        split = _soft_remainder(command)
        if split is None:
            return _deny(decision.reason)
        remainder, pushed = split
        refused = _soft_push_refusal(command, cwd, engine) if pushed or decision.category == 'release' else None
        if refused:
            return _deny(refused)
        if decision.soften == 'warn':
            notes.append(_guarded(decision.reason))
        decision = classify_command(remainder) if remainder else Decision()
        klass = decision.klass
        if klass == 'deny':
            return _deny(decision.reason, decision.category == 'malformed')
    if klass == 'release' and decision.workflow is not None and not locked and cwd is not None \
            and _workflow_is_plain(_toplevel(cwd), decision.workflow, _release_globs(engine, state_dir)):
        klass, decision = 'allow', Decision()  # Row N2: a workflow that is neither a release name nor missing
    if klass in {'release', 'release-multi', 'boundary'}:
        if missing_cwd:
            return _deny(MISSING_CWD)
        merged = _merge_gate(command, cwd, state_dir, engine)
        if merged is not None:
            if merged[0] == 'allow':
                return HookResult({})  # final in every mode: the receipt path never asks and the plane never reaches it
            return _deny(('Autonomy is active: ' if auto_on else UNATTENDED_LOCKED + ' ' if unattended else '') + merged[1])
        if busy and mode == 'protect':
            return _deny(BUSY)  # Row 42: normal needs no engine state; autonomy forces protect
    if role == 'subagent' and str(payload.get('agent_type')).startswith(_REVIEWER_TYPES) and runs_test_suite(command):
        gates = _gate_ids(engine)
        if gates:
            reason = 'Cite gate receipt ' + ', '.join(gates) + '; reviewers do not rerun suites'
            if mode == 'protect':
                return _deny(reason)
            notes.append(_guarded(reason))  # Row 43
    active = auto_on
    if unattended and not active:
        if klass in {'release', 'release-multi'} or _starts_new_run(command) or _switches_autonomy(command, ('disarm',)) \
                or (decision.boundary == 'merge' and _on_default_branch(cwd, engine)) \
                or (decision.boundary == 'delete' and _PROVIDER_DELETE.search(re.sub(r'\\\r?\n', '', command))):
            return _deny(UNATTENDED_LOCKED + ' Denied: ' + (decision.reason or command.strip()[:80]))
    hint = _PARK_HINT if engine is not None else ('the run state is unreadable (%s); the owner starts over with '
                                                  '`orchestra.py start --new-run ...`, which keeps the old file under history/.'
                                                  % (Path(state_dir) / 'state.json' if state_dir else 'state.json'))
    if active and (_switches_autonomy(command) or _starts_new_run(command)):
        return _deny(LEDGER_LOCKED)  # An agent never re-arms or disarms itself: that would rewrite its own boundaries
    if decision.category == 'merged-delete':
        # SPEC 5.14 item 4: with or without an engine and autonomy. Only a provably merged branch is deleted; under
        # autonomy a branch the run made also goes when another remote branch holds its tip (section 3.3).
        denied = _merged_delete_check(decision, cwd, engine, plane=active)
        if denied:
            return HookResult(denied)
        if active:
            return HookResult({})  # Cleanup of merged work is allowed under autonomy
    if active and decision.boundary == 'delete':
        cleanup = _autonomy_cleanup(command, decision, cwd, engine)
        if cleanup is not None:
            return cleanup
        if engine is not None and _rm_in_worktrees(command, cwd):
            return HookResult({})  # Section 3.4: the run may delete files inside a linked worktree
    if active:
        # Checked before any permit: a permit never opens a boundary while autonomy is active (12.4).
        if klass == 'release' and decision.category == 'gitpush':
            refused = _pull_request_push(command, cwd, engine)
            if refused is None:
                return HookResult({})  # A feature branch for a pull request; the owner merges it after the run
            if not _preauthorized(engine, decision):
                return _deny('Autonomy is active: ' + refused + ' ' + hint)
        if klass in {'release', 'release-multi'} and not (klass == 'release' and _preauthorized(engine, decision)):
            return _deny('Autonomy is active: merges and releases wait for the owner. ' + hint)
        if decision.boundary == 'delete':
            return _deny('Approval boundary under autonomy: ' + hint)
        if decision.boundary == 'config':
            return _deny('Autonomy is active: ' + decision.reason + '. ' + hint)
        if decision.category == 'boundary' and decision.boundary == 'merge' and _on_default_branch(cwd, engine):
            return _deny('Approval boundary under autonomy: no merge on the default branch. ' + hint)
    if klass in {'release', 'release-multi'} and (engine is not None or armed) and mode == 'protect':
        # Normal never asks (rows 24, 27, 46, 50, 51). Protect: a current permit lets the release run; otherwise the
        # user is present: ask, unless autonomy is active.
        problem = decision.reason
        if klass == 'release' and engine is not None and decision.remote and decision.target:
            try:
                if engine.check_release(decision.remote, decision.target, argv=list(decision.argv)):
                    return HookResult({})
                problem = 'No current release permit'
            except (OSError, ValueError, KeyError, RuntimeError, AttributeError) as exc:
                problem = str(exc)
        if active:
            return _deny('Release denied: ' + problem)
        return _ask('Orchestra run active: approve this release action? No current release permit covers it: ' + problem)
    return HookResult({})  # allow, boundary (autonomy off) and unarmed release classes


def _carries_approval_text(value, depth=0):
    """True when any string inside a tool input (a nested value, or a JSON string holding one) is only the approval word."""
    if isinstance(value, str):
        if APPROVAL_PROMPT.fullmatch(value):
            return True
        if depth < 3 and value.lstrip()[:1] in ('{', '['):
            try:
                return _carries_approval_text(json.loads(value), depth + 1)
            except ValueError:
                return False
        return False
    if depth > 6:
        return False
    if isinstance(value, dict):
        return any(_carries_approval_text(v, depth + 1) for v in value.values())
    if isinstance(value, list):
        return any(_carries_approval_text(v, depth + 1) for v in value)
    return False


def _merge_gate(command, cwd, state_dir, engine):
    """The merge guard (approval.py) for a merge-looking command: None when it does not gate, else ('allow', '') or
    ('deny', reason). It reads raw state and asks gh; it writes nothing."""
    directory = state_dir if state_dir is not None else getattr(engine, 'state_dir', None)
    if not isinstance(directory, (str, os.PathLike)) or cwd is None or not MERGE_SEGMENT.search(command):
        return None
    return merge_decision(command, cwd, directory, _toplevel(cwd))


def _toplevel(cwd):
    code, out = _git_out(cwd, 'rev-parse', '--show-toplevel')
    return Path(out if code == 0 and out else cwd)


def _release_globs(engine, state_dir):
    """The `release_workflows` globs: the loaded policy, else policy.json, else the defaults; a malformed value is the default."""
    found = None
    try:
        policy = engine.policy if engine is not None else None
        if not isinstance(policy, dict) and state_dir is not None:
            from .paths import load_policy
            policy = load_policy(state_dir)
        found = policy.get('release_workflows') if isinstance(policy, dict) else None
    except Exception:
        pass
    if isinstance(found, list) and found and all(isinstance(g, str) and g for g in found):
        return found
    return RELEASE_WORKFLOWS


def _workflow_is_plain(repo, name, globs):
    """True when `gh workflow run NAME` names a local workflow file that no release glob matches. A name with a path,
    a glob or no text is never plain; a workflow not found locally counts as a release."""
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9._-]*', name) or '..' in name:
        return False
    if any(fnmatch.fnmatchcase(name.lower(), g.lower()) for g in (globs or RELEASE_WORKFLOWS)):
        return False
    folder = Path(repo) / '.github' / 'workflows'
    return any((folder / (name + suffix)).is_file() for suffix in ('', '.yml', '.yaml'))


def _soft_push_refusal(command, cwd, engine):
    """Q1: normal warns on a softened push, but the hook still denies one that deletes a tag, the default branch or a
    protected branch, and any one whose default branch it cannot resolve. A reason, or None."""
    if cwd is None:
        return 'A multi-ref push needs a working directory'
    if re.search(r'\$\(|`|<\(|>\(', command):
        return 'A multi-ref push inside a substitution cannot be checked; run it as a command of its own'
    pushes = []
    try:
        for segment in _segments(command):
            words = _command_words(segment)
            if words and PurePosixPath(words[0]).name == 'git':
                pushes.append(words)
            elif words and PurePosixPath(words[0]).name in {'sh', 'bash', 'zsh', 'dash', 'ksh', 'eval'}:
                return 'A multi-ref push inside a shell string cannot be checked; run it as a command of its own'
    except ValueError:
        return 'The push could not be read'
    pushes = [w for w in pushes if 'push' in w]
    if not pushes:
        return None
    protected = {b.lower() for b in RULES['git']['autonomy_protected_branches']}
    value_options = set(RULES['git']['push_value_options'])
    for words in pushes:
        if len(words) < 2 or words[1] != 'push':
            return 'A push with a Git global option cannot be checked; push by hand'
        args, positional, delete, skip = words[2:], [], False, False
        for word in args:
            if skip:
                skip = False
            elif word in value_options:
                skip = True
            elif word == '--delete' or (re.fullmatch(r'-[A-Za-z]+', word) and 'd' in word):
                delete = True
            elif not word.startswith('-'):
                positional.append(word)
        if not positional:
            return 'A multi-ref push needs an explicit remote'
        remote, refspecs = positional[0], positional[1:]
        known = set(protected)
        code, head = _git_out(cwd, 'symbolic-ref', '--short', 'refs/remotes/%s/HEAD' % remote)
        if code == 0 and head:
            known.add((head[len(remote) + 1:] if head.startswith(remote + '/') else head).lower())
        known |= {v.lower() for v in _armed_defaults(engine).values()}
        if code != 0 and not _armed_defaults(engine):
            return 'The default branch of %s cannot be resolved; push by hand' % remote
        targets = refspecs if delete else [r.partition(':')[2] for r in refspecs if r.startswith(':')]
        for target in targets:
            target = target.lstrip(':')
            if any(c in target for c in '*?[') or not target:
                return 'A multi-ref push may not delete a pattern'
            if target.startswith(('refs/tags/', 'tags/')) or _git_out(cwd, 'show-ref', '--verify', '--quiet', 'refs/tags/' + target)[0] == 0:
                return 'A push may not delete a tag; ask the owner'
            branch = target[len('refs/heads/'):] if target.startswith('refs/heads/') else target
            branch = branch[len('heads/'):] if branch.startswith('heads/') else branch
            if branch.lower() in known:
                return 'A push may not delete the default or a protected branch (%s); ask the owner' % branch
    return None


def _soft_remainder(command):
    """R4: (the command without its softened segments, True when one of them is a push), or None when the command
    cannot be split safely: a substitution, a heredoc, a shell string, a softened segment inside a pipe or an
    unreadable segment."""
    if re.search(r'\$\(|`|<\(|>\(|<<', command):
        return None
    kept, pushed = [], False
    try:
        for pipeline in _pipelines(command):
            soft = []
            for segment in pipeline:
                words = _command_words(segment)
                if words and PurePosixPath(words[0]).name in {'sh', 'bash', 'zsh', 'dash', 'ksh', 'eval'}:
                    return None
                found = classify_command(segment)
                soft.append(found.klass == 'deny' and bool(found.soften))
                pushed = pushed or (soft[-1] and found.category == 'release')
            if any(soft) and len(pipeline) > 1:
                return None
            if not any(soft):
                kept.append(' | '.join(pipeline))
    except ValueError:
        return None
    return '\n'.join(kept), pushed


def _soften_call(payload):
    """A shell call whose classifier deny carries `soften`: normal mode relaxes it, so the mod cannot decide it and the
    call always reaches this hook. A command that cannot be classified reaches it too."""
    data = payload.get('tool_input')
    command = data.get('command', data.get('cmd')) if isinstance(data, dict) else None
    if not isinstance(payload.get('tool_name'), str) or payload['tool_name'] not in _SHELL_TOOLS or not isinstance(command, str):
        return False
    try:
        return bool(classify_command(command).soften)
    except Exception:
        return True


_BRANCH = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._/-]*')
_NOT_A_BRANCH = ('refs/', 'heads/', 'tags/', 'remotes/')


def _pull_request_push(command, cwd, engine):
    """Autonomy may push one feature branch for a pull request. Only the exact shape
    `git push [-u|--set-upstream] REMOTE REFSPEC` qualifies: no environment prefix, wrapper, Git option or other push
    option, a configured remote by name with no push mapping, and a refspec whose destination is one branch that is
    not the remote's default branch, `main` or `master` (compared ignoring case). REFSPEC is BRANCH, HEAD or @
    (the current branch), or SRC:DST where DST names the same branch as SRC (BRANCH or refs/heads/BRANCH). None allows; otherwise the reason.
    Any doubt refuses, including a remote whose default branch the remote itself did not confirm at arm. The ledger must allow pull
    request pushes (the 2.6 Push line), and the configured release branch is never a pull request push."""
    shape = 'A pull request push is exactly `git push -u <remote> <branch>`, run as a command of its own.'
    if cwd is None or not re.fullmatch(r'[A-Za-z0-9_./:@+-]+( [A-Za-z0-9_./:@+-]+)*', command.strip()):
        if not command.isascii() and command.lstrip().startswith('git push'):
            return ('A pull request push needs an ASCII branch name; this one has other characters. '
                    'Rename the branch (`git branch -m`) or push it by hand.')
        return shape
    words = command.split()
    rest = [w for w in words[2:] if w not in ('-u', '--set-upstream')]
    if words[:2] != ['git', 'push'] or len(rest) != 2 or any(w.startswith(('-', '+')) for w in rest):
        return shape
    remote, refspec = rest
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9._-]*', remote) or not _git_out(cwd, 'config', '--get', 'remote.%s.url' % remote)[1]:
        return 'Push to a configured remote by name, not a URL.'
    if _git_out(cwd, 'config', '--get-all', 'remote.%s.push' % remote)[1] or _git_out(cwd, 'config', '--get-all', 'remote.%s.pushurl' % remote)[1]:
        return 'Remote %s has a push mapping or push URL; push it by hand.' % remote
    source, _, target = refspec.partition(':')
    if source in ('HEAD', '@'):
        code, current = _git_out(cwd, 'symbolic-ref', '--short', '-q', 'HEAD')
        if code != 0 or not current:
            return 'HEAD is detached; push a named branch.'
        source = current
    elif _git_out(cwd, 'show-ref', '--verify', '--quiet', 'refs/heads/' + source)[0] != 0:
        return 'Push a local branch; %s is not one.' % source
    target = target or source
    target = target[len('refs/heads/'):] if target.startswith('refs/heads/') else target
    if not _BRANCH.fullmatch(target) or target.startswith(_NOT_A_BRANCH) or '..' in target or target.endswith(('/', '.lock')):
        return 'The destination must be one branch name.'
    if target != source:
        return ('A pull request push keeps the branch name: push %s to %s, not %s. '
                'Rename the local branch first if the name is wrong.' % (source, source, target))
    try:
        auto = engine.status()['autonomy']
        allowed = auto.get('pull_requests') is True
        default = (auto.get('remote_defaults') or {}).get(remote)  # what the remote answered at arm, not a local cache
        armed_url = (auto.get('remote_push_urls') or {}).get(remote)
        release = engine.policy.get('release') or {}
    except Exception:
        return 'The run state cannot be read; push by hand.'
    if not allowed:
        return 'This ledger does not allow pull request pushes; the owner re-arms with the current Push line.'
    if not isinstance(default, str) or not default:
        return ('The default branch of %s was not confirmed when autonomy was armed; arm again once the remote answers.'
                % remote)
    now_url = _git_out(cwd, 'remote', 'get-url', '--push', '--all', remote)[1]
    if '\n' in now_url:
        return 'Remote %s has more than one push URL; push it by hand.' % remote
    from .paths import push_url_digest
    if not isinstance(armed_url, str) or not armed_url or push_url_digest(now_url) != armed_url:
        return ('Where %s pushes to differs from what it was when autonomy was armed (or was not recorded); '
                'the owner checks the remote and arms again.' % remote)
    if target.casefold() in {default.casefold(), *(x.casefold() for x in RULES['git']['autonomy_protected_branches'])}:
        return 'Never push the default or a release branch (main, master, production, gh-pages ...); push a feature branch and open a pull request.'
    if release.get('remote') == remote and str(release.get('target', '')).casefold() == target.casefold():
        return 'That branch is the configured release target; a release needs the pre-authorized permit.'
    return None


_PARK_HINT = 'park this card with `orchestra.py park TASK --reason ...` and continue with other cards.'


def _wait_for_lock(lock_path, started):
    """Poll for the exclusive state lock until STOP_LOCK_BUDGET seconds after `started`; True when it freed (and is released)."""
    end = (started if started is not None else time.monotonic()) + STOP_LOCK_BUDGET
    with open(lock_path, 'a+') as lock:
        while True:
            try:
                portable.lock(lock, exclusive=True, blocking=False)
                return True  # Closing the file releases it
            except OSError:
                if time.monotonic() >= end:
                    return False
                time.sleep(0.05)


def _autonomy_active(engine):
    try:
        return engine.autonomy_active() is True  # Strict: an opaque adapter never reads as active.
    except Exception:
        return True  # O29: an error while reading autonomy status counts as active.


def _foreign_subagent(payload):
    """A call made inside a subagent whose type is not orchestra:* (a Workflow agent without agentType is
    'workflow-subagent'). agent_type is a routing hint, never authentication."""
    agent_type = payload.get('agent_type')
    return bool(payload.get('agent_id')) and not (isinstance(agent_type, str) and agent_type.startswith('orchestra:'))


def _reviewer_call(payload):
    """A call made inside a reviewer or critic: the mod does not know the test-suite rule, so Python always guards it."""
    return bool(payload.get('agent_id')) and str(payload.get('agent_type')).startswith(_REVIEWER_TYPES)


def _run_active(engine):
    """Item 9: a loaded engine whose session is active. An engine that cannot say counts as active only when the
    raw state shows (or cannot show otherwise) an active session; an inactive raw session allows."""
    if engine is None:
        return False
    try:
        session = engine.status()['session']
        return bool(session) and session.get('active') is True
    except Exception:
        try:
            return _raw_session_active(engine.state_path)
        except Exception:
            return True


def _gate_ids(engine):
    """Item 10: ids of the passed gate receipts for the current artifact; [] with no engine, no method or any error."""
    try:
        ids = engine.current_gate_ids()
        return [str(item) for item in ids] if isinstance(ids, (list, tuple)) else []
    except Exception:  # Includes AttributeError: an engine without the method has no receipts to cite.
        return []


def _preauthorized(engine, decision):
    """SPEC 5.8 item 8.3: the ledger pre-authorized exactly this remote and target. Any doubt reads as no (fail closed);
    the normal permit check still runs after it."""
    try:
        release = engine.status()['autonomy']['release']
        return (isinstance(decision.remote, str) and bool(decision.remote) and isinstance(decision.target, str)
                and bool(decision.target) and release['remote'] == decision.remote and release['target'] == decision.target)
    except Exception:
        return False


def _raw_state(state_file):
    """The unvalidated state of a file the engine cannot load; None when it is unreadable or unparseable."""
    try:
        return json.loads(Path(state_file).read_text())
    except (OSError, ValueError, UnicodeError):
        return None


def _raw_autonomy_active(state_file):
    """O29: the unvalidated `autonomy.active` flag of a state file the engine cannot load; unparseable counts as active."""
    data = _raw_state(state_file)
    if data is None:
        return True
    auto = data.get('autonomy') if isinstance(data, dict) else None
    return isinstance(auto, dict) and auto.get('active') is True


def _other_session(engine, session_id):
    """O37: the run is bound to a harness session and the payload names a different one. Either missing: False."""
    if not isinstance(session_id, str) or not session_id:
        return False
    try:
        bound = engine.status()['session'].get('harness_session')
    except Exception:
        return False  # Opaque adapters and unreadable sessions keep the Stop behavior they had.
    return isinstance(bound, str) and bool(bound) and bound != session_id


def _raw_unattended(state_file):
    """The unattended lock from the raw state file: False when there is no file or the run never kept a report; True for
    a stopped run without an owner receipt for its run id, and for a file that cannot be read (fail closed)."""
    path = Path(state_file)
    if not path.is_file():
        return False
    data = _raw_state(path)
    return True if not isinstance(data, dict) else raw_unattended(data)


def _raw_session_active(state_file):
    """O35: an ended run under a changed policy is unarmed; an unparseable or active state stays armed."""
    data = _raw_state(state_file)
    if not isinstance(data, dict) or 'session' not in data:
        return True  # Unparseable or not a recorded session: fail closed.
    session = data['session']
    return not (session is None or (isinstance(session, dict) and session.get('active') is False))


def _compact_brief(text):
    """The brief without its empty sections ("### Title" followed only by "  - none"): they cost context and say nothing."""
    out, lines, i = [], text.split('\n'), 0
    while i < len(lines):
        if lines[i].startswith('### ') and i + 1 < len(lines) and lines[i + 1].strip() == '- none' \
                and (i + 2 >= len(lines) or not lines[i + 2].startswith('  - ')):
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out).strip()


def _report_context(engine):
    try:
        brief = engine.status().get('last_brief')
        if isinstance(brief, dict) and isinstance(brief.get('text'), str):
            return ' Run brief (' + str(brief.get('reason')) + '): ' + _compact_brief(brief['text'])[:2000] \
                + ' Full report: ' + str(brief.get('path')) + '.'
        report = engine.autonomy_report()
    except Exception:
        return ''
    if not isinstance(report, dict) or not isinstance(report.get('text'), str):
        return ''
    return ' Autonomy report (' + str(report.get('reason')) + '): ' + _compact_brief(report['text'])[:2000] \
        + ' Full report: ' + str(report.get('path')) + '.'


_DEADLINE = [None]  # time.monotonic() by which the current merged-delete check must finish; None outside one


def _remaining(limit):
    """`limit` seconds, cut to what is left of the merged-delete deadline; 0.0 once it has passed."""
    if _DEADLINE[0] is None:
        return limit
    return max(0.0, min(limit, _DEADLINE[0] - time.monotonic()))


def _git_out(repo, *args, timeout=10):
    """(returncode, stdout) of a git command in repo; a spawn error or timeout is (1, '') so callers fail closed."""
    timeout = _remaining(timeout)
    if timeout <= 0 and _DEADLINE[0] is not None:
        return 1, ''
    try:
        done = subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL, timeout=timeout)
        return done.returncode, done.stdout.decode(errors='replace').strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ''


def _first_parent_trees(repo, default):
    """The trees of the first-parent commits of default, at most 2000 (one rev-list call)."""
    code, out = _git_out(repo, 'rev-list', '--first-parent', '-n2000', '--format=%T', default, timeout=30)
    return {line for line in out.splitlines() if line and not line.startswith('commit ')} if code == 0 else set()


def _branch_merged(repo, tip, default):
    """SPEC 5.14 item 4.5: tip is an ancestor of default, or its tree is a first-parent tree of default,
    or tip is an ancestor of a local or remote-tracking ref whose tree is (evaluated afresh at each delete)."""
    if _git_out(repo, 'merge-base', '--is-ancestor', tip, default)[0] == 0:
        return True
    trees = _first_parent_trees(repo, default)
    if not trees:
        return False
    code, tree = _git_out(repo, 'rev-parse', '--verify', '--quiet', tip + '^{tree}')
    if code == 0 and tree in trees:
        return True
    code, out = _git_out(repo, 'for-each-ref', '--contains', tip, '--format=%(refname)%09%(tree)', 'refs/heads', 'refs/remotes', timeout=30)
    if code != 0:
        return False
    return any(line.partition('\t')[2] in trees for line in out.splitlines() if '\t' in line)


def _remote_tip_matches(repo, remote, branch):
    """SPEC 5.14 item 4.4: `git ls-remote` reports the branch at the remote-tracking tip. Prompts are off and
    the call has a 3 s limit; any failure, timeout or difference is False."""
    code, tracking = _git_out(repo, 'rev-parse', '--verify', '--quiet', 'refs/remotes/%s/%s' % (remote, branch))
    if code != 0 or not tracking:
        return False
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    try:
        proc = subprocess.Popen(['git', '-C', str(repo), 'ls-remote', remote, 'refs/heads/' + branch], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                **portable.group_kwargs())
    except OSError:
        return False
    try:
        out, _ = proc.communicate(timeout=_remaining(3) or 0.01)
    except subprocess.TimeoutExpired:
        try:
            portable.kill_group(proc)
        except OSError:
            pass
        proc.communicate()
        return False
    if proc.returncode != 0:
        return False
    rows = [line.split() for line in out.decode(errors='replace').splitlines() if line.strip()]
    return len(rows) == 1 and len(rows[0]) == 2 and rows[0][0] == tracking and rows[0][1] == 'refs/heads/' + branch


def _armed_defaults(engine):
    """The default branch names each remote reported when autonomy was armed; {} without an engine or an armed run."""
    try:
        found = (engine.status()['autonomy'] or {}).get('remote_defaults') or {}
        return {k: v for k, v in found.items() if isinstance(k, str) and isinstance(v, str) and v}
    except Exception:
        return {}


MERGED_DELETE_BUDGET = 25.0  # seconds; under the 30 s PreToolUse hook timeout in hooks/claude.json


def _merged_delete_check(decision, cwd, engine=None, plane=False):
    """SPEC 5.14 item 4: a deny payload for a merged-delete that is not safe, else None. The whole check shares one
    deadline: a slow repository or remote is denied with that reason instead of the hook being killed mid-answer."""
    _DEADLINE[0] = time.monotonic() + MERGED_DELETE_BUDGET
    try:
        denied = _merged_delete_checked(decision, cwd, engine, plane)
        if denied is None and time.monotonic() >= _DEADLINE[0]:
            return _deny('The merged-delete check ran out of time (%d s); refusing to delete %s' % (MERGED_DELETE_BUDGET, decision.branch)).output
        return denied
    finally:
        _DEADLINE[0] = None


def _merged_delete_checked(decision, cwd, engine=None, plane=False):
    branch, remote = decision.branch, decision.remote if decision.kind == 'remote' else None
    if not branch:
        return _deny('Branch deletion must run plainly in the session repository').output
    if remote and _git_out(cwd, 'config', '--get', 'remote.%s.url' % remote)[1] == '':
        return _deny('Remote %s is not configured' % remote).output
    if remote:
        # The delete goes to the push URL and ls-remote reads the fetch URL: both must name one repository.
        code, fetch = _git_out(cwd, 'remote', 'get-url', remote)
        pcode, pushes = _git_out(cwd, 'remote', 'get-url', '--push', '--all', remote)
        if code != 0 or pcode != 0 or not fetch or any(url != fetch for url in pushes.splitlines() or ['']):
            return _deny('Remote %s push URL differs from its fetch URL; refusing to delete %s' % (remote, branch)).output
    # Full refnames only (R2): a local branch or tag named origin/main must not shadow the default, and a ref
    # is read only after it exists exactly, so rev-parse's short-name lookup never finds a decoy (G2f).
    tracked = 'refs/remotes/%s/' % (remote or 'origin')
    # The owner-confirmed default first, then the usual names: a repository whose default is `trunk` or `master` resolves too.
    names = list(dict.fromkeys([x for x in (_armed_defaults(engine).get(remote or 'origin'), 'main', 'master') if x]))
    heads = [tracked + 'HEAD'] + [tracked + n for n in names] + ([] if remote else ['refs/heads/' + n for n in names])
    default = sha = None
    for ref in heads:
        if ref.endswith('/HEAD'):
            ref = _git_out(cwd, 'symbolic-ref', '--quiet', ref)[1]
        if not ref or _git_out(cwd, 'show-ref', '--verify', '--quiet', ref)[0] != 0:
            continue
        code, target = _git_out(cwd, 'rev-parse', '--verify', '--quiet', ref + '^{commit}')
        if code == 0 and target:
            default, sha = ref, target
            break
    if sha is None:
        return _deny('The default branch cannot be resolved; refusing to delete %s' % branch).output
    if default.startswith(tracked):
        name, label = default[len(tracked):], default[len('refs/remotes/'):]
    elif default.startswith('refs/heads/'):
        name = label = default[len('refs/heads/'):]
    else:
        return _deny('The default branch cannot be resolved; refusing to delete %s' % branch).output
    # FS2-1: on a case-insensitive filesystem refs/heads/Main is the file refs/heads/main.
    fold = (lambda text: text.casefold()) if _git_out(cwd, 'config', '--bool', 'core.ignorecase')[1] == 'true' else (lambda text: text)
    if fold(branch) == fold(name):
        return _deny('Branch %s is the default branch' % branch).output
    code, current = _git_out(cwd, 'symbolic-ref', '--short', '-q', 'HEAD')
    if code == 0 and fold(current) == fold(branch):
        return _deny('Branch %s is checked out' % branch).output
    namespace = 'refs/remotes/%s/' % remote if remote else 'refs/heads/'
    tracking = namespace + branch
    # The tip comes from the exact listed row: rev-parse would resolve a case variant to another branch's tip,
    # and with a case twin (FC3) git deletes both refs, so a twin is never deleted whatever core.ignorecase says.
    code, listing = _git_out(cwd, 'for-each-ref', '--format=%(refname)%09%(objectname)', namespace)
    rows = dict(line.split('\t', 1) for line in listing.splitlines() if '\t' in line) if code == 0 else {}
    if tracking not in rows:
        return _deny('Branch %s does not exist' % branch).output
    if any(ref != tracking and ref.casefold() == tracking.casefold() for ref in rows):
        return _deny('Branch %s has a case-variant twin; refusing to delete' % branch).output
    code, tip = _git_out(cwd, 'rev-parse', '--verify', '--quiet', rows[tracking] + '^{commit}')
    if code != 0 or not tip:
        return _deny('Branch %s does not exist' % branch).output
    if remote and not _remote_tip_matches(cwd, remote, branch):
        return _deny('Remote %s does not report %s at the tracking tip' % (remote, branch)).output
    if not _branch_merged(cwd, tip, sha) and not (plane and _held_elsewhere(cwd, engine, branch, tip)):
        return _deny('Branch %s is not merged into %s (no ancestor, tree or covering-branch evidence)' % (branch, label)).output
    return None


def _run_branch(engine, branch):
    """Section 3.3: a branch the run made (absent from the local and remote branch lists recorded at arm) that no recorded
    pull request names as head or base. False without an engine, a recorded list or on any doubt."""
    try:
        state = engine.status()
        auto = state.get('autonomy') or {}
        before = auto['local_branches_at_arm'], auto['remote_branches_at_arm']
        entries = [e for e in state.get('pull_requests') or [] if isinstance(e, dict)]
        if not all(isinstance(names, list) for names in before):
            return False
        if branch in before[0] or branch in before[1]:
            return False
        return not any(branch in (e.get('head_ref'), e.get('base_ref')) for e in entries)
    except Exception:
        return False


def _held_elsewhere(cwd, engine, branch, tip):
    """True for a run branch whose tip a remote branch other than its own counterpart contains (section 3.3)."""
    if engine is None or not _run_branch(engine, branch):
        return False
    code, out = _git_out(cwd, 'for-each-ref', '--contains', tip, '--format=%(refname)', 'refs/remotes', timeout=30)
    if code != 0:
        return False
    own = re.compile(r'refs/remotes/[^/]+/' + re.escape(branch))
    return any(ref and not own.fullmatch(ref) and not ref.endswith('/HEAD') for ref in out.splitlines())


_CLEANUP_PLAIN = re.compile(r'[A-Za-z0-9_./:+=-]+( [A-Za-z0-9_./:+=-]+)*')


def _autonomy_cleanup(command, decision, cwd, engine=None):
    """Cleanup of merged work under autonomy, for three plain one-command shapes; None for any other command.
    `git branch -d B` and `git worktree remove PATH` (no force) need the merged-delete proof for the branch; the
    worktree must be a linked worktree of this repository, not the session's own. `git worktree prune` only drops
    records of worktrees already gone from disk. Git itself refuses to remove a worktree with uncommitted work."""
    if cwd is None or not _CLEANUP_PLAIN.fullmatch(command.strip()):
        return None  # Quoting, wrappers, chaining or substitution: not a plain cleanup command
    words = command.split()
    if words[:3] == ['git', 'worktree', 'prune'] and set(words[3:]) <= {'-n', '-v', '--dry-run', '--verbose'}:
        return HookResult({})
    if len(words) == 4 and words[:3] in (['git', 'branch', '-d'], ['git', 'branch', '--delete']):
        branch = words[3]
    elif len(words) == 4 and words[:3] == ['git', 'worktree', 'remove'] and not words[3].startswith('-'):
        branch = _worktree_branch(cwd, words[3])
        if isinstance(branch, HookResult):
            return branch
    else:
        return None
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9._/+-]*', branch):
        return _deny('Branch %s is not a plain branch name' % branch)
    merged = replace(decision, category='merged-delete', kind='local', branch=branch, remote=None)
    denied = _merged_delete_check(merged, cwd, engine, plane=True)
    return HookResult(denied) if denied else HookResult({})


_RM_PLAIN = re.compile(r'[A-Za-z0-9_./:+=*?\[\]~-]+( [A-Za-z0-9_./:+=*?\[\]~-]+)*')
_RM_FLAGS = re.compile(r'-[A-Za-z]+|--(?:force|recursive|verbose|dir)')
_FIND_ACTIONS = {'-exec', '-execdir', '-ok', '-okdir', '-fprint', '-fprint0', '-fprintf', '-fls'}


def _linked_worktrees(cwd):
    """The resolved roots of the linked worktrees of the repository at cwd; the main checkout is left out."""
    code, out = _git_out(cwd, 'worktree', 'list', '--porcelain')
    if code != 0:
        return []
    roots = [line[len('worktree '):] for line in out.splitlines() if line.startswith('worktree ')]
    return [Path(root).resolve() for root in roots[1:]]


def _rm_in_worktrees(command, cwd):
    """Section 3.4: `rm` or `find ... -delete` as one plain command whose every operand lies inside a linked worktree
    and outside `.git`. An operand with `$`, a backtick or a leading `~` is never resolved. A glob operand is judged by
    the directory before its first glob character, which may be a worktree root; a hidden-name pattern is refused."""
    if cwd is None or not _RM_PLAIN.fullmatch(command.strip()):
        return False  # Quoting, chaining, redirects and substitution: not a plain command
    words = command.split()
    if words[0] == 'rm':
        operands, options = [], True
        for word in words[1:]:
            if options and word == '--':
                options = False
            elif options and word.startswith('-'):
                if not _RM_FLAGS.fullmatch(word):
                    return False
            else:
                operands.append(word)
    elif words[0] == 'find' and '-delete' in words and not _FIND_ACTIONS & set(words):
        operands = []
        for word in words[1:]:
            if word.startswith('-'):
                break
            operands.append(word)
        operands = operands or ['.']
    else:
        return False
    roots = _linked_worktrees(cwd)
    if not operands or not roots:
        return False
    for operand in operands:
        glob = re.search(r'[*?\[]', operand)
        if operand.startswith('~'):
            return False
        if glob:
            head = operand[:glob.start()]
            tail = operand.rsplit('/', 1)[-1]
            if tail.startswith('.') or '..' in head.split('/'):
                return False
            target = (Path(cwd) / (head.rsplit('/', 1)[0] if '/' in head else '')).resolve()
            if not any(target == root or root in target.parents for root in roots):
                return False
            continue
        target = (Path(cwd) / operand).resolve()
        root = next((r for r in roots if r in target.parents), None)
        if root is None or any(part.casefold() == '.git' for part in target.relative_to(root).parts):
            return False
    return True


def _autonomy_file(path, cwd):
    """True when `path` is one of the settings files in `protected.autonomy_files` (any directory)."""
    parts = tuple(part.casefold() for part in (Path(cwd) / path).resolve().parts)
    return any(parts[-len(t):] == t for t in (tuple(x.casefold() for x in PurePosixPath(f).parts)
                                              for f in _PROTECTED['autonomy_files']))


def _is_autonomy_file_text(text):
    """A looser test for the mod bypass: the path (or a patch text) names a settings file. Over-matching only sends the
    call to this hook."""
    text = text.replace('\\', '/').casefold()
    return any(f.casefold() in text for f in _PROTECTED['autonomy_files'])


def _worktree_branch(cwd, path):
    """The branch of the linked worktree at `path`, or a deny when it is not one this cleanup may remove."""
    target = (Path(cwd) / path).resolve()
    here = Path(cwd).resolve()
    if target == here or target in here.parents:
        return _deny('Worktree %s holds the session directory' % path)
    code, out = _git_out(cwd, 'worktree', 'list', '--porcelain')
    if code != 0:
        return _deny('Worktrees cannot be listed; refusing to remove %s' % path)
    entries = [block.splitlines() for block in out.split('\n\n') if block.strip()]
    for index, lines in enumerate(entries):
        fields = dict(line.split(' ', 1) if ' ' in line else (line, '') for line in lines)
        if Path(fields.get('worktree', '')).resolve() != target:
            continue
        if index == 0:
            return _deny('Worktree %s is the main worktree' % path)
        ref = fields.get('branch', '')
        if not ref.startswith('refs/heads/'):
            return _deny('Worktree %s has no branch checked out; its work cannot be proven merged' % path)
        return ref[len('refs/heads/'):]
    return _deny('%s is not a worktree of this repository' % path)


def _on_default_branch(cwd, engine=None):
    """SPEC 5.1: the branch is read from the payload cwd's own worktree; any doubt counts as the default branch. The default
    is what origin/HEAD names, else `main` or `master`; a default the remote reported when autonomy was armed counts too."""
    try:
        current = subprocess.check_output(['git', '-C', str(cwd), 'symbolic-ref', '--short', 'HEAD'],
                                          stderr=subprocess.PIPE, timeout=10).decode().strip()
    except (OSError, subprocess.SubprocessError):
        return True  # Detached HEAD or a git error: fail closed.
    try:
        head = subprocess.check_output(['git', '-C', str(cwd), 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD'],
                                       stderr=subprocess.PIPE, timeout=10).decode().strip()
        defaults = {head[len('origin/'):] if head.startswith('origin/') else head}
    except (OSError, subprocess.SubprocessError):
        defaults = {'main', 'master'}
    return current in defaults | set(_armed_defaults(engine).values())


def _main_worktree(cwd):
    """A15: the main worktree of a linked worktree; None for a bare common directory."""
    common = subprocess.check_output(['git', '-C', str(cwd), 'rev-parse', '--git-common-dir'],
                                     stderr=subprocess.PIPE).decode().strip()
    path = (Path(cwd) / common).resolve()  # A relative result is relative to cwd; an absolute one wins the join.
    return path.parent if path.name == '.git' else None


def _run_location(cwd):
    """Return (repo, state_dir) of the run that governs this cwd; own state first (A15)."""
    from .paths import repository, state_location
    repo = repository(cwd)
    state_dir = state_location(repo)
    if not (state_dir / 'state.json').is_file():
        main = _main_worktree(cwd)
        if main is not None and main != repo and (state_location(main) / 'state.json').is_file():
            return main, state_location(main)
    return repo, state_dir


def _release_call(payload):
    """A shell call of class release or release-multi. A mod `tool.call` hook cannot ask the user, so it passes an
    `ask` on and this native hook raises the prompt even while the mod is live."""
    data = payload.get('tool_input')
    command = data.get('command', data.get('cmd')) if isinstance(data, dict) else None
    if not isinstance(payload.get('tool_name'), str) or payload['tool_name'] not in _SHELL_TOOLS or not isinstance(command, str):
        return False
    try:
        return classify_command(command).klass in {'release', 'release-multi'}
    except Exception:
        return True  # Unclassifiable: let the full hook decide


def _ledger_call(payload):
    """An edit of autonomy.md or of a settings file, or a shell command that arms or disarms autonomy or starts a new run.
    The mod does not know the autonomy state, so these always go through this hook, which does."""
    data = payload.get('tool_input')
    if not isinstance(data, dict) or not isinstance(payload.get('tool_name'), str):
        return False
    name = payload['tool_name']
    if name in _SHELL_TOOLS:
        command = data.get('command', data.get('cmd'))
        return isinstance(command, str) and (_switches_autonomy(command) or _starts_new_run(command))
    paths = [data.get('file_path', data.get('path'))] if name != 'apply_patch' else [data.get('command', data.get('patch'))]
    return any(isinstance(p, str) and ('autonomy.md' in p or _is_autonomy_file_text(p)) for p in paths)


def _mod_is_live(payload):
    """A12: a fresh marker carrying this copy's rules hash means the mod already guarded."""
    session = payload.get('session_id')
    if not isinstance(session, str) or not re.fullmatch(_MARKER['session_id_pattern'], session):
        return False
    try:
        marker = json.loads((_marker_dir() / (session + '.json')).read_text())
        age = int(time.time() * 1000) - marker['heartbeat_ms']
        return (marker['session_id'] == session and not isinstance(marker['heartbeat_ms'], bool)
                and 0 <= age < _MARKER['fresh_ms']
                and marker['rules_sha256'] == guard_digest())
    except (OSError, ValueError, KeyError, TypeError):
        return False


_CRASH_TOOL = {'name': None}  # The tool named by the payload being handled, for the crash handler below


def main(argv=None):
    """Run the hook. An unexpected crash must not let a guarded call through: a shell or edit tool call is denied (exit 2)
    with the cause, and every other event or tool gets an empty answer so the session itself keeps working."""
    _CRASH_TOOL['name'] = None
    event = next((a for a in (argv if argv is not None else sys.argv[1:]) if not a.startswith('-')), None)
    try:
        return _main(argv)
    except SystemExit:
        raise
    except Exception as exc:
        name = _CRASH_TOOL['name']
        if event == 'PreToolUse' and (name is None or isinstance(name, str) and (name in _MOD_TOOLS or name in _EDIT_TOOLS or name in _SHELL_TOOLS
                                                  or name in {'Agent', 'Task'} or name in _APPROVAL_TEXT_TOOLS)):
            reason = 'Orchestra guard could not check this call (%s: %s); report it to the plugin owner' % (type(exc).__name__, exc)
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                     'permissionDecisionReason': reason}}))
            print(reason, file=sys.stderr)
            return 2
        print('{}')
        return 0


def _prompt_submit(payload):
    """UserPromptSubmit never blocks a prompt: any failure prints an empty answer and exits 0."""
    reply = {}
    try:
        if isinstance(payload, dict) and isinstance(payload.get('cwd'), str) and payload['cwd']:
            from .prompt_approval import handle_prompt
            repo, state_dir = _run_location(payload['cwd'])
            reply = handle_prompt(payload, state_dir, repo)
    except Exception:
        reply = {}
    print(json.dumps(reply))
    return 0


def _main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument('event', choices=['SessionStart', 'PreToolUse', 'SubagentStart', 'Stop', 'Interrupt', 'SessionEnd', 'UserPromptSubmit'])
    parser.add_argument('--harness', choices=['claude'], default='claude')
    parser.add_argument('--from-mod', action='store_true')
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get('tool_name'), str):
        _CRASH_TOOL['name'] = payload['tool_name']
    if args.event == 'UserPromptSubmit':
        return _prompt_submit(payload)
    if (args.event == 'PreToolUse' and args.harness == 'claude' and not args.from_mod
            and isinstance(payload, dict) and isinstance(payload.get('tool_name'), str)
            and payload.get('tool_name') in _MOD_TOOLS and not _reviewer_call(payload)
            and not _foreign_subagent(payload)
            and not _release_call(payload)
            and not _soften_call(payload)
            and not _ledger_call(payload)
            and _mod_is_live(payload)):
        print('{}')
        return 0
    state_dir = os.environ.get('ORCHESTRA_STATE_DIR')
    engine = None
    armed = False
    autonomy = False
    busy = False
    missing_cwd = False
    build_error = None
    if args.event in {'PreToolUse', 'Interrupt', 'Stop', 'SubagentStart'} and isinstance(payload, dict) and isinstance(payload.get('cwd'), str):
        missing_cwd = args.event == 'PreToolUse' and not os.path.isdir(payload['cwd'])
        try:
            from .paths import StateRootError, load_policy
            repo, state_dir = _run_location(payload['cwd'])
            # Discovery is read-only. Construct the engine only for an existing run.
            if (state_dir / 'state.json').is_file():
                armed = True  # A state file that cannot be loaded fails closed: armed, no permit.
                try:
                    from .engine import Engine
                    engine = Engine(state_dir, repo, policy=load_policy(state_dir), lock_wait=LOCK_WAIT)
                    try:
                        session = engine.status()['session']
                        armed = bool(session and session.get('active'))
                    except (TypeError, KeyError, AttributeError):
                        pass  # Opaque engine adapters stay armed.
                except Exception as exc:
                    busy = type(exc).__name__ == 'StateBusy'  # By name: the engine module may be replaced in tests
                    if not (busy and args.event != 'PreToolUse'):
                        engine = None  # A busy Stop or Interrupt keeps its engine: Stop polls the lock, Interrupt blocks on it
                    armed = _raw_session_active(state_dir / 'state.json')  # O35
                    autonomy = _raw_autonomy_active(state_dir / 'state.json')
                if args.event in {'PreToolUse', 'SubagentStart'} and not armed:
                    engine = None  # An inactive session is an unarmed run.
        except StateRootError:
            raise  # An unsafe fallback root is a crash, not 'no run': the crash wrapper denies the call
        except (ImportError, OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            pass
    if args.event == 'SessionStart' and isinstance(payload, dict):
        _prune_markers(payload.get('session_id'))
    if (args.event in {'SessionStart', 'SessionEnd'} and isinstance(payload, dict) and isinstance(payload.get('cwd'), str)
            and (args.event == 'SessionStart' or args.event == 'SessionEnd')):
        try:
            from .paths import load_policy
            from .engine import Engine
            repo, state_dir = _run_location(payload['cwd'])
            if (state_dir / 'state.json').is_file():
                engine = Engine(state_dir, repo, policy=load_policy(state_dir), lock_wait=LOCK_WAIT)
        except Exception as exc:
            engine = None  # Unloadable state: SessionStart still returns context; a lost lease is recovered by hand
            if (args.event == 'SessionEnd' and state_dir is not None and (Path(state_dir) / 'state.json').is_file()
                    and _raw_session_active(Path(state_dir) / 'state.json')):  # O35: an ended run has nothing to record
                build_error = exc
    unattended = args.event == 'PreToolUse' and state_dir is not None and _raw_unattended(Path(state_dir) / 'state.json')
    result = handle_event(args.event, payload, harness=args.harness, state_dir=state_dir, engine=engine, armed=armed,
                          autonomy=autonomy, busy=busy, missing_cwd=missing_cwd, started=started,
                          mode=_guard_mode(state_dir) if args.event == 'PreToolUse' else 'protect', unattended=unattended)
    if build_error is not None and not result.output:
        result = HookResult({'systemMessage': 'Orchestra session end could not be recorded: ' + str(build_error)
                             + '. A run that holds a lost lease is recovered by hand with '
                             + '`orchestra.py --actor A --lease L interrupt` (A and L from the start receipt).'})
    print(json.dumps(result.output))
    if result.exit_code == 2:
        print(result.output['hookSpecificOutput']['permissionDecisionReason'], file=sys.stderr)
    return result.exit_code


if __name__ == '__main__':
    sys.exit(main())
