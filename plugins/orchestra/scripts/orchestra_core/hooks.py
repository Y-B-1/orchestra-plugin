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

from . import delta, portable
from .approval import APPROVAL_PROMPT, MERGE_SEGMENT, merge_decision, raw_unattended
from .guards import (RULES, Decision, _WORD_START, _command_words, _gh_readings, _pipelines, _segments, _shell_payload, classify_command,
                     guard_digest, runs_test_suite)

_PROTECTED = RULES['protected']
_MARKER = RULES['marker']
_MOD_TOOLS = {'Bash', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}  # The mod guards only these; any other tool needs Python.
_EDIT_TOOLS = set(RULES['tools']['edit'])
_SCHEDULERS = set(RULES['tools']['scheduler'])
_APPROVAL_TEXT_TOOLS = _SCHEDULERS | {'SendMessage'}  # a call to one of these must never carry the approval word alone
_SHELL_TOOLS = set(RULES['tools']['shell'])
_REBIND_SOURCES = ('clear', 'resume', 'fork')
STOP_LOCK_BUDGET = 8.0  # SPEC 5.16 item 4: seconds from hook start that a busy-state Stop waits for the lock
LOCK_WAIT = 2.0  # SPEC 5.16 item 3: seconds a hook read waits for the state lock
MISSING_CWD = 'Session directory no longer exists: cd to an existing directory, then retry'
BUSY = 'Orchestra state is busy; retry'
AGENT_GUARD = ('Orchestra run active: use an orchestra:* agent (investigator-code for search, builder for edits), because only '
               'those get the worker brief, role limits and standing orders and return evidence the run can review')
_REVIEWER_TYPES = ('orchestra:code-reviewer', 'orchestra:critic')
_LEASE_FLAG = re.compile(r'(?<![\w-])--lease(?![\w-])')  # not --force-with-lease
LEASE_COORDINATOR_ONLY = 'The coordinator lease is coordinator-only: a worker never runs orchestra.py with --lease'
AUTONOMY_STOPPED = 'Orchestra autonomy stopped: %s. The run brief is in %s.'
STATE_SHELL = ('a shell command may not touch the Orchestra state directory; run orchestra.py for engine commands, and the '
               'Write tool for review packages and progress notes')
SUBAGENT_GUARD = ('Orchestra run active: this agent is not an orchestra:* agent; stop and report. '
                  'Start Agent and Workflow workers with an orchestra:<role> type')


CONTEXT = (
    'Orchestra is enabled. You are the main coordinator. Read the orchestra skill '
    'before substantial work. Own assignments, bounded file reservations, exact '
    'artifact evidence, independent review and integration. Workers never delegate '
    'or change coordinator state. Session start injects context only; do not repair '
    'the repository, resume prior runs or arm autonomy without an explicit request. '
    '`start --recover` of this session\'s own run is not a resume: it arms no autonomy. '
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
    """`<ORCHESTRA_STATE_DIR>/mods` when that is absolute or starts with `~/` (marker.ts writes the same place), else
    `<state home>/orchestra/mods`."""
    override = os.environ.get('ORCHESTRA_STATE_DIR', '')
    if override.startswith('~/'):
        override = os.path.expanduser(override)
    if override and os.path.isabs(override):
        return (Path(override) / 'mods').resolve()
    from .paths import state_home
    return (state_home() / 'orchestra' / 'mods').resolve()


def _protected(path, cwd, state_dir):
    resolved = (Path(cwd) / path).resolve()
    if state_dir:
        state = Path(state_dir).expanduser().resolve()
        if resolved == state or state in resolved.parents:
            # Review packages are coordinator-authored too: their contents, never the directory entry itself.
            inside = resolved.relative_to(state).parts
            if len(inside) > 1 and inside[0] in _PROTECTED['state_dir_exceptions']:
                return False
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


_PROVIDER_DELETE = re.compile(r'\bgh\b[^|;&\n]*\b(?:%s)\b' % '|'.join(r'%s\s+%s' % tuple(pair) for pair in RULES['boundary']['gh']))


def _provider_delete(command):
    """A release or repository delete on the provider (`gh release delete`, `gh repo delete`): the unattended lock denies
    it like a release. Either check counts: the raw text, or the words as bash reads them, so quoting or escaping a word
    does not hide it (R7), and a `gh` word past the first (a `find -exec` payload) is read too. Text the guard cannot
    read word by word (a substitution or expansion, a heredoc, a shell string, an unparsable command) counts as one.
    Local deletes (`rm`, `git tag -d`) keep their ordinary path after the owner's disarm."""
    command = re.sub(r'\\\r?\n', '', command)
    if _PROVIDER_DELETE.search(command) or re.search(r'\$|`|<<|<\(|>\(', command):
        return True
    try:
        for segment in _segments(command):
            words = _command_words(segment)
            name = PurePosixPath(words[0]).name if words else ''
            if name in {'sh', 'bash', 'zsh', 'dash', 'ksh', 'eval', 'source', '.'}:
                return True
            for i, word in enumerate(words):
                if PurePosixPath(word).name == 'gh':
                    readings = _gh_readings(words[i:])  # every flag position (HK1); None past the cap counts
                    if readings is None or any(r[1:3] in RULES['boundary']['gh'] for r in readings):
                        return True
    except ValueError:
        return True
    return False


LEDGER_LOCKED = ('The autonomy ledger and the autonomy switch belong to the owner while autonomy is armed: '
                 'the owner changes them with /orchestra-autonomy off, then edits and arms again.')


UNATTENDED_LOCKED = ('The last autonomous run stopped and its work waits for the owner: releases, merges, scheduler tools and '
                     'settings edits stay denied. Type `approved` in the owner\'s session, or run '
                     '`orchestra.py autonomy disarm` in a terminal.')


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


GUARD_MODES = ('minimal', 'normal', 'protect')
RELEASE_WORKFLOWS = ['release*', 'publish*', 'deploy*']  # the policy key `release_workflows` replaces these


def _guard_mode(state_dir):
    """The mode `policy.json` selects, read on every call with or without `state.json`: no file or no state directory
    is `minimal`; `minimal`, `normal` and `protect` are themselves; a file that cannot be read or checked, or any other
    value, is `protect` (fail closed)."""
    if state_dir is None:
        return 'minimal'
    try:
        from .paths import load_policy
        policy = load_policy(state_dir)
    except Exception:
        return 'protect'
    if policy is None:
        return 'minimal'
    mode = policy.get('guard_mode', 'minimal')
    return mode if isinstance(mode, str) and mode in GUARD_MODES else 'protect'


def handle_event(event, payload, *, harness='claude', state_dir=None, engine=None, armed=False, autonomy=False,
                 busy=False, missing_cwd=False, started=None, mode='protect', unattended=False):
    """`mode` is the guard mode (`minimal`, `normal` or `protect`; the default keeps every direct caller on the strict
    verdicts). `minimal` leaves generic command classification to Claude Code's permission mode and keeps only the
    Orchestra-specific denials; no mode ever asks.
    `unattended` marks a stopped run whose report is kept without an owner receipt: it locks like an active run.
    A warning collected while deciding rides on an otherwise empty answer as `additionalContext`."""
    notes = []
    if engine is not None and not busy and isinstance(payload, dict) and not payload.get('agent_id') and (
            event == 'Stop' or (event == 'PreToolUse' and payload.get('tool_name') in _SHELL_TOOLS
                                and 'orchestra.py' in str((payload.get('tool_input') or {}).get('command') or ''))):
        level = (payload.get('effort') or {}).get('level') if isinstance(payload.get('effort'), dict) else None
        _record_model(engine, payload, level if level in EFFORTS else None)  # live m1: the first turn has no earlier record
    result = _decide(event, payload, notes, mode if mode in ('minimal', 'normal') else 'protect', harness=harness, state_dir=state_dir,
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
        if not worker and engine is not None and payload.get('source') != 'fork' and isinstance(session_id, str) and session_id:
            try:
                engine.revive_harness_session(session_id)  # A restart of the same conversation keeps its lease
            except Exception:
                pass
        if not worker:
            _record_model(engine, payload)  # Bookkeeping, not progress; any error is swallowed
        if not worker and engine is not None:
            line, armed = _run_line(engine)
            context += line
            if not armed:
                context += _report_context(engine)  # while autonomy is armed the last brief's stop reason is stale
            context += _leftovers(engine, payload.get('transcript_path'))
            if _other_session(engine, session_id) and _run_active(engine):
                context += (' An Orchestra run is active in this repository but bound to another session, so this session is not '
                            'its coordinator: it reads only and may use any agent type. To move the run here once that session '
                            'has ended, run `orchestra.py start --recover --take-over --harness-session ' + str(session_id) + '`.')
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
    if event == 'SubagentStop':
        from .capture import capture  # Lazy: only this event reads transcripts
        before = _board(engine)
        answer = capture(payload, engine)
        if not answer:
            _note_pending(engine, before)
        return HookResult(answer)
    if event == 'PostToolUse':
        return HookResult(_post_agent(payload, engine))
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
            armed_before = _armed_now(engine)
            reason = engine.hook_stop()
            if isinstance(reason, str) and reason:
                if armed_before and _ends_with_question(payload):
                    reason += ' ' + DECIDE_OR_PARK
                return HookResult({'decision': 'block', 'reason': reason})
            if armed_before:
                return HookResult(_stopped_note(engine) if not _armed_now(engine) else {})
            return HookResult(_board_stop(engine, payload))
        except (OSError, ValueError, KeyError, RuntimeError, AttributeError):
            return HookResult({})  # Corrupt/unarmed state never creates continuation.
    if event != 'PreToolUse':
        return HookResult({})
    name, data = payload.get('tool_name'), payload.get('tool_input')
    if not isinstance(name, str) or not name or not isinstance(data, dict):
        return _deny('Malformed tool payload', True)
    if name == 'AskUserQuestion':
        return _answer_question(payload, data, engine)
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
    shell = data.get('command', data.get('cmd')) if name in _SHELL_TOOLS else None
    if locked and isinstance(shell, str):
        lock = 'Autonomy is active: ' if auto_on else UNATTENDED_LOCKED + ' '
        where = state_dir if state_dir is not None else getattr(engine, 'state_dir', None)
        if isinstance(where, (str, os.PathLike)) and _touches_state(shell, where, payload.get('cwd')) and not _cli_only(shell):
            return _deny(lock + STATE_SHELL)
        if _moves_default(shell, payload.get('cwd') if isinstance(payload.get('cwd'), str) else None, engine):
            return _deny(lock + 'no merge into or move of the default or a protected branch. '
                         + (_hint(engine, state_dir) if auto_on else 'Denied: ' + shell.strip()[:80]))
    if not locked and isinstance(shell, str):
        where = state_dir if state_dir is not None else getattr(engine, 'state_dir', None)
        if isinstance(where, (str, os.PathLike)) and Path(where).is_dir() and _writes_state(shell, where, payload.get('cwd')):
            return _deny(STATE_SHELL)  # engine state is protected in every mode, locked or not
    if mode == 'minimal' and name in _SHELL_TOOLS and role != 'subagent':
        # Generic command classification is Claude Code's permission mode; the state, runtime and release locks of an
        # autonomous or unattended run took the full path above (`locked`), and role limits cover only workers. The
        # merge guard is Orchestra's own: after `approved` it checks the printed merges in every mode.
        return _minimal_merge_gate(shell, payload, state_dir, engine) if isinstance(shell, str) else _deny('Missing shell command', True)
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
                path = data.get('notebook_path') if name == 'NotebookEdit' else data.get('file_path', data.get('path'))
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
    if _worker_lease_call(payload, command):
        return _deny(LEASE_COORDINATOR_ONLY)  # a worker role limit in every mode
    if role == 'subagent' and str(payload.get('agent_type')).startswith(_REVIEWER_TYPES) and runs_test_suite(command):
        gates = _gate_ids(engine)
        if gates:  # a worker role limit: minimal keeps it like protect; normal warns (row 43)
            reason = 'Cite gate receipt ' + ', '.join(gates) + '; reviewers do not rerun suites'
            if mode != 'normal':
                return _deny(reason)
            notes.append(_guarded(reason))
    if mode == 'minimal':
        # A worker's shell call: the role limits above applied; the merge guard too; the rest is Claude Code's call.
        return _minimal_merge_gate(command, payload, state_dir, engine)
    shaped = _cd_delete_shape(command, cwd)
    if shaped:
        found = classify_command(shaped[0])
        if found.category == 'merged-delete' or (found.boundary == 'delete' and shaped[0].startswith('git branch ')):
            command, cwd = shaped  # judged as the bare delete, in the directory the cd names
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
        refused = _soft_push_refusal(_uncomment(command), cwd, engine) if pushed or decision.category == 'release' else None
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
    active = auto_on
    if unattended and not active:
        if klass in {'release', 'release-multi'} or _starts_new_run(command) or _switches_autonomy(command, ('disarm',)) \
                or (decision.boundary == 'merge' and _on_default_branch(cwd, engine)) \
                or (decision.boundary == 'delete' and _provider_delete(command)) or _deletes_tag(command):
            return _deny(UNATTENDED_LOCKED + ' Denied: ' + (decision.reason or command.strip()[:80]))
    hint = _hint(engine, state_dir)
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
        if _rm_in_temp(command):
            return HookResult({})  # Files under the system temp directory hold no work of the run
        if engine is not None and _rm_in_worktrees(command, cwd):
            return HookResult({})  # Section 3.4: the run may delete files inside a linked worktree
        if engine is not None and _deletes_only_ignored(command, cwd):
            return HookResult({})  # Build output and caches Git ignores hold no work of the run
    if active:
        # Checked before any permit: a permit never opens a boundary while autonomy is active (12.4).
        if klass == 'release-multi':
            push = _routine_push(command)
            if push is not None and _pull_request_push(push, cwd, engine) is None:
                return HookResult({})  # Routine git work, then one pull request push: judged by the push
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
        # Normal never releases without a question; protect: a current permit lets the release run, otherwise deny.
        problem = decision.reason
        if klass == 'release' and decision.category == 'gitpush' and not locked and engine is not None and cwd is not None \
                and _pull_request_push(command, cwd, engine, plain=True) is None:
            return HookResult({})  # outside a lock a pull request push needs no permit; the owner merges it
        if klass == 'release' and engine is not None and decision.remote and decision.target:
            try:
                if engine.check_release(decision.remote, decision.target, argv=list(decision.argv)):
                    return HookResult({})
                problem = 'No current release permit'
            except (OSError, ValueError, KeyError, RuntimeError, AttributeError) as exc:
                problem = str(exc)
        if active:
            return _deny('Release denied: ' + problem)
        return _deny('Release needs a current permit (orchestra.py permit ...) or the owner\'s "approved"; Orchestra never asks. ' + problem)
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


def _uncomment(command):
    """The command with each `#` comment cut at its line end, or None when a `#` is not clearly a comment. The split reads a quote inside a comment as a real quote
    and would join the next lines into one segment, so every comment goes before it reads a word."""
    out, quote, escaped, comment, literal = [], None, False, False, -1
    for i, char in enumerate(command):
        if comment:
            comment = char != '\n'  # a comment runs to the end of its line, as the classifier reads it
            if comment:
                continue
        elif escaped:
            escaped, literal = False, i
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == '#' and (not i or command[i - 1] in _WORD_START):
            if i and (command[i - 1] == ')' or command[i - 2:i] == '\\\n'):
                return None  # the classifier may read this `#` as part of a word: do not cut a command it could see
            if literal != i - 1:  # bash reads `x\ #y` as one word: a `#` after an escaped blank starts no comment
                comment = True
                continue
        out.append(char)
    return ''.join(out)


def _soft_remainder(command):
    """R4: (the command without its softened segments, True when one of them is a push), or None when the command
    cannot be split safely: a substitution, a heredoc, a shell string, a softened segment inside a pipe, an
    unreadable segment or a `$'...'` string (the split reads none of them, so each could hide a command). A `#` comment
    is cut at its line end first."""
    if re.search(r'\$\(|`|<\(|>\(|<<|\$\'', command):
        return None
    command = _uncomment(command)
    if command is None:
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


def _pull_request_push(command, cwd, engine, plain=False):
    """Autonomy may push one feature branch for a pull request. Only the exact shape
    `git push [-u|--set-upstream] REMOTE REFSPEC` qualifies: no environment prefix, wrapper, Git option or other push
    option, a configured remote by name with no push mapping, and a refspec whose destination is one branch that is
    not the remote's default branch, `main` or `master` (compared ignoring case). REFSPEC is BRANCH, HEAD or @
    (the current branch), or SRC:DST where DST names the same branch as SRC (BRANCH or refs/heads/BRANCH). `plain`
    (protect mode, outside a lock, no autonomy state) takes the default branch from the local remote-tracking head
    instead of the ledger and skips the ledger's Push line and push URL checks; the shape, branch and release rules stay.
    None allows; otherwise the reason.
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
    if plain:  # protect outside a lock: no autonomy state, so the default comes from the local remote-tracking head
        code, head = _git_out(cwd, 'symbolic-ref', '--short', '-q', 'refs/remotes/%s/HEAD' % remote)
        default = head[len(remote) + 1:] if code == 0 and head.startswith(remote + '/') else ''
        if not default:
            return 'The default branch of %s cannot be resolved; push by hand.' % remote
        try:
            release = engine.policy.get('release') or {}
        except Exception:
            return 'The run policy cannot be read; push by hand.'
        if target.casefold() in {default.casefold(), *(x.casefold() for x in RULES['git']['autonomy_protected_branches'])}:
            return 'Never push the default or a release branch; push a feature branch and open a pull request.'
        if release.get('remote') == remote and str(release.get('target', '')).casefold() == target.casefold():
            return 'That branch is the configured release target; a release needs a permit.'
        return None
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


_PARK_HINT = "park this card with `orchestra.py park TASK --reason 'needs-owner: WHY'` and continue with other cards."


def _hint(engine, state_dir):
    """The way on under autonomy: park the card, or, when the state cannot be loaded, the owner's fresh start."""
    return _PARK_HINT if engine is not None else ('the run state is unreadable (%s); the owner starts over with '
                                                  '`orchestra.py start --new-run ...`, which keeps the old file under history/.'
                                                  % (Path(state_dir) / 'state.json' if state_dir else 'state.json'))


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


def _worker_lease_call(payload, command):
    """A call made inside an Orchestra worker whose shell command runs orchestra.py with --lease (coordinator-only)."""
    return (bool(payload.get('agent_id')) and str(payload.get('agent_type')).startswith('orchestra:')
            and isinstance(command, str) and 'orchestra.py' in command and bool(_LEASE_FLAG.search(command)))


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


_STATE_ORDER = ('queued', 'running', 'reported', 'repairing', 'parked', 'held', 'accepted')


def _age(at):
    """'Nm ago' or 'Nh ago' for an ISO time; 'at an unknown time' when it does not parse."""
    try:
        seconds = max(0, int(datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(str(at)).timestamp()))
    except (TypeError, ValueError):
        return 'at an unknown time'
    return '%dm ago' % (seconds // 60) if seconds < 7200 else '%dh ago' % (seconds // 3600)


def _live_counts(status):
    counts = {}
    for task in (status.get('tasks') or {}).values():
        counts[task.get('state')] = counts.get(task.get('state'), 0) + 1
    return ', '.join('%s %d' % (s, counts[s]) for s in _STATE_ORDER if counts.get(s)) or 'no cards'


def _live_transcripts(transcript_path):
    """How many subagent transcripts of this conversation were written in the last LIVE_TRANSCRIPT_SECONDS: a worker
    can outlive a restart, and a recently written transcript means one is still working. None when unknown."""
    if not isinstance(transcript_path, str) or not transcript_path.endswith('.jsonl'):
        return None
    root = Path(transcript_path[:-len('.jsonl')]) / 'subagents'
    try:
        cutoff = time.time() - LIVE_TRANSCRIPT_SECONDS
        return sum(1 for f in root.rglob('*.jsonl') if f.stat().st_mtime >= cutoff)
    except OSError:
        return None


LIVE_TRANSCRIPT_SECONDS = 120


def _leftovers(engine, transcript_path=None):
    """After a restart: the running worker cards, how many worker transcripts are still being written (a worker can
    outlive the restart), and the run worktrees that hold uncommitted work, so the coordinator knows what to resume
    and does not start a second worker beside a live one. Empty when there is nothing; never raises."""
    try:
        status = engine.status()
        running = [(i, t) for i, t in sorted((status.get('tasks') or {}).items())
                   if t.get('state') == 'running' and not t.get('inline')]
        parts = ['%s (worker %s, started %s)' % (i, t.get('worker'), _age(t.get('started_at'))) for i, t in running[:10]]
        dirty = []
        listing = subprocess.run(['git', '-C', str(engine.repo), 'worktree', 'list', '--porcelain'], capture_output=True,
                                 text=True, timeout=5).stdout
        for line in listing.splitlines():
            if not line.startswith('worktree '):
                continue
            path = Path(line[len('worktree '):])
            if '.claude/worktrees/' not in path.as_posix() or len(dirty) >= 10:
                continue
            changed = subprocess.run(['git', '-C', str(path), 'status', '--porcelain'], capture_output=True, text=True,
                                     timeout=5).stdout.splitlines()
            if changed:
                dirty.append('%s (%d uncommitted)' % (path.name, len(changed)))
    except Exception:
        return ''
    text = ''
    if parts:
        live = _live_transcripts(transcript_path)
        alive = '' if live is None else (' %d worker transcript%s written in the last 2 minutes;' % (live, '' if live == 1 else 's'))
        text += (' Running worker cards:' + alive + ' check each worker is gone before you redispatch its card: '
                 + '; '.join(parts) + '.')
    if dirty:
        text += ' Run worktrees with uncommitted work: ' + ', '.join(dirty) + '.'
    return text


def _report_context(engine):
    try:
        status = engine.status()
        brief = status.get('last_brief')
        if isinstance(brief, dict) and isinstance(brief.get('text'), str):
            return ' Run brief (' + str(brief.get('reason')) + ', written ' + _age(brief.get('at')) + '; live board: ' \
                + _live_counts(status) + '): ' + _compact_brief(brief['text'])[:2000] \
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


def _git_raw(repo, *args, timeout=10):
    """(returncode, raw stdout bytes) of a git command in repo, unstripped for -z output; spawn error or timeout is (1, b'')."""
    timeout = _remaining(timeout)
    if timeout <= 0 and _DEADLINE[0] is not None:
        return 1, b''
    try:
        done = subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL, timeout=timeout)
        return done.returncode, done.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, b''


def _changes_on_default(repo, tip, default):
    """True when every path tip changed since its merge base with default holds the same entry (mode and object, or
    absent) in default. Plain tree plumbing only: no merge driver, diff driver, textconv or external command runs, and
    submodule ignore config cannot hide a gitlink change.
    A branch that changed nothing loses nothing, so it counts. Any git error or unparsable output is no proof."""
    code, base = _git_out(repo, 'merge-base', default, tip)
    if code != 0 or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base):
        return False
    code, out = _git_raw(repo, 'diff-tree', '-r', '-z', '--no-renames', '--no-ext-diff', '--no-textconv',
                         '--ignore-submodules=none', '--name-only', base, tip, timeout=30)
    if code != 0 or (out and not out.endswith(b'\0')):
        return False
    paths = out.split(b'\0')[:-1]
    if not paths:
        return True
    if any(not path for path in paths):
        return False
    code, out = _git_raw(repo, '--literal-pathspecs', 'diff-tree', '-r', '-z', '--no-renames', '--no-ext-diff',
                         '--no-textconv', '--ignore-submodules=none', default, tip, '--', *paths, timeout=30)
    return code == 0 and out == b''


def _branch_merged(repo, tip, default):
    """SPEC 5.14 item 4.5: tip is an ancestor of default, or its tree is a first-parent tree of default,
    or tip is an ancestor of a local or remote-tracking ref whose tree is (evaluated afresh at each delete),
    or every path tip changed already holds tip's entry in default (cherry-picks, squash merges after default
    moved on in other files)."""
    if _git_out(repo, 'merge-base', '--is-ancestor', tip, default)[0] == 0:
        return True
    trees = _first_parent_trees(repo, default)
    if trees:
        code, tree = _git_out(repo, 'rev-parse', '--verify', '--quiet', tip + '^{tree}')
        if code == 0 and tree in trees:
            return True
        code, out = _git_out(repo, 'for-each-ref', '--contains', tip, '--format=%(refname)%09%(tree)', 'refs/heads', 'refs/remotes', timeout=30)
        if code == 0 and any(line.partition('\t')[2] in trees for line in out.splitlines() if '\t' in line):
            return True
    return _changes_on_default(repo, tip, default)


_CD_WORD = r'[A-Za-z0-9_./:+=@%,]'
_CD_PATH = r"%s[A-Za-z0-9_./:+=@%%,-]*|\"%s[A-Za-z0-9_./:+=@%%, -]*\"|'%s[A-Za-z0-9_./:+=@%%, -]*'" % ((_CD_WORD,) * 3)
_CD_DELETE = re.compile(r'(?:cd (?P<dir>%s) && )?(?P<delete>git (?:branch|push) [A-Za-z0-9_./:+=@%%, -]+?)'
                        r'(?P<err> 2>&1)?(?: \| (?P<pipe>(?:tail|head|grep|cat)(?: [A-Za-z0-9_./:+=@%%,-]+)*))?' % _CD_PATH)
_PIPE_LETTERS = {'cat': 'AbeEnstTuv', 'head': '0123456789ncqv', 'tail': '0123456789ncqv', 'grep': 'ivwxcnoqsEFGHhlLaI'}


def _pipe_reader_ok(words):
    """One read-only consumer of the delete's output: flags only, no file operand (grep takes its one pattern)."""
    program, args = words[0], words[1:]
    operands, i = [], 0
    while i < len(args):
        token = args[i]
        if token.startswith('-'):
            if not re.fullmatch(r'-[A-Za-z0-9]+', token) or any(c not in _PIPE_LETTERS[program] for c in token[1:]):
                return False
            if program in ('head', 'tail') and token[-1] in 'nc':
                i += 1
                if i >= len(args) or not re.fullmatch(r'\+?[0-9]+', args[i]):
                    return False
        else:
            operands.append(token)
        i += 1
    return len(operands) == (1 if program == 'grep' else 0)


def _common_dir(path):
    code, out = _git_out(path, 'rev-parse', '--git-common-dir')
    return os.path.realpath(os.path.join(path, out)) if code == 0 and out else None


def _cd_delete_shape(command, cwd):
    """SPEC 5.14: (the bare delete, the directory to judge it in) for `[cd DIR &&] git branch|push ... [2>&1]
    [| tail|head|grep|cat FLAGS]`, else None. DIR is a literal path with no `$`, `~`, glob or leading `-`, and its Git
    common directory is the session's own, so a nested repository or submodule is never judged as the session's."""
    if cwd is None:
        return None
    found = _CD_DELETE.fullmatch(command.strip())
    if not found or not (found['dir'] or found['err'] or found['pipe']):
        return None
    if found['pipe'] and not _pipe_reader_ok(found['pipe'].split()):
        return None
    where = found['dir'].strip('"\'') if found['dir'] else None
    target = os.path.join(cwd, where) if where else cwd
    if where and (not os.path.isdir(target) or _common_dir(target) is None or _common_dir(target) != _common_dir(cwd)):
        return None
    return found['delete'], str(target)


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
        if _merged_run_worktree(cwd, words[3]):
            return HookResult({})  # A clean run worktree whose commits the current branch already holds
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


def _merged_run_worktree(cwd, path):
    """True when `path` is a linked worktree under `<repository>/.claude/worktrees/` that is not the session's own,
    has no change `git status --porcelain` reports, and whose HEAD is an ancestor of the HEAD at cwd."""
    code, out = _git_out(cwd, 'worktree', 'list', '--porcelain')
    if code != 0 or not out.startswith('worktree '):
        return False
    main = Path(out.split('\n', 1)[0][len('worktree '):]).resolve()
    here, target = Path(cwd).resolve(), (Path(cwd) / path).resolve()
    if target == here or target in here.parents or (main / '.claude' / 'worktrees') not in target.parents:
        return False
    if target not in _linked_worktrees(cwd):
        return False
    code, status = _git_out(target, 'status', '--porcelain')
    code_head, head = _git_out(target, 'rev-parse', 'HEAD')
    if code != 0 or status or code_head != 0 or not head:
        return False
    return _git_out(cwd, 'merge-base', '--is-ancestor', head, 'HEAD')[0] == 0


_TEMP_PLAIN = re.compile(r'[A-Za-z0-9_./:+=*?\[\]~${}-]+( [A-Za-z0-9_./:+=*?\[\]~${}-]+)*')
_TMPDIR_PREFIX = re.compile(r'\$(?:TMPDIR|\{TMPDIR\})(?=/|$)')


def _rm_in_temp(command):
    """`rm` with any flags as one plain command whose every operand lies below `/tmp`, `/private/tmp` or `$TMPDIR`.
    The operand is resolved first, so a `..` or a link that leaves the directory refuses it; a glob is judged by the
    directory before it and may not start with a dot. The temp directory itself is never an operand."""
    if not _TEMP_PLAIN.fullmatch(command.strip()):
        return False
    words = command.split()
    if words[0] != 'rm':
        return False
    roots = [Path('/tmp').resolve(), Path('/private/tmp').resolve()]
    tmpdir = os.environ.get('TMPDIR')
    if tmpdir and os.path.isabs(tmpdir) and len(Path(tmpdir).resolve().parts) >= 3:
        roots.append(Path(tmpdir).resolve())
    operands, options = [], True
    for word in words[1:]:
        if options and word == '--':
            options = False
        elif options and word.startswith('-'):
            if not _RM_FLAGS.fullmatch(word):
                return False
        else:
            operands.append(word)
    if not operands:
        return False
    for operand in operands:
        if _TMPDIR_PREFIX.match(operand):
            if not tmpdir or not os.path.isabs(tmpdir):
                return False
            operand = tmpdir.rstrip('/') + operand[_TMPDIR_PREFIX.match(operand).end():]
        if '$' in operand or '{' in operand or '}' in operand or not operand.startswith('/') or '..' in operand.split('/'):
            return False
        parts = operand.split('/')
        for part in parts:
            if re.search(r'[*?\[]', part) and (part.startswith('.') or ('[' in part and '.' in part)):
                return False
        glob = re.search(r'[*?\[]', operand)
        base = operand[:glob.start()].rsplit('/', 1)[0] if glob else operand
        target = Path(base or '/').resolve()
        if not any(root in target.parents or (glob and target == root) for root in roots):
            return False
    return True


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


_STATE_NAMES = re.compile(r'(?:\.local/state|XDG_STATE_HOME\}?)/orchestra(?![A-Za-z0-9._-])|ORCHESTRA_STATE_DIR')
_PYTHON_WORD = re.compile(r'python[0-9.]*')


def _touches_state(command, state_dir, cwd):
    """GF1: a shell command whose text names the run's state directory (as given or resolved, its 24-hex identity, the
    state base or the ORCHESTRA_STATE_DIR variable), or that runs inside it. Text only: best effort, never isolation."""
    text = command.replace('\\', '/')
    state = Path(state_dir).expanduser()
    try:
        real = state.resolve()
        forms = {str(state), str(real)}
        if real.parent.name == 'orchestra':  # the default layout <base>/orchestra/<identity>: the base holds every run
            forms |= {str(real.parent), str(state.parent)}
        if isinstance(cwd, str) and cwd and (Path(cwd).resolve() == real or real in Path(cwd).resolve().parents):
            return True
    except (OSError, RuntimeError, ValueError):
        return True
    if any(re.search(re.escape(form.replace('\\', '/')) + r'(?![A-Za-z0-9._-])', text) for form in forms if form not in ('', '/', '.')):
        return True
    return bool(_STATE_NAMES.search(text) or (re.fullmatch(r'[0-9a-f]{24}', real.name) and real.name in text))


_WRITE_VERBS = {'tee', 'rm', 'rmdir', 'unlink', 'shred', 'mv', 'cp', 'install', 'ln', 'truncate', 'dd', 'chmod', 'chown',
                'set-content', 'add-content', 'out-file', 'remove-item', 'copy-item', 'move-item', 'new-item', 'clear-content',
                'touch', 'mkdir'}
_DEST_VERBS = {'cp', 'install', 'ln', 'copy-item', 'move-item'}  # the last word is the destination: a read copy is fine
_COPY_VERBS = {'cp', 'install'}  # these write their destination's content, so a coordinator note may be one
_NOTES = tuple(name for name in _PROTECTED['state_root_exceptions'] if name != 'autonomy.md')  # the ledger stays denied
_WRAPPERS = {'sudo', 'command', 'builtin', 'exec', 'nohup', 'env', 'time', 'nice'}


def _target_dir(args):
    """The directory named by `-t DIR`, `-vt DIR`, `-tDIR` or `--target-directory[=]DIR` (cp, install), or None."""
    for i, word in enumerate(args):
        if word.startswith('--target-directory='):
            return word.split('=', 1)[1]
        if word == '--target-directory' or re.fullmatch(r'-[A-Za-z]*t', word):
            return args[i + 1] if i + 1 < len(args) else ''
        if re.fullmatch(r'-t.+', word):
            return word[2:]
    return None


def _is_state_note(target, state_dir, base):
    """True when `target`, relative to `base` (None: only an absolute or home path can be resolved), is a coordinator
    note at the root of the state directory."""
    if target.startswith('$'):
        return False
    try:
        path = Path(target).expanduser()
        if not path.is_absolute():
            if base is None:
                return False
            path = Path(base).expanduser() / path
        resolved = path.resolve()
        state = Path(state_dir).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved.parent == state and resolved.name in _NOTES


def _is_state_root(target, state_dir):
    """True when `target` (a `cd` operand) is the state directory itself, as an absolute or home path."""
    if target.startswith('$') or not target.startswith(('/', '~')):
        return False
    try:
        return Path(target).expanduser().resolve() == Path(state_dir).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False


def _lands_in_state(target, state_dir, cwd, inside, notes_ok=False, at_root=True):
    """True when a write to `target` lands in the state directory. `inside` is an earlier `cd` into it, so a relative
    target names a file there; `at_root` says the last `cd` named the state root itself, the only place a relative note
    resolves. With `notes_ok`, a coordinator note at the state root does not count (the Write rule's list)."""
    relative = not target.startswith(('/', '~', '$'))
    if not (_touches_state(target, state_dir, cwd if relative else None) or (relative and inside)):
        return False
    if not notes_ok or (relative and inside and not at_root):
        return True
    base = state_dir if relative and inside else (cwd if relative else None)
    return not _is_state_note(target, state_dir, base)


def _writes_state(command, state_dir, cwd):
    """A shell command that writes into the state directory: an output redirect, tee, cp or install aimed at it, or rm, mv,
    ln, truncate, dd, chmod or `sed -i` there. Outside a lock the coordinator's notes at the state root are not state
    (redirects, tee, cp and install may write them). Reads and orchestra.py commands are not writes. Text only: best effort."""
    if _cli_only(command) or not _touches_state(command, state_dir, cwd):
        return False
    text = re.sub(r'\d*>&\s*(?:\d+|-)(?![^\s;&|<>()])|\d*>&\s*\d+(?=[\'"](?:[\s;&|<>()]|$))', ' ', command)  # a descriptor copy writes no file; `>&1new` and `>&1""/x` are files
    text = text.replace('&>', '>')
    text = re.sub(r'>&(?=\s*[^\s&>])', '>', text)  # `>&FILE` sends stdout and stderr to a file
    inside = False  # an earlier `cd` into the state directory
    at_root = False  # the last `cd` named the state root itself
    for piece in re.split(r'[;&\n]+|(?<!>)\|+', text):  # `>|` is a clobbering redirect, not a pipe
        piece = re.sub(r'^[\s({]+', '', piece)  # a subshell or group opener is punctuation, not the verb
        for target in re.findall(r'>>?\|?\s*((?:\'[^\']*\'|"[^"]*"|[^\s<>\'"])+)', piece):
            target = target.replace("'", '').replace('"', '').rstrip(')}')
            if _lands_in_state(target, state_dir, cwd, inside, notes_ok=True, at_root=at_root):
                return True
        try:
            words = shlex.split(piece.replace('>', ' '))
        except ValueError:
            words = piece.split()
        while words and (words[0] in _WRAPPERS or re.fullmatch(r'[A-Za-z_]\w*=\S*', words[0])):
            words = words[1:]
        if not words:
            continue
        verb = PurePosixPath(words[0]).name.lower()
        args = words[1:]
        if verb in ('cd', 'pushd'):
            named = [w for w in args if not w.startswith('-')]
            at_root = bool(named) and _is_state_root(named[0], state_dir)
            inside = inside or _touches_state(piece, state_dir, None)
            continue
        flagged = verb == 'sed' and any(re.match(r'-[A-Za-z]*i|--in-place', w) for w in args if w.startswith('-'))
        if verb not in _WRITE_VERBS and not flagged:
            continue
        operands = [w for w in args if not w.startswith('-')] or args
        if verb in _DEST_VERBS:
            dest = _target_dir(args)
            if dest is None:
                dest = operands[-1] if operands else ''
            recursive = any(re.fullmatch(r'-[A-Za-z]*[rRa][A-Za-z]*|--recursive|--archive', w) for w in args)
            if _lands_in_state(dest, state_dir, cwd, inside, notes_ok=verb in _COPY_VERBS and not recursive, at_root=at_root):
                return True
        elif verb == 'tee':
            if any(_lands_in_state(word, state_dir, cwd, inside, notes_ok=True, at_root=at_root) for word in operands):
                return True
        elif inside or _touches_state(piece, state_dir, cwd):
            return True
    return False


def _cli_only(command):
    """One plain `[python] orchestra.py ...` command: no chain, pipe, redirection or substitution beside it."""
    if re.search(r'[;&|<>`\n\r]|\$\(', command):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if words and _PYTHON_WORD.fullmatch(PurePosixPath(words[0]).name):
        words = words[1:]
        while words and words[0] in ('-B', '-I', '-E', '-s', '-S', '-u', '-O'):
            words = words[1:]
    return bool(words) and PurePosixPath(words[0]).name == 'orchestra.py'


def _git_argvs(command, depth=0):
    """The words after `git` and its global options for each git command in `command`, a `sh -c` payload included;
    None when the command cannot be read word by word."""
    found = []
    try:
        for segment in _segments(re.sub(r'\\\r?\n', '', command)):
            words = _command_words(segment)
            if not words:
                continue
            name = PurePosixPath(words[0]).name
            if name in {'sh', 'bash', 'zsh', 'dash', 'ksh'} or name == 'eval':
                payload = ' '.join(words[1:]) if name == 'eval' else _shell_payload(words)
                inner = _git_argvs(payload, depth + 1) if payload is not None and depth < 3 else []
                if inner is None:
                    return None
                found.extend(inner)
            elif name == 'git':
                args = words[1:]
                while args and args[0].startswith('-'):
                    if args.pop(0) in RULES['git']['global_value_options'] and args:
                        args.pop(0)
                found.append(args)
    except ValueError:
        return None
    return found


def _default_names(cwd, engine):
    """The casefolded names of the default and protected branches: the rules list, what the remote reported at arm and
    what origin/HEAD names."""
    names = {b.casefold() for b in RULES['git']['autonomy_protected_branches']}
    names |= {v.casefold() for v in _armed_defaults(engine).values()}
    if cwd is not None:
        code, head = _git_out(cwd, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
        if code == 0 and head:
            names.add(head.split('/', 1)[-1].casefold())
    return names


def _moves_default(command, cwd, engine):
    """GF2: a command that moves the default or a protected branch without a merge on it: a switch to it followed by a
    merge, rebase, reset or commit; `git branch -f|-m|-c` naming it; `git checkout|switch -B|-C` onto it;
    `git update-ref` of it (or of HEAD while on it, or from --stdin); `git fetch . SRC:DEFAULT`."""
    argvs = _git_argvs(command)
    if not argvs:
        return False
    names = None
    for args in argvs:
        if args and args[0] in ('switch', 'checkout', 'branch', 'update-ref', 'fetch'):
            names = _default_names(cwd, engine)
            break
    if names is None:
        return False

    def named(ref):
        return ref.removeprefix('refs/heads/').casefold() in names
    switched = False
    for args in argvs:
        verb, rest = (args[0], args[1:]) if args else ('', [])
        positional = [w for w in rest if not w.startswith('-')]
        if verb in ('switch', 'checkout'):
            i, target = 0, None
            while i < len(rest):
                word = rest[i]
                if word in ('-C', '-B', '--force-create') and i + 1 < len(rest) and named(rest[i + 1]):
                    return True
                if word in ('-c', '-b', '-C', '-B', '--create', '--force-create', '--orphan'):
                    i, target = i + 2, ''  # a new branch: not a switch to an existing one
                    continue
                if word == '--':
                    break
                if not word.startswith('-') and target is None:
                    target = word
                i += 1
            switched = switched or bool(target) and named(target)
        elif verb in ('merge', 'rebase', 'reset', 'commit', 'pull', 'cherry-pick', 'revert', 'am') and switched:
            return True
        elif verb == 'branch' and any(w in ('--force', '--move', '--copy') or re.fullmatch(r'-[A-Za-z]*[fmMcC][A-Za-z]*', w)
                                      for w in rest) and any(named(w) for w in positional):
            return True
        elif verb == 'update-ref':
            if '--stdin' in rest:
                return True
            refs = [w for w, before in zip(rest, [None] + rest) if not w.startswith('-') and before != '-m']
            if refs and (named(refs[0]) if refs[0].startswith('refs/heads/') else refs[0] == 'HEAD' and _on_default_branch(cwd, engine)):
                return True
        elif verb == 'fetch' and positional and positional[0].startswith(('.', '/')) \
                and any(named(w.lstrip('+').partition(':')[2]) for w in positional[1:] if ':' in w):
            return True  # a fetch from a local repository into the default branch
    return False


def _deletes_tag(command):
    """GF3: a `git tag -d|--delete` anywhere in the command; a command that cannot be read counts as one."""
    argvs = _git_argvs(command)
    if argvs is None:
        return True
    return any(args[:1] == ['tag'] and any(w == '--delete' or re.fullmatch(r'-[A-Za-z]*d[A-Za-z]*', w) for w in args[1:])
               for args in argvs)


def _minimal_merge_gate(command, payload, state_dir, engine):
    """GF5: in `minimal` only the merge guard judges a shell call: after `approved` it checks the printed merges (order,
    head, form); every other call is Claude Code's."""
    cwd = payload.get('cwd') if isinstance(payload.get('cwd'), str) and payload.get('cwd') else None
    if cwd is None:
        try:
            cwd = os.getcwd()
        except OSError:
            return HookResult({})
    merged = _merge_gate(command, cwd, state_dir, engine)
    return _deny(merged[1]) if merged is not None and merged[0] == 'deny' else HookResult({})


def _routine_push(command):
    """GF4: the push of `GIT ... && git push ...` when every command before the last `&&` is a plain `git VERB` (no
    global option, wrapper or assignment) that the classifier allows; None otherwise."""
    head, sep, push = command.strip().rpartition(' && ')
    if not sep or not head.strip() or re.search(r'[$`<>|\n\r(){}#]', head):
        return None
    try:
        for segment in _segments(head):
            if not segment.strip():
                continue
            words = shlex.split(segment)
            if len(words) < 2 or words[0] != 'git' or words[1].startswith('-') or classify_command(segment).klass != 'allow':
                return None
    except ValueError:
        return None
    return push.strip() if classify_command(head).klass == 'allow' else None


_FIND_TESTS = {'-name': 1, '-iname': 1, '-path': 1, '-ipath': 1, '-type': 1, '-maxdepth': 1, '-mindepth': 1,
               '-o': 0, '-or': 0, '-a': 0, '-and': 0, '-not': 0, '!': 0}
_FIND_CAP = 20000


def _find_matches(words, cwd, top):
    """The paths `find ROOT... TESTS -delete` would delete, listed by running the same tests with -print0 instead.
    Every root lies inside the repository at `top`; only name, path, type and depth tests are read. None for anything
    else, a timeout or more than _FIND_CAP matches."""
    i = 1
    while i < len(words) and not words[i].startswith('-') and words[i] != '!':
        i += 1
    roots, expr = words[1:i] or ['.'], words[i:]
    if expr[-1:] != ['-delete'] or expr.count('-delete') != 1 or any(re.search(r'[*?\[]', r) for r in roots):
        return None
    for root in roots:
        path = (Path(cwd) / root).resolve()
        if path != top and top not in path.parents:
            return None
    expr, j = expr[:-1], 0
    while j < len(expr):
        width = _FIND_TESTS.get(expr[j])
        if width is None or j + width >= len(expr):
            return None
        if expr[j] == '-type' and expr[j + 1] not in ('f', 'd', 'l'):
            return None
        if expr[j] in ('-maxdepth', '-mindepth') and not expr[j + 1].isdigit():
            return None
        j += 1 + width
    try:
        done = subprocess.run(['find', *roots, *expr, '-print0'], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    found = [p for p in done.stdout.decode(errors='replace').split('\0') if p]
    return found if done.returncode == 0 and len(found) <= _FIND_CAP else None


def _deletes_only_ignored(command, cwd):
    """GF4: `rm [FLAGS] PATH...` or `find ROOT... TESTS -delete`, run as one plain command, where every path it removes
    lies inside the session's repository outside `.git`, is ignored by Git and holds no tracked file. Anything Git
    does not ignore, a glob, a variable, `~` or a path outside the repository keeps the boundary deny."""
    if cwd is None or re.search(r'[;&|<>`$\n\r\\(){}~]', command):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if words[:1] == ['rm']:
        targets, options = [], True
        for word in words[1:]:
            if options and word == '--':
                options = False
            elif options and word.startswith('-'):
                if not _RM_FLAGS.fullmatch(word):
                    return False
            elif re.search(r'[*?\[]', word):
                return False
            else:
                targets.append(word)
        if not targets:
            return False
    elif words[:1] != ['find']:
        return False
    code, top = _git_out(cwd, 'rev-parse', '--show-toplevel')
    if code != 0 or not top:
        return False
    top = Path(top).resolve()
    if words[0] == 'find':
        targets = _find_matches(words, cwd, top)
        if targets is None:
            return False
    rels = []
    for target in targets:
        if '..' in PurePosixPath(target).parts:
            return False
        joined = Path(os.path.normpath(Path(cwd) / target))
        # rm removes a symlink itself, never what it points to; with a trailing `/` or `/.` it follows the link (PR2)
        path = joined.resolve() if target.endswith(('/', '/.')) else joined.parent.resolve() / joined.name
        if path == top or top not in path.parents:
            return False
        rel = path.relative_to(top)
        if any(part.casefold() == '.git' for part in rel.parts):
            return False
        rels.append(rel.as_posix())
    if not rels:
        return True  # find matched nothing: nothing is deleted
    try:
        done = subprocess.run(['git', '-C', str(top), 'check-ignore', '-z', '--stdin'], input=('\0'.join(rels) + '\0').encode(),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    if done.returncode != 0 or set(p for p in done.stdout.decode(errors='replace').split('\0') if p) != set(rels):
        return False
    for start in range(0, len(rels), 500):  # an ignored directory may still hold a force-added, tracked file
        code, tracked = _git_out(top, '--literal-pathspecs', 'ls-files', '-z', '--', *rels[start:start + 500])
        if code != 0 or tracked:
            return False
    return True


DECIDE_OR_PARK = ('Autonomy is armed and the owner is away. Decide this yourself: take the option you would recommend, '
                  'record the decision in your next message, and continue. If only the owner can answer (a secret, a code, '
                  "an account action, or a matter of their taste), park the card with `orchestra.py park TASK --reason "
                  "'needs-owner: <the question>'` and continue with other cards.")


def _answer_question(payload, data, engine):
    """AskUserQuestion while autonomy is armed: answer each question with its "(Recommended)" option, log the decisions to
    progress.md, and deny a question with no such option. Unarmed, without an engine, from a worker or from a session the
    run is not bound to: no decision, so the question reaches the person."""
    if engine is None or payload.get('agent_id') or _other_session(engine, payload.get('session_id')) or not _armed_now(engine):
        return HookResult({})
    questions = data.get('questions')
    answers = {}
    if isinstance(questions, list) and questions:
        for item in questions:
            options = item.get('options') if isinstance(item, dict) else None
            text = item.get('question') if isinstance(item, dict) else None
            if not isinstance(text, str) or not isinstance(options, list):
                answers = None
                break
            labels = [o['label'] for o in options if isinstance(o, dict) and isinstance(o.get('label'), str)
                      and o['label'].rstrip().lower().endswith('(recommended)')]
            if not labels:
                answers = None
                break
            answers[text] = ', '.join(labels) if item.get('multiSelect') is True else labels[0]
    else:
        answers = None
    if not answers:
        return _deny(DECIDE_OR_PARK)
    try:
        from .engine import _append_progress  # Lazy, like the other engine imports
        at = datetime.now(timezone.utc).isoformat(timespec='seconds')
        _append_progress(engine.state_dir, '\n'.join('- decided for the owner: %s -> %s (at %s)' % (q, a, at)
                                                    for q, a in answers.items()))
    except Exception:
        pass  # The log is a courtesy; the answer still stands
    return HookResult({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow',
                                              'updatedInput': {**data, 'answers': answers}}})


def _ends_with_question(payload):
    """True when the last assistant message ends with a question (a `?` in its last 600 characters): the message from the
    Stop payload, else the last assistant text of the transcript (its last 256 KB). Any error means no question."""
    try:
        text = payload.get('last_assistant_message')
        if not isinstance(text, str):
            text = ''
            with open(payload['transcript_path'], 'rb') as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 256 * 1024))
                lines = handle.read().decode('utf-8', 'replace').splitlines()
            for line in reversed(lines):
                try:
                    row = json.loads(line)
                    message = row['message']
                    if row.get('type') != 'assistant' or not isinstance(message.get('content'), list):
                        continue
                    parts = [c['text'] for c in message['content'] if isinstance(c, dict) and c.get('type') == 'text'
                             and isinstance(c.get('text'), str)]
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
                if parts:
                    text = '\n'.join(parts)
                    break
        return '?' in text[-600:]
    except Exception:
        return False


def _armed_now(engine):
    """Strict: True only when the engine says autonomy is active; any error is False (used to see autonomy end)."""
    try:
        return engine.autonomy_active() is True
    except Exception:
        return False


def _board(engine):
    """The lease-free board of the loaded engine, or None when it cannot be read (a mock adapter included)."""
    try:
        view = engine.view()
    except Exception:
        return None
    return view if isinstance(view, dict) else None


def _note_pending(engine, before):
    """After a SubagentStop that moved a card, append the move to `<state>/pending-delta` for the coordinator's next
    PostToolUse, prompt or Stop. Writes nothing when no card moved; any error is ignored."""
    try:
        moved = delta.delta(before, _board(engine))
        if moved:
            path = Path(engine.state_dir) / 'pending-delta'
            old = path.read_text() if path.exists() else ''
            from .paths import atomic
            atomic(path, ((old + '\n' if old else '') + moved).encode())
    except Exception:
        pass


def _post_agent(payload, engine):
    """PostToolUse on Agent or Task, made by the coordinator: print the pending delta once as context and clear it.
    Workflow agents never reach this hook; their moves reach the coordinator through the prompt and Stop hooks."""
    try:
        if engine is None or payload.get('tool_name') not in ('Agent', 'Task') or payload.get('agent_id') \
                or _other_session(engine, payload.get('session_id')):
            return {}
        directory = Path(engine.state_dir)
        path = directory / 'pending-delta'
        if not path.is_file():
            return {}
        moved = ' | '.join(path.read_text().split('\n'))
        path.unlink()
        view = _board(engine)
        command = delta.next_command(view)
        if delta.live(view):
            delta.store(directory, 'board-seen.json', view)
        return {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
                                       'additionalContext': delta.PREFIX + moved + ('. Next: ' + command if command else '')}}
    except Exception:
        return {}


def _board_stop(engine, payload):
    """Outside autonomy: block a Stop once per board signature while a card is reported or startable, naming the next
    command. Never while only workers run, with no cards, on a repeated Stop or for an engine that cannot show a board."""
    try:
        if payload.get('stop_hook_active') is True:
            return {}
        view = _board(engine)
        if not delta.live(view) or not delta.next_command(view):
            return {}
        directory = Path(engine.state_dir)
        if delta.read(directory, 'stop-seen').get('signature') == delta.signature(view):
            return {}
        delta.store(directory, 'stop-seen', view)
        return {'decision': 'block', 'reason': delta.line(view, {})}
    except Exception:
        return {}


EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')  # As engine.EFFORTS; hooks import the engine lazily


def _transcript_model(path):
    """The model of the last assistant entry in the last 256 KB of a transcript, or None for any error."""
    try:
        with open(path, 'rb') as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 262144))
            lines = handle.read().decode('utf-8', 'replace').splitlines()
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get('message') if isinstance(entry, dict) and entry.get('type') == 'assistant' else None
            model = message.get('model') if isinstance(message, dict) else None
            if isinstance(model, str) and model.strip() and not model.startswith('<'):
                return model
    except Exception:
        pass
    return None


def _record_model(engine, payload, effort=None):
    """Record the main session's model (payload, else the transcript) and effort. Bookkeeping: every error is swallowed."""
    try:
        if engine is None or payload.get('agent_id'):
            return
        model = payload.get('model')
        if not (isinstance(model, str) and model.strip()):
            path = payload.get('transcript_path')
            model = _transcript_model(path) if isinstance(path, str) and path else None
        if model is None and effort is None:
            return
        session = engine.view().get('session') or {}  # a read: an unchanged record writes nothing
        if (model is None or session.get('model') == model) and (effort is None or session.get('effort') == effort):
            return
        engine.record_model(model, effort)
    except Exception:
        pass


def _model_line(engine, view):
    """The Model fit line for a prompt, or None: the cards of the board that run on another model than the session's."""
    session = view.get('session') or {}
    if not session.get('active'):
        return None
    queued = [c for c in view.get('cards') or [] if c.get('state') == 'queued']
    model, effort = engine.session_model({'session': session})
    if not model:
        if any(c['role'] == 'builder' for c in queued):
            return 'Session model: unknown; the engine refuses no inline card on model grounds.'
        return None
    away = []
    for card in queued:
        need_model, need_effort = engine.card_model(card)
        want, have = engine._family(need_model), engine._family(model)
        higher = (want == have and need_effort in EFFORTS and effort in EFFORTS
                  and EFFORTS.index(effort) < EFFORTS.index(need_effort))
        if want and have and (want != have or higher):
            away.append('%s (%s %s)' % (card['id'], need_model, need_effort))
    if not away:
        return None
    extra = ' +%d' % (len(away) - 8) if len(away) > 8 else ''
    return 'Session model: %s%s. Cards that must go to a worker (another model): %s%s.' % (
        model, ' ' + effort if effort else '', ', '.join(away[:8]), extra)


def prompt_board(payload, engine):
    """The UserPromptSubmit answer for the board: one `Orchestra board: ...` context line when the board signature
    differs from `<state>/board-seen.json` (then stored), plus the Model fit line when it changed; `{}` otherwise."""
    try:
        if engine is None or _other_session(engine, payload.get('session_id')):
            return {}
        effort = os.environ.get('CLAUDE_EFFORT')
        _record_model(engine, payload, effort if effort in EFFORTS else None)
        view, directory = _board(engine), Path(engine.state_dir)
        parts = []
        text = delta.line(view, delta.read(directory, 'board-seen.json'))
        if text is not None:
            delta.store(directory, 'board-seen.json', view)
            (directory / 'pending-delta').unlink(missing_ok=True)
            parts.append(text)
        fit = _model_line(engine, view) if view else None
        seen = directory / 'model-seen'
        if fit is not None and (not seen.is_file() or seen.read_text() != fit):
            seen.write_text(fit)
            parts.append(fit)
        elif fit is None and seen.is_file():
            seen.unlink()
        if not parts:
            return {}
        return {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': ' '.join(parts)}}
    except Exception:
        return {}


def _stopped_note(engine):
    """GF12: the Stop that ended autonomy says why, so the coordinator does not learn it from its next deny."""
    try:
        reason = (engine.status().get('autonomy') or {}).get('last_stop_reason') or 'unknown'
        return {'systemMessage': AUTONOMY_STOPPED % (reason, Path(engine.state_dir) / 'progress.md')}
    except Exception:
        return {'systemMessage': AUTONOMY_STOPPED % ('unknown', 'progress.md')}


def _run_line(engine):
    """GF11: (one line naming a live run, whether autonomy is armed); ('', False) with no active session or any error."""
    try:
        status = engine.status()
        session = status.get('session')
        if not (isinstance(session, dict) and session.get('active') is True):
            return '', False
        auto = status.get('autonomy') if isinstance(status.get('autonomy'), dict) else {}
        armed = auto.get('active') is True
        line = ' Run active (size %s); %s; guard_mode %s; run orchestra.py status.' % (
            session.get('size') or 'unset', 'autonomy armed until %s' % auto.get('deadline') if armed else 'autonomy off',
            _guard_mode(engine.state_dir))
        return line, armed
    except Exception:
        return '', False


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
    """A shell call of class release or release-multi: this native hook decides it even while the mod is live."""
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
    paths = ([data.get('command', data.get('patch'))] if name == 'apply_patch' else [data.get('notebook_path')]
             if name == 'NotebookEdit' else [data.get('file_path', data.get('path'))])
    return any(isinstance(p, str) and ('autonomy.md' in p or _is_autonomy_file_text(p)) for p in paths)


_LOCK_TEXT = re.compile(r'orchestra/[0-9a-f]{24}|\.local/state|_STATE_|state\.json|policy\.json|autonomy\.md|progress\.md'
                        r'|review-packages|update-ref|\bbranch\b[^;&|\n]*\s-'
                        r'|\b(?:switch|checkout)\b[^\n]*\b(?:merge|rebase|reset|commit|pull|cherry-pick|revert|am)\b'
                        r'|\bfetch\b[^;&|\n]*:', re.I)


def _lock_text_call(payload):
    """A shell command whose text may touch the state directory or move the default branch (GF1, GF2): the mod does
    not know the autonomy or unattended lock, so these always reach this hook. Over-matching only costs a Python call."""
    data = payload.get('tool_input')
    if payload.get('tool_name') not in _SHELL_TOOLS or not isinstance(data, dict):
        return False
    command = data.get('command', data.get('cmd'))
    named = [os.environ.get(k, '') for k in ('ORCHESTRA_STATE_DIR', 'XDG_STATE_HOME')]
    return isinstance(command, str) and bool(_LOCK_TEXT.search(command) or any(v and v in command for v in named))


def _ledger_without_session(state_dir):
    """GF1: a state that parses but holds no valid session while an autonomy ledger exists counts as armed with autonomy
    unknown (fail closed), never as no run: a shell write of `{}` must not lift the lock."""
    data = _raw_state(Path(state_dir) / 'state.json')
    if not isinstance(data, dict):
        return False  # unparseable: the raw autonomy flag already reads it as active
    session = data.get('session')
    valid = 'session' in data and (session is None or (isinstance(session, dict) and isinstance(session.get('active'), bool)))
    return not valid and (Path(state_dir) / 'autonomy.md').is_file()


def _lock_held(payload):
    """PR2: the mod does not see an arm the engine wrote, so a live mod skips this hook only when the raw state of the
    run governing this cwd holds neither lock. Active autonomy, a kept report without a receipt, a ledger without a
    valid session, or a state that cannot be read or located: True. No run, or no repository: False."""
    cwd = payload.get('cwd')
    if not isinstance(cwd, str) or not cwd:
        return False
    try:
        from .paths import StateRootError
        override = os.environ.get('ORCHESTRA_STATE_DIR')  # state_location's override needs no git
        try:
            state_dir = Path(override).expanduser().resolve() if override else _run_location(cwd)[1]
        except StateRootError:
            return True
        state_file = state_dir / 'state.json'
        if not state_file.is_file():
            return False
    except (ImportError, OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        return False  # the full handler finds no run here either
    return _raw_autonomy_active(state_file) or _raw_unattended(state_file) or _ledger_without_session(state_dir)


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
            if not reply and (state_dir / 'state.json').is_file():
                from .engine import Engine
                from .paths import load_policy
                reply = prompt_board(payload, Engine(state_dir, repo, policy=load_policy(state_dir), lock_wait=LOCK_WAIT))
    except Exception:
        reply = {}
    print(json.dumps(reply))
    return 0


def _model_switch(payload):
    """PostModelSwitch records the main session's new model. It never blocks and never adds context."""
    try:
        if isinstance(payload, dict) and isinstance(payload.get('cwd'), str) and payload['cwd'] \
                and not payload.get('agent_id') and isinstance(payload.get('to_model'), str):
            repo, state_dir = _run_location(payload['cwd'])
            if (state_dir / 'state.json').is_file():
                from .engine import Engine
                from .paths import load_policy
                _record_model(Engine(state_dir, repo, policy=load_policy(state_dir), lock_wait=LOCK_WAIT),
                              {'model': payload['to_model']})
    except Exception:
        pass
    print('{}')
    return 0


def _main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument('event', choices=['SessionStart', 'PreToolUse', 'SubagentStart', 'SubagentStop', 'Stop', 'Interrupt', 'SessionEnd', 'UserPromptSubmit', 'PostToolUse', 'PostModelSwitch'])
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
    if args.event == 'PostModelSwitch':
        return _model_switch(payload)
    if (args.event == 'PreToolUse' and args.harness == 'claude' and not args.from_mod
            and isinstance(payload, dict) and isinstance(payload.get('tool_name'), str)
            and payload.get('tool_name') in _MOD_TOOLS and not _reviewer_call(payload)
            and not _foreign_subagent(payload)
            and not _worker_lease_call(payload, (payload.get('tool_input') or {}).get('command')
                                       if isinstance(payload.get('tool_input'), dict) else None)
            and not _release_call(payload)
            and not _soften_call(payload)
            and not _ledger_call(payload)
            and not _lock_text_call(payload)
            and _mod_is_live(payload)
            and not _lock_held(payload)):
        print('{}')
        return 0
    state_dir = os.environ.get('ORCHESTRA_STATE_DIR')
    engine = None
    armed = False
    autonomy = False
    busy = False
    missing_cwd = False
    build_error = None
    if args.event in {'PreToolUse', 'Interrupt', 'Stop', 'SubagentStart', 'SubagentStop', 'PostToolUse'} and isinstance(payload, dict) and isinstance(payload.get('cwd'), str):
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
                    autonomy = _raw_autonomy_active(state_dir / 'state.json') or _ledger_without_session(state_dir)
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
