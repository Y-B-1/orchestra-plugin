"""SPEC 5.10 items 5 and 10: the fresh-context relaunch harness. It runs `claude -p` passes until autonomy stops."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import uuid

from .engine import Engine, EngineError
from .paths import atomic, load_policy

PROMPT = Path(__file__).resolve().parents[2] / 'config/relaunch-prompt.md'
EXIT = {'complete': 0, 'parked-only': 3, 'no-ready-card': 3, 'deadline': 4, 'disarmed': 5, 'ledger-tampered': 5}
FORWARD_WAIT = 10  # seconds the harness waits for the pass after forwarding a signal


class _Interrupted(Exception):
    pass


def _say(text):
    print(json.dumps({'error': text}), file=sys.stderr)


def _code(reason):
    return EXIT.get(reason, 5)


def _backoff(streak):
    return min(60 * 2 ** (streak - 1), 900)


def _read(path):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _markers(directory):
    for marker in directory.glob('pass-*.marker'):
        try:
            marker.unlink()
        except FileNotFoundError:
            pass


def run(repo, state_dir, permission_mode, model=None, launcher=None, clock=time.time, sleep=time.sleep):
    """Run passes until a stop; returns the exit code of SPEC 5.10 item 10."""
    state_dir = Path(state_dir)
    engine = Engine(state_dir, repo, load_policy(state_dir), clock=clock)
    run_dir = state_dir / 'relaunch'
    harness_path = run_dir / 'harness.json'
    status = engine.status()
    auto = status.get('autonomy')
    session = status.get('session')
    if (not auto or not auto.get('relaunch') or (session and session.get('active'))
            or not (auto['active'] or auto.get('last_stop_reason'))):
        _say('End the interactive session first; relaunch needs an active run with relaunch autonomy armed and no active session')
        return 2
    harness = _read(harness_path)
    number = harness.get('pass', 0) if isinstance(harness.get('pass'), int) else 0
    streak = harness.get('stalled_streak', 0) if isinstance(harness.get('stalled_streak'), int) else 0
    prompt = PROMPT.read_text()
    if launcher:
        command = list(launcher)
    else:
        command = ['claude', '-p', prompt, '--permission-mode', permission_mode]
        if model:
            command += ['--model', model]
        command += ['--output-format', 'text']
    current = {}  # the running pass: process, marker
    state = {'busy': False, 'signals': []}  # busy: the main thread is inside an engine call (it may hold the state lock)

    def call(function, *args):
        state['busy'] = True
        try:
            return function(*args)
        finally:
            state['busy'] = False
            if state['signals']:
                raise _Interrupted()

    def send(signum):
        process = current.get('process')
        if process is not None:
            try:
                os.killpg(process.pid, signum)
            except (ProcessLookupError, PermissionError):
                pass

    def forward(signum, _frame):
        """Record the signal and never take the state lock here (SPEC 5.10 item 5.7). Outside an engine call the main
        loop is interrupted at once; inside one the pass gets the signal now and the loop stops when the call returns."""
        first = not state['signals']
        state['signals'].append(signum)
        if state['busy']:
            if first:
                send(signum)
                state['sent'] = True
            return
        if first:
            raise _Interrupted()

    def stop():
        """Disarm first, outside any engine call, so no continuation survives; the pass gets the signal; then 130."""
        signum = state['signals'][0] if state['signals'] else signal.SIGTERM
        state['busy'] = True
        try:
            engine.disarm_autonomy()
        except (EngineError, OSError, ValueError):
            pass
        finally:
            state['busy'] = False
        if not state.get('sent'):
            send(signum)
        process = current.get('process')
        if process is not None:
            try:
                process.wait(timeout=FORWARD_WAIT)
            except subprocess.TimeoutExpired:
                pass

    previous = {}
    if threading.current_thread() is threading.main_thread():
        for name in ('SIGINT', 'SIGTERM'):
            previous[name] = signal.signal(getattr(signal, name), forward)
    try:
        while True:
            settled = call(engine.settle)
            if settled['stopped']:
                return _code(settled['reason'])
            if not settled['armed']:
                return 5
            before = settled['signature']
            number += 1
            nonce = uuid.uuid4().hex
            _markers(run_dir)
            marker = run_dir / ('pass-' + nonce + '.marker')
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(nonce + '\n')
            current['marker'] = marker
            env = dict(os.environ, ORCHESTRA_RELAUNCH_PASS=nonce, ORCHESTRA_STATE_DIR=str(state_dir))
            try:
                with (run_dir / ('pass-%d.log' % number)).open('wb') as log:
                    try:
                        process = subprocess.Popen(command, cwd=str(repo), env=env, stdout=log, stderr=subprocess.STDOUT,
                                                   stdin=subprocess.PIPE if launcher else subprocess.DEVNULL,
                                                   start_new_session=True)
                    except OSError as exc:
                        _say('Launcher not found or not runnable: %s' % exc)
                        return 127
                    current['process'] = process
                    if launcher:
                        try:
                            process.stdin.write(prompt.encode())
                            process.stdin.close()
                        except (BrokenPipeError, OSError):
                            pass
                    process.wait()
                    current.pop('process', None)
                session = call(engine.status).get('session')
                if session and session.get('active'):
                    try:
                        call(engine.end_pass_session, nonce)
                    except EngineError:
                        _say('A session not started by this pass is active')
                        return 2
            finally:
                try:
                    marker.unlink()
                except FileNotFoundError:
                    pass
            after = call(engine.settle)
            streak = streak + 1 if after['signature'] == before else 0
            atomic(harness_path, json.dumps({'pass': number, 'signature': after['signature'],
                                             'stalled_streak': streak}, indent=2).encode())
            print('pass %d exited; stalled streak %d' % (number, streak), file=sys.stderr)
            if after['stopped']:
                return _code(after['reason'])
            if streak:
                sleep(_backoff(streak))
    except _Interrupted:
        stop()
        return 130
    finally:
        for name, handler in previous.items():
            signal.signal(getattr(signal, name), handler)
