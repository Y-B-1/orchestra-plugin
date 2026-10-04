"""Native hook adapter. Shell inspection and caller identity are best effort.

Reference wire contracts: https://learn.chatgpt.com/docs/hooks and
https://code.claude.com/docs/en/hooks (checked 2026-09-30).
"""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import subprocess
import time

from .guards import RULES, classify_command, guard_digest

_PROTECTED = RULES['protected']
_MARKER = RULES['marker']
_EDIT_TOOLS = set(RULES['tools']['edit'])
_SHELL_TOOLS = set(RULES['tools']['shell'])
_REBIND_SOURCES = ('clear', 'resume', 'fork')


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


def _deny(reason, malformed=False):
    return HookResult({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': reason}}, 2 if malformed else 0)


def _marker_dir():
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    return (base.expanduser() / 'orchestra' / 'mods').resolve()


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
    parts = resolved.parts
    if _PROTECTED['component'] in parts:
        return True
    # Every harness directory in the path counts, not only the first (B-F4).
    for i, part in enumerate(parts):
        if part in _PROTECTED['harness_dirs']:
            tail = parts[i + 1:]
            if tail and (tail[0] in _PROTECTED['files'] or
                         (tail[0] == 'agents' and any(x.startswith(tuple(_PROTECTED['agents_prefixes'])) for x in tail[1:]))):
                return True
    return False


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


def handle_event(event, payload, *, harness='codex', state_dir=None, engine=None, armed=False):
    """Decide output; optional engine adapter owns locked state operations.

    `armed` marks a run whose state could not be loaded: release classes deny (fail closed).
    A loaded engine implies an armed run; neither means unarmed.
    """
    if harness not in {'codex', 'claude'}:
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
        if not worker and isinstance(session_id, str) and session_id:
            context += ' Harness session id: ' + session_id + '. Pass --harness-session ' + session_id + ' to orchestra.py start.'
        return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': context}})
    if event == 'SubagentStart':
        # A11: only Orchestra agents get worker context.
        agent_type = payload.get('agent_type')
        if isinstance(agent_type, str) and agent_type.startswith('orchestra:'):
            return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': WORKER_CONTEXT}})
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
            return HookResult({'systemMessage': 'Orchestra session end could not be recorded: ' + str(exc)})
        return HookResult({})
    if event == 'Interrupt':
        if engine is not None:
            try:
                session = engine.status()['session']
                if session.get('active'):
                    engine.interrupt(session['actor'], session['lease'])
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                return HookResult({'systemMessage': 'Orchestra interruption could not be recorded: ' + str(exc)})
        return HookResult({})
    if event == 'Stop':
        if engine is None:
            return HookResult({})
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
    role = os.environ.get('ORCHESTRA_ROLE', 'main')  # Advisory, caller-controlled marker.
    if role != 'main' and name in {'Agent', 'Task', 'spawn_agent', 'create_thread', 'send_message_to_thread'}:
        return _deny('Workers do not delegate')
    cwd = payload.get('cwd', os.getcwd())
    if not isinstance(cwd, str):
        return _deny('Malformed cwd', True)
    if name in _EDIT_TOOLS:
        try:
            if name == 'apply_patch':
                paths = _patch_paths(data.get('command', data.get('patch')))
            else:
                path = data.get('file_path', data.get('path'))
                if not isinstance(path, str) or not path:
                    raise ValueError('Missing file path')
                paths = [path]
            if any(_protected(path, cwd, state_dir) for path in paths):
                return _deny('Use the structured coordinator API for state; protect installed runtime configuration')
        except (ValueError, OSError) as exc:
            return _deny(str(exc), True)
    if name not in _SHELL_TOOLS:
        return HookResult({})
    command = data.get('command', data.get('cmd'))
    if not isinstance(command, str):
        return _deny('Missing shell command', True)
    decision = classify_command(command)
    klass = decision.klass
    if klass == 'deny':
        return _deny(decision.reason, decision.category == 'malformed')
    if klass in {'release', 'release-multi'} and (engine is not None or armed):
        if klass == 'release-multi':
            return _deny(decision.reason)
        if engine is None or not decision.remote or not decision.target:
            return _deny('Release needs a configured exact structured command and current permit')
        try:
            permit = engine.check_release(decision.remote, decision.target, argv=list(decision.argv))
            if not permit:
                raise ValueError('No current release permit')
        except (OSError, ValueError, KeyError, RuntimeError, AttributeError) as exc:
            return _deny('Release denied: ' + str(exc))
    return HookResult({})  # allow, boundary (until autonomy, B10) and unarmed release classes


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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('event', choices=['SessionStart', 'PreToolUse', 'SubagentStart', 'Stop', 'Interrupt', 'SessionEnd'])
    parser.add_argument('--harness', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--from-mod', action='store_true')
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        payload = None
    if (args.event == 'PreToolUse' and args.harness == 'claude' and not args.from_mod
            and isinstance(payload, dict) and _mod_is_live(payload)):
        print('{}')
        return 0
    state_dir = os.environ.get('ORCHESTRA_STATE_DIR')
    engine = None
    armed = False
    if args.event in {'PreToolUse', 'Interrupt', 'Stop'} and isinstance(payload, dict) and isinstance(payload.get('cwd'), str):
        try:
            from .paths import load_policy
            repo, state_dir = _run_location(payload['cwd'])
            # Discovery is read-only. Construct the engine only for an existing run.
            if (state_dir / 'state.json').is_file():
                armed = True  # A state file that cannot be loaded fails closed: armed, no permit.
                try:
                    from .engine import Engine
                    engine = Engine(state_dir, repo, policy=load_policy(state_dir))
                    try:
                        session = engine.status()['session']
                        armed = bool(session and session.get('active'))
                    except (TypeError, KeyError, AttributeError):
                        pass  # Opaque engine adapters stay armed.
                except Exception:
                    engine = None
                if args.event == 'PreToolUse' and not armed:
                    engine = None  # An inactive session is an unarmed run.
        except (ImportError, OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            pass
    if (args.event in {'SessionStart', 'SessionEnd'} and isinstance(payload, dict) and isinstance(payload.get('cwd'), str)
            and (args.event == 'SessionEnd' or (args.harness == 'claude' and payload.get('source') in _REBIND_SOURCES))):
        try:
            from .paths import load_policy
            from .engine import Engine
            repo, state_dir = _run_location(payload['cwd'])
            if (state_dir / 'state.json').is_file():
                engine = Engine(state_dir, repo, policy=load_policy(state_dir))
        except Exception:
            engine = None  # Unloadable state: SessionStart still returns context; a lost lease is recovered by hand
    result = handle_event(args.event, payload, harness=args.harness, state_dir=state_dir, engine=engine, armed=armed)
    print(json.dumps(result.output))
    if result.exit_code == 2:
        print(result.output['hookSpecificOutput']['permissionDecisionReason'], file=sys.stderr)
    return result.exit_code


if __name__ == '__main__':
    sys.exit(main())
