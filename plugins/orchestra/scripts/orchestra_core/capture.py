"""SubagentStop capture: save an Orchestra worker's final message and record it as the card's report.

The stopped agent maps to its card through the `Assignment: WORKER TOKEN` line (or the prose `Worker name W, assignment
token T`) in the first user message of its transcript. Caller-supplied identifiers are routing hints, never authority:
the engine still checks the worker name and token against the running card."""
import json
from pathlib import Path
import re

from .paths import atomic

_ASSIGNMENT = re.compile(r'^[ \t]*Assignment:[ \t]+(\S+)[ \t]+(\S+)[ \t]*$', re.M)
_PROSE = re.compile(r'Worker name[ \t]+([^\s,]+),[ \t]+assignment token[ \t]+([A-Za-z0-9_-]+)')
_SAFE = re.compile(r'[A-Za-z0-9_-]+')
_LINES = 64


def _first_user_text(path):
    with open(path, encoding='utf-8', errors='replace') as stream:
        for _, line in zip(range(_LINES), stream):
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get('message') if isinstance(entry, dict) else None
            if not isinstance(message, dict) or (entry.get('type') or message.get('role')) != 'user':
                continue
            content = message.get('content')
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return '\n'.join(b['text'] for b in content if isinstance(b, dict) and isinstance(b.get('text'), str))
    return ''


def _transcript(payload):
    path = payload.get('agent_transcript_path')
    if isinstance(path, str) and path:
        return path
    base, session, agent = payload.get('transcript_path'), payload.get('session_id'), payload.get('agent_id')
    if all(isinstance(v, str) and v for v in (base, session, agent)):
        return str(Path(base).parent / session / 'subagents' / ('agent-' + agent + '.jsonl'))
    return None


def _assignment(text):
    found = _ASSIGNMENT.search(text) or _PROSE.search(text)
    return (found.group(1), found.group(2).rstrip('.')) if found else (None, None)


def _save(directory, name, message):
    atomic(directory / (name + '.md'), message.encode('utf-8'))


def _has_report_lines(message):
    return bool(re.search(r'^STATUS: ', message, re.M) and re.search(r'^ARTIFACT: ', message, re.M))


def _running(engine, worker, token):
    state = engine.status()
    session = state.get('session')
    if not session or not session.get('active'):
        return False
    return any(t.get('assignment') == token and t.get('worker') == worker and t.get('state') == 'running'
               for t in state.get('tasks', {}).values())


def capture(payload, engine):
    """The SubagentStop answer: `{}`, or a block carrying the engine's refusal. Never raises."""
    try:
        return _capture(payload, engine)
    except Exception:
        return {}


def _capture(payload, engine):
    agent_type, message = payload.get('agent_type'), payload.get('last_assistant_message')
    if not isinstance(agent_type, str) or not agent_type.startswith('orchestra:') or agent_type == 'orchestra:orchestrator':
        return {}
    if engine is None or not isinstance(message, str) or not message.strip():
        return {}
    session = engine.status().get('session')
    if not session or not session.get('active'):
        return {}
    path = _transcript(payload)
    if path is None:
        return {}
    text = _first_user_text(path)  # An unreadable transcript raises: nothing is written
    reports = Path(engine.state_dir) / 'reports'
    agent_id = payload.get('agent_id')
    unmatched = 'unmatched-' + agent_id if isinstance(agent_id, str) and _SAFE.fullmatch(agent_id) else None
    worker, token = _assignment(text)
    if worker is None or not _SAFE.fullmatch(token):
        if unmatched:
            _save(reports, unmatched, message)
        return {}
    if not _running(engine, worker, token):
        return {}
    if not _has_report_lines(message):
        if unmatched:
            _save(reports, unmatched, message)
        return {}
    _save(reports, token, message)
    try:
        engine.report(worker, token, message)
    except Exception as exc:
        if payload.get('stop_hook_active') is True:
            return {}
        return {'decision': 'block', 'reason': 'Orchestra refused your report: %s. Fix it and end again with the STATUS and '
                'ARTIFACT lines first.' % ' '.join(str(exc).split())}
    return {}
