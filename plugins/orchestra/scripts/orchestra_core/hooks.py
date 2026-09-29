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

from .guards import classify_command


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


def _protected(path, cwd, state_dir):
    resolved = (Path(cwd) / path).resolve()
    if state_dir:
        state = Path(state_dir).expanduser().resolve()
        if resolved == state or state in resolved.parents:
            return True
    parts = resolved.parts
    if '.orchestra' in parts:
        return True
    for harness in ['.codex', '.claude']:
        if harness in parts:
            tail = parts[parts.index(harness) + 1:]
            if tail and (tail[0] in {'hooks.json', 'config.toml', 'settings.json'} or
                         (tail[0] == 'agents' and any(x.startswith('orchestra-') for x in tail[1:]))):
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


def handle_event(event, payload, *, harness='codex', state_dir=None, engine=None):
    """Decide output; optional engine adapter owns locked state operations."""
    if harness not in {'codex', 'claude'}:
        raise ValueError('Unsupported harness')
    if not isinstance(payload, dict):
        return _deny('Malformed hook payload', True) if event == 'PreToolUse' else HookResult({})
    if event == 'SessionStart':
        # Native agent_type, where supplied, is a routing hint, never authentication.
        worker = bool(payload.get('agent_type')) or os.environ.get('ORCHESTRA_ROLE', 'main') != 'main'
        context = WORKER_CONTEXT if worker else CONTEXT
        return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': context}})
    if event == 'SubagentStart':
        return HookResult({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': WORKER_CONTEXT}})
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
        if payload.get('stop_hook_active') or engine is None:
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
    if name in {'apply_patch', 'Edit', 'Write', 'MultiEdit'}:
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
    if name not in {'Bash', 'exec_command', 'shell', 'shell_command'}:
        return HookResult({})
    command = data.get('command', data.get('cmd'))
    if not isinstance(command, str):
        return _deny('Missing shell command', True)
    decision = classify_command(command)
    if decision.action == 'deny':
        return _deny(decision.reason, decision.category == 'malformed')
    if decision.action == 'release':
        if engine is None or not decision.remote or not decision.target:
            return _deny('Release needs a configured exact structured command and current permit')
        try:
            permit = engine.check_release(decision.remote, decision.target, argv=list(decision.argv))
            if not permit:
                raise ValueError('No current release permit')
        except (OSError, ValueError, KeyError, RuntimeError, AttributeError) as exc:
            return _deny('Release denied: ' + str(exc))
    return HookResult({})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('event', choices=['SessionStart', 'PreToolUse', 'SubagentStart', 'Stop', 'Interrupt', 'SessionEnd'])
    parser.add_argument('--harness', choices=['codex', 'claude'], default='codex')
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        payload = None
    state_dir = os.environ.get('ORCHESTRA_STATE_DIR')
    engine = None
    if args.event in {'PreToolUse', 'Interrupt', 'Stop'} and state_dir and isinstance(payload, dict) and isinstance(payload.get('cwd'), str):
        try:
            from .engine import Engine
            engine = Engine(state_dir, payload['cwd'])
        except (ImportError, OSError, ValueError, RuntimeError):
            pass
    result = handle_event(args.event, payload, harness=args.harness, state_dir=state_dir, engine=engine)
    print(json.dumps(result.output))
    if result.exit_code == 2:
        print(result.output['hookSpecificOutput']['permissionDecisionReason'], file=sys.stderr)
    return result.exit_code


if __name__ == '__main__':
    sys.exit(main())
