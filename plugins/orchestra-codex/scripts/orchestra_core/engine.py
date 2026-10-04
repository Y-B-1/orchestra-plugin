"""Durable workflow consistency checks, not a hostile-worker security boundary."""
from __future__ import annotations

import contextlib
import copy
import fcntl
import hashlib
import json
import os
import math
import re
import shlex
import shutil
import signal
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from .guards import classify_command


class EngineError(ValueError):
    pass


REVIEW_ROLES = ('code-reviewer', 'critic')
CATEGORIES = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']
REBIND_WINDOW_SECONDS = 60
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT = dict(max_workers=20, required_checks=[], required_review_categories=CATEGORIES,
               gate_timeout_seconds=300, secret_scan=dict(required=False, argv=[]),
               release=dict(enabled=False, remote=None, target=None, argv=[]))


def _contracts():
    """The role-to-modes map binds a run. Method files must exist but their text does not bind it."""
    try:
        path = PACKAGE_ROOT / 'config/roles.json'
        raw = path.read_bytes()
        roles = json.loads(raw)['roles']
        result = {}
        root = (PACKAGE_ROOT / 'skills').resolve()
        for role in roles:
            name, modes, methods = role['id'], role['modes'], role['methods']
            if (not isinstance(name, str) or name in result or not modes or not methods
                    or not all(isinstance(v, str) and v.strip() for v in modes + methods)):
                raise ValueError('Invalid role contract')
            result[name] = modes
            for method in methods:
                target = (root / method).resolve()
                if root not in target.parents or not target.is_file():
                    raise ValueError('Missing required method: ' + method)
        digest = _digest(result)  # every role, the orchestrator included, binds the run
        result.pop('orchestrator', None)  # but a task never takes the orchestrator role
        return result, digest
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise EngineError('Invalid canonical role/method contract: ' + str(exc)) from exc


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return _hash(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


class Engine:
    def __init__(self, state_dir, repo, policy=None, clock=time.time):
        self._clock = clock
        self.repo = Path(repo).resolve()
        self.state_dir = Path(state_dir).resolve()
        for protected in (self.repo, PACKAGE_ROOT.resolve()):
            if self.state_dir == protected or protected in self.state_dir.parents:
                raise EngineError('Run state must live outside the repository and immutable plugin root')
        self.policy = copy.deepcopy(DEFAULT)
        if policy:
            self.policy.update(copy.deepcopy(policy))
        if isinstance(self.policy['max_workers'], bool) or not isinstance(self.policy['max_workers'], int) or self.policy['max_workers'] < 1:
            raise EngineError('Invalid worker capacity')
        timeout = self.policy['gate_timeout_seconds']
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise EngineError('Gate timeout must be positive and finite')
        for key in ('release', 'secret_scan'):
            if not isinstance(self.policy[key], dict):
                raise EngineError('Invalid policy ' + key)
        if not isinstance(self.policy['required_checks'], list):
            raise EngineError('Invalid required checks')
        categories = self.policy['required_review_categories']
        if (not isinstance(categories, list) or not categories
                or any(not isinstance(c, str) or c not in CATEGORIES for c in categories)):
            raise EngineError('required_review_categories must be a non-empty list of known categories')
        self.modes, self.contract_hash = _contracts()
        self.policy_hash = _digest(dict(policy=self.policy, contracts=self.contract_hash))
        self._git('rev-parse', '--show-toplevel')
        if Path(self._git('rev-parse', '--show-toplevel').decode().strip()).resolve() != self.repo:
            raise EngineError('repo must name repository root')
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / 'state.json'

    def _git(self, *args):
        try:
            return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            raise EngineError(exc.stderr.decode(errors='replace')) from exc

    @staticmethod
    def _in_scope(path, scope):
        return any(path == s or path.startswith(s + '/') for s in scope)

    def artifact(self, scope=None):
        """Whole-repo evidence, or with `scope` (repository-relative paths) evidence for those paths plus HEAD."""
        scope = sorted({Path(s).as_posix() for s in scope}) if scope else None
        # Hash every tracked and untracked nonignored entry. Index and status are also bound.
        names = self._git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
        entries = []
        for raw in sorted(set(names) - {b''}):
            if scope is not None and not self._in_scope(os.fsdecode(raw), scope):
                continue
            path = self.repo / os.fsdecode(raw)
            if path.is_symlink():
                value = ['symlink', os.readlink(path)]
            elif path.is_file():
                value = ['file', path.stat().st_mode & 0o777, _hash(path.read_bytes())]
            elif path.is_dir():
                # Gitlinks need their nested HEAD, dirty state and contents bound too.
                value = ['directory', self._directory_hash(path)]
            else:
                value = ['missing']
            entries.append([os.fsdecode(raw), value])
        common = Path(self._git('rev-parse', '--git-common-dir').decode().strip())
        if not common.is_absolute():
            common = self.repo / common
        index = self._git('ls-files', '--stage', '-z')
        status = self._git('status', '--porcelain=v1', '-z', '--untracked-files=all')
        result = dict(repo=str(self.repo), identity=str(common.resolve()),
                      head=self._git('rev-parse', 'HEAD').decode().strip(),
                      tree=self._git('rev-parse', 'HEAD^{tree}').decode().strip(),
                      fingerprint=_digest(entries), index=_hash(index), status=_hash(status),
                      policy=self.policy_hash)
        if scope is not None:
            lines = [l for l in index.split(b'\0') if l and self._in_scope(os.fsdecode(l.split(b'\t', 1)[-1]), scope)]
            changes, parts = [], status.split(b'\0')
            while parts:
                part = parts.pop(0)
                if not part:
                    continue
                paths = [os.fsdecode(part[3:])]
                if part[:1] in b'RC' or part[1:2] in b'RC':
                    paths.append(os.fsdecode(parts.pop(0)) if parts else '')
                if any(self._in_scope(x, scope) for x in paths):
                    changes.append(part)
            result.update(scope=scope, index=_hash(b'\0'.join(lines)), status=_hash(b'\0'.join(changes)))
        return result

    def scope_for(self, task_ids):
        """Union of the tasks' reservation files, or None (whole repo) when any task reserves no files."""
        with self._state(False) as state:
            return self._scope_of(state, task_ids)

    def _scope_of(self, state, task_ids):
        files, whole = set(), False
        for task_id in task_ids:
            if task_id not in state['tasks']:
                raise EngineError('Unknown task: ' + str(task_id))
            reserved = self._reservation(state['tasks'][task_id], state)['files']
            whole = whole or not reserved
            files.update(Path(f).as_posix() for f in reserved)
        return None if whole or not files else sorted(files)

    def _artifact_cached(self, cache, scope):
        key = tuple(scope) if scope else None
        if key not in cache:
            cache[key] = self.artifact(scope)
        return cache[key]

    @staticmethod
    def _directory_hash(path):
        entries = []
        for child in sorted(path.rglob('*')):
            if '.git' in child.relative_to(path).parts:
                continue
            if child.is_symlink():
                entries.append([str(child.relative_to(path)), 'link', os.readlink(child)])
            elif child.is_file():
                entries.append([str(child.relative_to(path)), _hash(child.read_bytes())])
        return _digest(entries)

    @contextlib.contextmanager
    def _state(self, write=True):
        if _contracts()[1] != self.contract_hash:
            raise EngineError('Role or method instructions changed; start a new run')
        with (self.state_dir / 'state.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            if self.state_path.exists():
                try:
                    state = json.loads(self.state_path.read_text())
                    self._validate_state(state)
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    raise EngineError('Malformed run state: ' + str(exc)) from exc
                if state['repo'] != str(self.repo) or state['policy'] != self.policy_hash:
                    raise EngineError('Repository or policy changed; start a new run')
            else:
                state = dict(version=1, repo=str(self.repo), policy=self.policy_hash,
                             session=None, tasks={}, reviews=[], gates=[], permits=[], autonomy=None)
            try:
                yield state
            except (KeyError, TypeError, AttributeError, IndexError) as exc:
                raise EngineError('Malformed run state or request: ' + str(exc)) from exc
            if write:
                fd, name = tempfile.mkstemp(dir=self.state_dir, prefix='.state-')
                try:
                    with os.fdopen(fd, 'w') as out:
                        json.dump(state, out, sort_keys=True, indent=2)
                        out.flush()
                        os.fsync(out.fileno())
                    os.replace(name, self.state_path)
                    directory = os.open(self.state_dir, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                finally:
                    if os.path.exists(name):
                        os.unlink(name)

    @staticmethod
    def _validate_state(state):
        if not isinstance(state, dict) or state.get('version') != 1:
            raise EngineError('Unsupported run state schema')
        for key, kind in [('repo', str), ('policy', str), ('tasks', dict),
                          ('reviews', list), ('gates', list), ('permits', list)]:
            if not isinstance(state.get(key), kind):
                raise EngineError('Invalid run state ' + key)
        for key in ('session', 'autonomy'):
            if key not in state or (state[key] is not None and not isinstance(state[key], dict)):
                raise EngineError('Invalid run state ' + key)
        session = state['session']
        if session is not None and (not isinstance(session.get('active'), bool)
                or any(not isinstance(session.get(k), str) or not session[k] for k in ('actor', 'lease'))):
            raise EngineError('Invalid session state')
        if session is not None:
            bound = session.get('harness_session')
            if 'harness_session' in session and (not isinstance(bound, str) or not bound):
                raise EngineError('Invalid harness session')
            pending = session.get('pending_rebind')
            if 'pending_rebind' in session and (not isinstance(pending, dict) or not isinstance(pending.get('from'), str)
                    or isinstance(pending.get('at'), bool) or not isinstance(pending.get('at'), (int, float))):
                raise EngineError('Invalid pending rebind')
        for name, task in state['tasks'].items():
            if not isinstance(task, dict) or task.get('id') != name or task.get('state') not in ('queued', 'running', 'reported', 'repairing', 'accepted'):
                raise EngineError('Invalid task state')
            for key in ('role', 'mode'):
                if not isinstance(task.get(key), str):
                    raise EngineError('Invalid task ' + key)
            for key in ('inputs', 'acceptance', 'files', 'resources', 'dependencies'):
                if not isinstance(task.get(key), list) or any(not isinstance(v, str) or not v.strip() for v in task[key]):
                    raise EngineError('Invalid task ' + key)
            if any(dep not in state['tasks'] for dep in task['dependencies']):
                raise EngineError('Invalid stored dependency')
        fields = {
            'reviews': {'id': str, 'reviewer': str, 'categories': list, 'tasks': list, 'final': bool,
                        'findings': list, 'artifact': dict, 'action': str, 'path': str, 'source': str, 'sha256': str},
            'gates': {'id': str, 'name': str, 'argv': list, 'exit_code': int, 'artifact': dict,
                      'after': dict, 'action': str, 'path': str, 'sha256': str, 'passed': bool},
            'permits': {'id': str, 'action': str, 'remote': str, 'target': str, 'argv': list,
                        'artifact': dict, 'lease': str},
        }
        for key, schema in fields.items():
            for item in state[key]:
                if not isinstance(item, dict) or any(not isinstance(item.get(k), kind) for k, kind in schema.items()):
                    raise EngineError('Invalid ' + key + ' state')

    def _check_contract(self, task):
        modes, digest = _contracts()
        if digest != self.contract_hash:
            raise EngineError('Role or method instructions changed; start a new run')
        if task['mode'] not in modes.get(task['role'], []):
            raise EngineError('Unavailable role or mode')
        if 'objective' in task and (not isinstance(task['objective'], str) or not task['objective'].strip()):
            raise EngineError('Task objective must be meaningful')
        if 'brief' in task:
            if not isinstance(task['brief'], str) or not task['brief'].strip():
                raise EngineError('Task brief must name a file')
            brief = Path(task['brief'])
            if not brief.is_absolute():
                brief = self.repo / brief
            if not brief.is_file() or not brief.read_bytes().strip():
                raise EngineError('Task brief must be an existing nonempty file')
            if not re.search(r'^Mode:[ \t]+' + re.escape(task['mode']) + r'[ \t]*$', brief.read_text(errors='replace'), re.M):
                raise EngineError('Task brief must carry the line Mode: ' + task['mode'])

    @staticmethod
    def _redact_leases(value):
        if isinstance(value, dict):
            return {k: Engine._redact_leases(v) for k, v in value.items() if k != 'lease'}
        if isinstance(value, list):
            return [Engine._redact_leases(v) for v in value]
        return value

    def status(self):
        """The run state without any lease: the board and `where` never see one (SPEC 11.2)."""
        with self._state(False) as state:
            return self._redact_leases(copy.deepcopy(state))

    @staticmethod
    def _lease(state, actor, lease):
        session = state['session']
        if not session or not session['active'] or session['actor'] != actor or session['lease'] != lease:
            raise EngineError('Invalid or interrupted coordinator lease')

    def validate_lease(self, actor, lease):
        """Check coordinator consistency; caller identifiers are not authentication."""
        with self._state(False) as state:
            self._lease(state, actor, lease)

    def open_session(self, actor, harness_session=None):
        if not isinstance(actor, str) or not actor.strip():
            raise EngineError('Missing coordinator')
        if harness_session is not None and (not isinstance(harness_session, str) or not harness_session.strip()):
            raise EngineError('Invalid harness session id')
        with self._state() as state:
            if state['session'] and state['session']['active']:
                raise EngineError('A coordinator session is already active')
            lease = uuid.uuid4().hex
            state['session'] = dict(actor=actor, lease=lease, active=True)
            if harness_session is not None:
                state['session']['harness_session'] = harness_session
            for task in state['tasks'].values():
                if task['state'] == 'running':
                    task['state'] = 'queued'
                    task.pop('assignment', None)
                    task.pop('report', None)
            state['permits'] = []
            return lease

    def interrupt(self, actor, lease):
        with self._state() as state:
            self._lease(state, actor, lease)
            state['session']['active'] = False
            state['permits'] = []
            state['autonomy'] = None

    def interrupt_active(self):
        """Interrupt the active session without a caller-supplied lease. Python only, for the Interrupt hook."""
        with self._state(False) as state:
            if not (state['session'] and state['session']['active']):
                return False  # Read-only unless there is a session to interrupt
        with self._state() as state:
            if not (state['session'] and state['session']['active']):
                return False
            state['session']['active'] = False
            state['permits'] = []
            state['autonomy'] = None
            return True

    @staticmethod
    def _bound_to(state, session_id):
        session = state['session']
        return bool(session and session['active'] and session.get('harness_session') == session_id)

    def end_harness_session(self, session_id):
        """The bound harness session ended: what interrupt does, with outcome 'ended'. Idempotent."""
        with self._state(False) as state:
            if not self._bound_to(state, session_id):
                return False  # A no-op never rewrites state.json
        with self._state() as state:
            if not self._bound_to(state, session_id):
                return False
            state['session'].update(active=False, outcome='ended')
            state['session'].pop('pending_rebind', None)  # harness_session stays as a record
            state['permits'] = []
            state['autonomy'] = None
            return True

    def mark_harness_rebind(self, session_id):
        """/clear or /resume: the process continues under a new id; record the pending hand-over."""
        with self._state(False) as state:
            if not self._bound_to(state, session_id):
                return False  # A no-op never rewrites state.json
        with self._state() as state:
            if not self._bound_to(state, session_id):
                return False
            state['session']['pending_rebind'] = {'from': session_id, 'at': self._clock()}
            return True

    def apply_harness_rebind(self, session_id):
        """Bind the new id when a fresh pending rebind exists (age 0..60 s); one-shot, stale entries are removed."""
        with self._state(False) as state:
            if not state['session'] or 'pending_rebind' not in state['session']:
                return False  # Read-only unless a rebind is pending (SPEC 12.6)
        with self._state() as state:
            session = state['session']
            pending = session.pop('pending_rebind', None) if session else None
            if pending is None:
                return False
            if not 0 <= self._clock() - pending['at'] <= REBIND_WINDOW_SECONDS:
                return False
            session['harness_session'] = session_id
            return True

    def add_task(self, actor, lease, task):
        task = copy.deepcopy(task)
        with self._state() as state:
            self._lease(state, actor, lease)
            for key in ('id', 'role', 'mode'):
                if not isinstance(task.get(key), str) or not task[key].strip():
                    raise EngineError('Missing task ' + key)
            if task['id'] in state['tasks']:
                raise EngineError('Duplicate task')
            self._check_contract(task)
            if self._is_release(task) and any(self._is_release(t) for t in state['tasks'].values()):
                raise EngineError('A run supports one terminal release task')
            for key in ('inputs', 'acceptance', 'files', 'resources', 'dependencies'):
                values = task.get(key)
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise EngineError('Invalid task ' + key)
                if key in ('inputs', 'acceptance') and not values:
                    raise EngineError('Empty task ' + key)
                if len(values) != len(set(values)):
                    raise EngineError('Duplicate ' + key)
            for name in task['files']:
                p = Path(name)
                if any(char in name for char in '*?[]'):
                    raise EngineError('File ownership needs explicit paths, not globs')
                if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] == '.git':
                    raise EngineError('File ownership must stay inside repository')
                resolved = (self.repo / p).resolve()
                if self.repo not in resolved.parents:
                    raise EngineError('File ownership escapes repository')
            if any(dep not in state['tasks'] for dep in task['dependencies']):
                raise EngineError('Unknown dependency or cycle')
            review_of = task.get('review_of', [])
            if (not isinstance(review_of, list)
                    or any(not isinstance(i, str) or i not in state['tasks'] for i in review_of)
                    or len(review_of) != len(set(review_of))):
                raise EngineError('Review targets must name existing tasks')
            if review_of and task['role'] not in REVIEW_ROLES:
                raise EngineError('Only independent review roles can use review_of')
            if set(review_of) & set(task['dependencies']):
                raise EngineError('Use review_of instead of an accepted dependency for reviewed work')
            if task['role'] == 'builder' and task['mode'] == 'repair':
                repair_of = task.get('repair_of')
                if repair_of not in state['tasks'] or state['tasks'][repair_of]['role'] != 'builder':
                    raise EngineError('Repair needs a specific earlier builder task')
                original = state['tasks'][repair_of]
                if original['state'] not in ('reported', 'accepted') or original.get('repaired_by'):
                    raise EngineError('Repair needs a reported builder without an existing repair')
                if repair_of in task['dependencies']:
                    raise EngineError('repair_of replaces an accepted dependency on the original')
                verdicts = self._review_verdicts(state, {}, task_id=repair_of)
                if not any(r['findings'] for r in verdicts.values()):
                    raise EngineError('Repair needs earlier checked coding findings')
                # Suspend the whole chain atomically. Reports and workers remain as history,
                # but none of those old assignments reserve capacity or writable files.
                original['repaired_by'] = task['id']
                ancestor = original
                while True:
                    ancestor['state'] = 'repairing'
                    ancestor['review_since'] = len(state['reviews'])
                    if not ancestor.get('repair_of'):
                        break
                    ancestor = state['tasks'][ancestor['repair_of']]
            # Dependencies refer only to existing immutable cards, making cycles impossible.
            task['state'] = 'queued'
            state['tasks'][task['id']] = task

    @staticmethod
    def _is_release(task):
        return task['role'] == 'operator' and task['mode'] == 'release'

    @staticmethod
    def _collides(a, b):
        if set(a['resources']) & set(b['resources']):
            return True
        return any(x == y or x in y.parents or y in x.parents
                   for x in map(Path, a['files']) for y in map(Path, b['files']))

    @staticmethod
    def _read_review(task):
        return bool(task.get('review_of')) and task['role'] in REVIEW_ROLES

    @staticmethod
    def _reservation(task, state):
        files, resources = set(task['files']), set(task['resources'])
        while task.get('repair_of'):
            task = state['tasks'][task['repair_of']]
            files.update(task['files'])
            resources.update(task['resources'])
        return dict(files=list(files), resources=list(resources))

    def _ready(self, state):
        occupied = [t for t in state['tasks'].values() if t['state'] == 'running'
                    or (t['state'] == 'reported' and not self._read_review(t))
                    or (t['state'] == 'queued' and t.get('repair_of'))]
        if sum(t['state'] == 'running' for t in occupied) >= self.policy['max_workers']:
            return []
        return [t['id'] for t in state['tasks'].values() if t['state'] == 'queued'
                and all(state['tasks'][d]['state'] == 'accepted' for d in t['dependencies'])
                and all(state['tasks'][d]['state'] in ('reported', 'accepted') for d in t.get('review_of', []))
                and not any(other['id'] != t['id']
                            and self._collides(self._reservation(t, state), self._reservation(other, state))
                            and not (other['id'] in t.get('review_of', []) and other['state'] == 'reported'
                                     and not set(t['resources']) & set(other['resources']))
                            for other in occupied)]

    def ready(self, actor, lease):
        with self._state(False) as state:
            self._lease(state, actor, lease)
            return self._ready(state)

    def dispatch(self, actor, lease, task_id, worker):
        return self._start_assignment(actor, lease, task_id, worker, inline=False)

    def start_inline(self, actor, lease, task_id):
        return self._start_assignment(actor, lease, task_id, actor, inline=True)

    def _start_assignment(self, actor, lease, task_id, worker, inline):
        with self._state() as state:
            self._lease(state, actor, lease)
            if not isinstance(worker, str) or not worker.strip() or (worker == actor and not inline):
                raise EngineError('Worker must differ from coordinator')
            task = state['tasks'].get(task_id)
            if inline and task and task['role'] in REVIEW_ROLES:
                raise EngineError('Independent review roles need a separate worker')
            if any(t.get('worker') == worker and t['state'] in ('running', 'reported') for t in state['tasks'].values()):
                raise EngineError('Worker is already reserved')
            if task_id not in self._ready(state):
                raise EngineError('Task is not ready or capacity is exhausted')
            self._check_contract(state['tasks'][task_id])
            token = uuid.uuid4().hex
            state['tasks'][task_id].update(state='running', worker=worker, assignment=token, lease=lease, inline=inline)
            return token

    def report(self, worker, token, report):
        if not isinstance(report, str) or not report.strip():
            raise EngineError('Empty worker report')
        with self._state() as state:
            task = next((t for t in state['tasks'].values() if t.get('assignment') == token), None)
            if not task or task['state'] != 'running' or task['worker'] != worker:
                raise EngineError('Invalid assignment')
            self._lease(state, state['session']['actor'], task['lease'])
            task.update(state='reported', report=report,
                        report_artifact=self.artifact(self._scope_of(state, [task['id']])))
            ancestor = task
            while ancestor.get('repair_of'):
                ancestor = state['tasks'][ancestor['repair_of']]
                ancestor['state'] = 'reported'

    def _snapshot(self, path, kind):
        path = Path(path).resolve()
        if not path.is_file() or not path.read_bytes().strip():
            raise EngineError('Evidence report must be a nonempty file')
        data = path.read_bytes()
        target = self.state_dir / (kind + '-' + uuid.uuid4().hex)
        with target.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        return dict(source=str(path), path=str(target), sha256=_hash(data))

    @staticmethod
    def _intact(receipt):
        for key in ('path', 'source'):
            if key in receipt:
                p = Path(receipt[key])
                if not p.is_file() or _hash(p.read_bytes()) != receipt['sha256']:
                    return False
        return True

    def record_review(self, actor, lease, reviewer, report_path, categories, task_ids=None, final=False, findings=None):
        with self._state() as state:
            self._lease(state, actor, lease)
            ids = list(task_ids or [])
            findings = findings or []
            if not isinstance(findings, list) or any(not isinstance(f, str) or not f.strip() for f in findings):
                raise EngineError('Invalid review findings')
            if not isinstance(reviewer, str) or not reviewer.strip() or reviewer == actor:
                raise EngineError('Review must be independent of coordinator')
            if not isinstance(categories, list) or not categories or not set(categories) <= set(CATEGORIES):
                raise EngineError('Invalid review categories')
            if not final and not ids:
                raise EngineError('Checkpoint review needs task coverage')
            if any(i not in state['tasks'] for i in ids):
                raise EngineError('Unknown reviewed task')
            if final and (len(ids) != len(set(ids)) or set(ids) not in (set(state['tasks']), self._pre_release_ids(state))):
                raise EngineError('Final review must explicitly cover every task')
            covered = [state['tasks'][i] for i in ids]
            if any(t.get('worker') == reviewer and not self._read_review(t) for t in covered):
                raise EngineError('Worker cannot review own artifact')
            if any(t['state'] not in ('reported', 'accepted') for t in covered):
                raise EngineError('Review covers incomplete work')
            scope = None if final else self._scope_of(state, ids)
            artifact = self.artifact(scope)
            try:
                body = json.loads(Path(report_path).read_text())
            except (ValueError, OSError) as exc:
                raise EngineError('Review report must be structured JSON') from exc
            expected = dict(reviewer=reviewer, categories=categories, tasks=ids, findings=findings,
                            verdict='BLOCKED' if findings else 'CLEAN', artifact=artifact, final=bool(final))
            if not isinstance(body, dict) or any(body.get(k) != v for k, v in expected.items()):
                raise EngineError('Review report metadata, verdict or artifact does not match')
            if not isinstance(body.get('summary'), str) or not body['summary'].strip():
                raise EngineError('Review needs a nonempty semantic summary')
            evidence = self._snapshot(report_path, 'review')
            receipt = dict(id=uuid.uuid4().hex, reviewer=reviewer, categories=categories,
                           tasks=ids, final=bool(final), findings=findings, artifact=artifact, scope=scope,
                           action='review', **evidence)
            state['reviews'].append(receipt)
            return copy.deepcopy(receipt)

    def _review_verdicts(self, state, cache, task_id=None, final=False):
        """Newest relevant verdict wins; altered evidence cannot restore an older verdict."""
        verdicts = {}
        since = state['tasks'][task_id].get('review_since', 0) if task_id is not None else 0
        for review in state['reviews'][since:]:
            if task_id is not None and task_id not in review['tasks']:
                continue
            if final and (not review['final'] or not self._pre_release_ids(state) <= set(review['tasks'])):
                continue
            # Each receipt is compared against the artifact recomputed with its own stored scope.
            # A stale newest receipt leaves its categories without a current verdict (O19).
            current = review['artifact'] == self._artifact_cached(cache, review.get('scope'))
            for category in review['categories']:
                verdicts[category] = (review, current)
        # A stale non-CLEAN newest receipt in any category voids every verdict until re-review (O22).
        if any(not current and review['findings'] for review, current in verdicts.values()):
            return {}
        verdicts = {category: review for category, (review, current) in verdicts.items() if current}
        if any(not self._intact(review) for review in verdicts.values()):
            kind = 'final' if final else 'task'
            raise EngineError('Current ' + kind + ' review evidence is missing or altered')
        return verdicts

    def accept(self, actor, lease, task_id):
        with self._state() as state:
            self._lease(state, actor, lease)
            task = state['tasks'].get(task_id)
            if not task or task['state'] != 'reported':
                raise EngineError('Task has no reported result')
            verdicts = self._review_verdicts(state, {}, task_id=task_id)
            if any(r['findings'] for r in verdicts.values()):
                raise EngineError('Task has current review findings')
            if task.get('repaired_by') and state['tasks'][task['repaired_by']]['state'] != 'accepted':
                raise EngineError('Task repair must be accepted first')
            if (task['role'] == 'builder' or task.get('review_required', False)) and not verdicts:
                raise EngineError('Task needs current independent review')
            if not (task['role'] == 'builder' or task.get('review_required', False)) and task['report_artifact'] != self.artifact(self._scope_of(state, [task_id])):
                raise EngineError('Reported artifact is stale')
            task['state'] = 'accepted'

    def run_secret_scan(self, actor, lease):
        return self.run_gate(actor, lease, 'secret-scan', self.policy['secret_scan'].get('argv', []))

    def run_gate(self, actor, lease, name, argv):
        unavailable = name == 'secret-scan' and argv == [] and not self.policy['secret_scan'].get('argv')
        if unavailable and self.policy['secret_scan'].get('required'):
            raise EngineError('Required secret scanner is unavailable')
        if not isinstance(name, str) or not name.strip():
            raise EngineError('Gate needs a name')
        if not unavailable and (not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or '\0' in a for a in argv)):
            raise EngineError('Gate needs an argv list')
        decision = classify_command(shlex.join(argv)) if not unavailable else None
        if decision is not None and decision.action != 'allow':
            raise EngineError('Gate command forbidden: ' + decision.reason)
        with self._state(False) as state:
            self._lease(state, actor, lease)
        before = self.artifact()
        log = self.state_dir / ('gate-' + uuid.uuid4().hex + '.log')
        with log.open('xb') as out:
            try:
                if unavailable:
                    out.write(b'Optional secret scanner unavailable: no command configured\n')
                    code = 126
                else:
                    process = subprocess.Popen(argv, cwd=self.repo, stdout=out, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    try:
                        code = process.wait(timeout=self.policy['gate_timeout_seconds'])
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
            except subprocess.TimeoutExpired:
                out.write(b'Gate timed out\n')
                code = 124
            except OSError as exc:
                out.write(str(exc).encode())
                code = 127
            out.flush()
            os.fsync(out.fileno())
        after = self.artifact()
        receipt = dict(id=uuid.uuid4().hex, name=name, argv=argv, exit_code=code,
                       artifact=before, after=after, action='gate', path=str(log),
                       sha256=_hash(log.read_bytes()), passed=code == 0 and before == after)
        with self._state() as state:
            self._lease(state, actor, lease)
            state['gates'].append(receipt)
        return receipt

    def _release_evidence(self, state, remote, target, action, argv=None):
        release = self.policy['release']
        if (action != 'release' or not release.get('enabled') or not release.get('authorization')
                or not release.get('argv') or release.get('remote') != remote or release.get('target') != target):
            raise EngineError('Release is disabled or target is unauthorized')
        decision = classify_command(shlex.join(release['argv']))
        if decision.action == 'deny':
            raise EngineError('Forbidden release command: ' + decision.reason)
        if decision.category == 'gitpush':
            command = release['argv'][0]
            if '/' in command and not Path(command).is_absolute():
                command = str(self.repo / command)
            executable, engine_git = shutil.which(command), shutil.which('git')
            if (not executable or not engine_git or Path(executable).resolve() != Path(engine_git).resolve()
                    or len(release['argv']) != 4 or release['argv'][1:2] != ['push']):
                raise EngineError('Known Git release needs exactly engine Git, push, remote and refspec')
        if decision.category == 'gitpush' and (decision.action != 'release'
                or decision.remote != remote or decision.target != target):
            raise EngineError('Git release command destination differs from authorized target')
        if self._git('status', '--porcelain=v1', '--untracked-files=all').strip():
            raise EngineError('Release needs a clean working tree')
        if argv is not None and argv != release['argv']:
            raise EngineError('Release command differs from configured command')
        artifact = self._completion_evidence(state, require_review=True, require_checks=True, for_release=True)
        if decision.category == 'gitpush':
            if not decision.source:
                raise EngineError('Git release command needs an explicit source')
            source = self._git('rev-parse', '--verify', '--end-of-options',
                               decision.source + '^{commit}').decode().strip()
            if source != artifact['head']:
                raise EngineError('Git release source differs from the reviewed HEAD')
        return artifact

    @staticmethod
    def _pre_release_ids(state):
        return {t['id'] for t in state['tasks'].values()
                if not Engine._is_release(t)}

    def _completion_evidence(self, state, require_review=False, require_checks=False, for_release=False):
        if for_release:
            releases = [t for t in state['tasks'].values() if self._is_release(t)]
            if releases and (len(releases) != 1 or releases[0]['state'] != 'running'):
                raise EngineError('The terminal release task must be running')
        required_ids = self._pre_release_ids(state) if for_release else set(state['tasks'])
        if any(state['tasks'][i]['state'] != 'accepted' for i in required_ids):
            raise EngineError('All tasks must be accepted')
        artifact = self.artifact()
        cache = {None: artifact}
        verdicts = self._review_verdicts(state, cache, final=True)
        categories = {category for category, review in verdicts.items() if not review['findings']}
        if any(review['findings'] for review in verdicts.values()):
            raise EngineError('Current final review has findings')
        for task_id in state['tasks']:
            if any(r['findings'] for r in self._review_verdicts(state, cache, task_id=task_id).values()):
                raise EngineError('Current task review has findings: ' + task_id)
        required_categories = set(self.policy['required_review_categories'])
        if (require_review or state['tasks']) and not required_categories <= categories:
            raise EngineError('Current final review coverage is incomplete')
        checks = list(self.policy['required_checks'])
        scanner = self.policy['secret_scan']
        if scanner.get('required'):
            if not scanner.get('argv'):
                raise EngineError('Required secret scanner is unavailable')
            checks.append(dict(name='secret-scan', argv=scanner['argv']))
        if require_checks and not checks:
            raise EngineError('Release needs configured required checks')
        for check in checks:
            name = check['name'] if isinstance(check, dict) else check
            expected = check.get('argv') if isinstance(check, dict) else self.policy.get('check_commands', {}).get(name)
            if not expected:
                raise EngineError('Required gate needs configured argv: ' + name)
            matching = [g for g in state['gates'] if g['name'] == name and g['argv'] == expected]
            if not matching or not matching[-1]['passed'] or matching[-1]['artifact'] != artifact or not self._intact(matching[-1]):
                raise EngineError('Required gate is missing, failed, altered or stale: ' + name)
        return artifact

    def check_completion(self, actor, lease):
        """Check completion evidence without changing the active coordinator session."""
        with self._state(False) as state:
            self._lease(state, actor, lease)
            return self._completion_evidence(state)

    def close_session(self, actor, lease):
        """Check and close under one lock, keeping completion distinct from interruption."""
        with self._state() as state:
            self._lease(state, actor, lease)
            artifact = self._completion_evidence(state)
            state['session'].update(active=False, outcome='completed')
            state['permits'] = []
            state['autonomy'] = None
            return artifact

    def release_permit(self, actor, lease, remote, target, action='release'):
        with self._state() as state:
            self._lease(state, actor, lease)
            artifact = self._release_evidence(state, remote, target, action)
            permit = dict(id=uuid.uuid4().hex, action=action, remote=remote, target=target,
                          argv=self.policy['release']['argv'], artifact=artifact, lease=lease)
            state['permits'].append(permit)
            return copy.deepcopy(permit)

    def check_release(self, remote, target, action='release', argv=None):
        with self._state(False) as state:
            session = state['session']
            if not session or not session['active']:
                raise EngineError('No active release session')
            artifact = self._release_evidence(state, remote, target, action, argv)
            for permit in reversed(state['permits']):
                if (permit['artifact'] == artifact and permit['remote'] == remote and permit['target'] == target
                        and permit['action'] == action and permit['lease'] == session['lease']):
                    return copy.deepcopy(permit)
            raise EngineError('No current explicit release permit')

    def enable_autonomy(self, actor, lease, ledger_path, max_passes, max_stalls):
        if (not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in (max_passes, max_stalls))
                or max_passes > 20 or max_stalls > 2):
            raise EngineError('Autonomy needs explicit positive caps')
        with self._state() as state:
            self._lease(state, actor, lease)
            state['autonomy'] = dict(ledger=self._snapshot(ledger_path, 'ledger'), max_passes=max_passes,
                                     max_stalls=max_stalls, passes=0, stalls=0, active=True, progress=self._progress(state))

    def autonomy_step(self, actor, lease, progress):
        if not isinstance(progress, bool):
            raise EngineError('Progress must be boolean')
        with self._state() as state:
            self._lease(state, actor, lease)
            ledger = state['autonomy']
            if not ledger or not ledger['active'] or not self._intact(ledger['ledger']):
                raise EngineError('No active intact autonomy ledger')
            ledger['passes'] += 1
            ledger['stalls'] = 0 if progress else ledger['stalls'] + 1
            ledger['active'] = ledger['passes'] < ledger['max_passes'] and ledger['stalls'] < ledger['max_stalls']
            return copy.deepcopy(ledger)

    def _progress(self, state):
        return _digest(dict(accepted=sorted(t['id'] for t in state['tasks'].values()
                                            if t['state'] == 'accepted'),
                            artifact=self.artifact(),
                            gates=sorted({(g['name'], g['sha256']) for g in state['gates']
                                          if g['passed'] and self._intact(g)})))

    def hook_stop(self):
        """Consume explicit bounded continuation; caller identifiers do not authenticate."""
        with self._state() as state:
            session = state['session']
            ledger = state['autonomy']
            if (not session or not session['active'] or not ledger or not ledger['active']
                    or not self._intact(ledger['ledger'])
                    or not any(t['state'] != 'accepted' for t in state['tasks'].values())):
                return None
            progress = self._progress(state)
            ledger['passes'] += 1
            ledger['stalls'] = 0 if ledger['progress'] != progress else ledger['stalls'] + 1
            ledger['progress'] = progress
            ledger['active'] = ledger['passes'] < ledger['max_passes'] and ledger['stalls'] < ledger['max_stalls']
            if not ledger['active']:
                return None
            return 'Continue the explicitly armed workflow within its ledger; check ready cards and evidence.'
