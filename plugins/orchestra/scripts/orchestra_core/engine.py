"""Durable workflow consistency checks, not a hostile-worker security boundary."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import math
import re
import shlex
import shutil
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

from .guards import classify_command
from . import portable
from .paths import push_url_digest


ACTIVE_MISMATCH = ('Repository or policy changed while a run is active, so a new run is refused. '
                   'End it with the version that started it, or move state.json out of the state '
                   'directory (README, Upgrade from 2.3 to 2.4)')


class EngineError(ValueError):
    pass



class StateBusy(EngineError):
    """The state lock stayed held past `lock_wait` (SPEC 5.16 item 3)."""

REVIEW_ROLES = ('code-reviewer', 'critic')
CATEGORIES = ['requirements', 'correctness', 'security', 'tests', 'architecture', 'standards', 'cleanup']
REBIND_WINDOW_SECONDS = 60
KEEP_REMOVE = ('## Keep', '## Remove')  # builder briefs carry both headings; checked at add only (SPEC 5.13)
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
ALWAYS_LENSES = ('requirements', 'correctness', 'tests', 'architecture')
INLINE_MAX_ITEMS = 5  # contract item 3: 1 to 5 items run inline, 6 or more go through a plan
SIZES = ('tiny', 'medium', 'large')
TIER_GUIDE = {'tiny': 50, 'medium': 400}  # contract item 1: changed lines per ask
CARD_SIZES = ('tiny', 'medium')  # a card's own size; a large run sizes its cards as one of these
REVIEWER_BAND = (400, 'medium', 'orchestra:code-reviewer-medium')
REVIEWER_FULL = ('full', 'orchestra:code-reviewer')
ASKS_ERROR = '--asks must be an integer, 1 or more'
SELF_REVIEW_ERROR = 'Builder report needs one SELF_REVIEW line'
PR_CONTINUATIONS = 2  # push-and-pull-request nudges in a row before the Stop loop gives up as `stalled`
WORKER_STALE_SECONDS = 3600  # A background worker silent this long is probably gone; policy.worker_stale_seconds overrides
GATE_FAILURE_LIMIT = 3  # Consecutive failures of one required gate after which an unattended run stops
LARGE_FILE_BYTES = 64 * 1024 * 1024  # Files over this are bound by size, mtime and sampled content, not read whole
SAMPLE_BYTES = 1024 * 1024
STALE_REVIEW = 'Review with findings is stale; re-review'
FINDING_ROUTES = '; add a repair card (`repair_of`) or record the finding with `finding add`'
# Keys the engine writes on a card; a task file never supplies them (repair_of only on a builder repair card).
ENGINE_TASK_KEYS = ('state', 'rev', 'seq', 'repaired_by', 'review_since', 'report', 'report_artifact', 'self_review',
                    'assignment', 'worker', 'lease', 'inline', 'held_finding', 'parked_reason', 'final_round',
                    'final_findings', 'helper_reason', 'started_at', 'dispatch_policy', 'report_sha')
DEFAULT = dict(max_workers=20, required_checks=[], gate_timeout_seconds=300,
               secret_scan=dict(required=False, argv=[]),
               release=dict(enabled=False, remote=None, target=None, argv=[]),
               sensitive_paths=['**/auth/**', '**/security/**', '**/*secret*', '**/hooks/**', '**/guard*',
                                '**/migrations/**', '.github/**'],
               standards_min_lines=200)
# Contract item 3: a run started by 2.3 binds the hash 2.3 computed: its DEFAULT and its role-to-modes digest.
DEFAULT_2_3 = dict(max_workers=20, required_checks=[], required_review_categories=CATEGORIES,
                   gate_timeout_seconds=300, secret_scan=dict(required=False, argv=[]),
                   release=dict(enabled=False, remote=None, target=None, argv=[]))
MAX_WORKTREES = 3  # Running builder cards that are not inline; policy.max_worktrees overrides
# Every key the engine reads or still loads from the older schema. `start` refuses any other, so a typo cannot turn a
# setting off in silence.
POLICY_KEYS = frozenset(DEFAULT) | frozenset(DEFAULT_2_3) | {
    'schema_version', 'max_worktrees', 'reserved_ports', 'denied_tools', 'worker_stale_seconds', 'file_budget_bytes', 'file_budget_waivers', 'check_commands',
    'release_timeout_seconds', 'guard_mode', 'release_workflows', 'parallel_waves'}
GUARD_MODES = ('minimal', 'normal', 'protect')  # `guard_mode` is read live by the hook, so it is left out of the policy hash
RUN_ID = re.compile(r'[0-9a-f]{16}')
PR_URL = re.compile(r'https?://[^/]+/([^/]+/[^/]+)/pull/([0-9]+)/?')
CONTRACT_HASH_2_3 = '7e12cdf268d85df0aac178c92f1577a3ce2ffbf686fbc536204b4677dfe3a942'


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


AUTONOMY_TEMPLATE = PACKAGE_ROOT / 'config' / 'autonomy-template.md'
AUTONOMY_FIXED = (
    '- Release: no release, permit or deploy.',
    '- Merge: no merge into the default or a protected branch; a pull request whose base is a run branch may merge.',
    '- Push: push any branch except the default, protected branches and tags; never force.',
    '- Deletion: delete only what the run created: its run branches and worktrees, and files inside a linked worktree; '
    'never tags, the default branch or other branches.',
    '- Credential entry: never enter credentials.',
    '- Engine-gated actions: nothing that needs a permit.',
)
AUTONOMY_KEEP_AWAKE = 'User step: enable keep-awake in Claude Desktop (or keep the machine awake) for an overnight run.'
CLAUDE_PROMPT_FREE_MODES = ('bypassPermissions', 'dontAsk', 'auto')
PARKABLE = ('queued', 'running', 'reported')
DISPOSITIONS = dict(finding=('rejected', 'deferred', 'inline', 'card', 'brief'),
                    out_of_scope=('inline', 'card', 'brief'))  # SPEC 5.12 item 1
TASK_STATES = ('queued', 'running', 'reported', 'repairing', 'accepted', 'parked', 'held')


def _append_progress(state_dir, text):
    """Append one entry to progress.md: one O_APPEND open and one write of the whole entry (SPEC 5.9 item 5)."""
    path = Path(state_dir) / 'progress.md'
    try:
        old = path.read_bytes()
    except OSError:
        old = b''
    gap = '' if not old.strip() else ('' if old.endswith(b'\n') else '\n')
    entry = (gap + text + ('' if text.endswith('\n') else '\n')).encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, entry)
    finally:
        os.close(fd)


def write_busy_brief(state_dir, at):
    """SPEC 5.16 item 5: a `state busy` brief appended to progress.md without touching state.json."""
    if not isinstance(at, str):
        at = datetime.fromtimestamp(at, timezone.utc).isoformat(timespec='seconds')
    _append_progress(state_dir, '\n'.join([
        '## Run brief ' + at, '', '- stop reason: state busy',
        '- Orchestra state stayed locked past the Stop hook budget; the run was left as it was. Retry or run `brief`.']))


def _fingerprint(text):
    """SHA-256 of the text with whitespace collapsed (N5), so a reworded layout keeps its triage."""
    return hashlib.sha256(' '.join(text.split()).encode()).hexdigest()


def _section(text, title):
    start = re.search(r'^##[ \t]+' + re.escape(title) + r'[ \t]*$', text, re.M)
    if not start:
        return None
    rest = text[start.end():]
    end = re.search(r'^##[ \t]', rest, re.M)
    return rest[:end.start()] if end else rest


def parse_ledger(text, now):
    """Parse the autonomy ledger (SPEC 12.2); every refusal names the field."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')  # a ledger saved with Windows line ends reads the same
    fields = {}
    for name in ('goal', 'max_passes', 'max_stalls', 'deadline'):
        match = re.search(r'^' + name + r':[ \t]*(.*?)[ \t]*$', text, re.M)
        if not match and name in ('max_passes', 'max_stalls'):
            continue  # SPEC 5.8 item 5: a 2.1 cap is optional, recorded and never enforced
        if not match or not match.group(1):
            raise EngineError('Ledger field %s is missing or empty' % name)
        if re.fullmatch(r'<.*>', match.group(1)):
            raise EngineError('Ledger field %s still holds its template placeholder' % name)
        fields[name] = match.group(1)
    for name, top in (('max_passes', 20), ('max_stalls', 2)):
        if name not in fields:
            continue
        if not re.fullmatch(r'[0-9]{1,6}', fields[name]) or not 1 <= int(fields[name]) <= top:
            raise EngineError('Ledger field %s must be an integer from 1 to %d' % (name, top))
        fields[name] = int(fields[name])
    try:
        when = datetime.fromisoformat(fields['deadline'])
    except ValueError:
        raise EngineError('Ledger field deadline must be ISO 8601 with a UTC offset') from None
    if when.utcoffset() is None:
        raise EngineError('Ledger field deadline needs a UTC offset')
    if when.timestamp() <= now:
        raise EngineError('Ledger field deadline must be in the future')
    checks, names = [], set()
    for raw in (_section(text, 'Completion checks') or '').splitlines():
        line = raw.strip()
        if line.startswith('- '):
            line = line[2:].strip()
        if not line or line.startswith('>'):
            continue
        if re.fullmatch(r'<.*>', line):
            raise EngineError('Completion checks still hold a template placeholder')
        name, colon, rest = line.partition(':')
        name = name.strip()
        try:
            argv = shlex.split(rest)
        except ValueError:
            argv = []
        if not colon or not re.fullmatch(r'[A-Za-z0-9._-]+', name) or not argv:
            raise EngineError('Completion checks line is not NAME: argv...: ' + line)
        if name in names:
            raise EngineError('Completion checks repeat the name ' + name)
        names.add(name)
        checks.append(dict(name=name, argv=argv))
    if not checks:
        raise EngineError('Completion checks need at least one NAME: argv... line')
    lines = [line.strip() for line in (_section(text, 'Approval boundaries') or '').splitlines()]
    boundaries = set(lines)
    releases = [line for line in lines if line.startswith('- Release:')]  # SPEC 5.8 item 8: exactly one, fixed or pre-authorized
    pair = re.fullmatch(r'- Release: pre-authorized ([^\s]+) ([^\s]+)', releases[0]) if len(releases) == 1 else None
    if len(releases) != 1 or (releases[0] != AUTONOMY_FIXED[0] and not pair):
        raise EngineError('Approval boundaries need exactly one Release line')
    refill = EngineError('Ledger uses the pre-2.11 Approval boundaries: copy the Merge, Push and Deletion lines '
                         'from the template, then arm again')
    if '- Push: no push to any branch.' in boundaries:  # the 2.5 line would be read as permission to push, not as a ban
        raise refill
    for line in AUTONOMY_FIXED[1:]:
        if line not in boundaries:
            if line.startswith(('- Merge:', '- Push:', '- Deletion:')) and any(
                    b.startswith(line.partition(':')[0] + ':') for b in boundaries):
                raise refill
            raise EngineError('Approval boundaries must keep the fixed line: ' + line)
    caps = {k: fields[k] for k in ('max_passes', 'max_stalls') if k in fields}
    release = dict(release=dict(remote=pair.group(1), target=pair.group(2))) if pair else {}
    return dict(goal=fields['goal'], deadline=fields['deadline'], checks=checks, pull_requests=True,
                **caps, **release)


def autonomy_preconditions(repo, home=None):
    """Read and report only (SPEC 12.5): never changes a setting, never refuses."""
    try:
        home = Path(home) if home else Path.home()
    except RuntimeError:  # No home directory: only the project settings can be read
        home = Path('/nonexistent')
    found = None
    for label, path in (('local project', Path(repo) / '.claude' / 'settings.local.json'),
                        ('project', Path(repo) / '.claude' / 'settings.json'),
                        ('user', home / '.claude' / 'settings.json')):
        try:
            value = json.loads(path.read_text())['permissions']['defaultMode']
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(value, str) and value:
            found = (value, label)
            break
    if not found:
        mode = 'unknown (no Claude settings file names permissions.defaultMode); WARNING: prompts may stall an unattended run'
    elif found[0] in CLAUDE_PROMPT_FREE_MODES:
        mode = '%s (%s settings)' % found
    else:
        mode = '%s (%s settings); WARNING: this mode can stall on prompts' % found
    return dict(permission_mode=mode, keep_awake=AUTONOMY_KEEP_AWAKE)


def ensure_remote_heads(repo, timeout=20):
    """Ask each remote for its default branch (`git remote set-head R --auto`) and record it locally. Returns
    (report, verified): one report line per remote, and {remote: default branch} for the remotes that answered.
    A recorded ref is never trusted on its own, since the remote may have changed its default since; a remote that
    cannot be reached is reported and left out of `verified`, so pull request pushes to it are refused."""
    def git(*args, limit=10):
        try:
            done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, timeout=limit,
                                  stdin=subprocess.DEVNULL, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
            return done.returncode, done.stdout.strip(), done.stderr.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, '', str(exc) or type(exc).__name__

    def head(remote):
        code, out, _ = git('symbolic-ref', '--short', '-q', 'refs/remotes/%s/HEAD' % remote)
        return out[len(remote) + 1:] if code == 0 and out.startswith(remote + '/') else None

    remotes = git('remote')[1].split()
    if not remotes:
        return 'no remote configured: pull request pushes are refused', {}
    lines, verified = [], {}
    for remote in remotes:
        before = head(remote)
        code, _, err = git('remote', 'set-head', remote, '--auto', limit=timeout)
        after = head(remote) if code == 0 else None
        if after:
            verified[remote] = after
            note = 'recorded now' if before is None else 'confirmed' if before == after else 'was %s, updated' % before
            lines.append('%s: default branch %s (%s)' % (remote, after, note))
        else:
            lines.append('%s: default branch not confirmed (%s); pull request pushes to %s are refused until it '
                         'answers and autonomy is armed again' % (remote, (err.splitlines() or ['no answer'])[-1], remote))
    return '; '.join(lines), verified


def effective_push_url(repo, remote):
    """Where `git push REMOTE` would go: `git remote get-url --push --all`, which applies pushurl, url.<base>.insteadOf
    and pushInsteadOf, one URL per line (a remote with several URLs pushes to every one). '' when Git cannot say.
    Recorded at arm and compared at every pull request push, so any later change to the remote's URL or its rewrites
    refuses the push whatever setting caused it, and a remote with more than one URL gets no pull request push."""
    try:
        done = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', '--push', '--all', remote], capture_output=True,
                              text=True, timeout=10, stdin=subprocess.DEVNULL)
        return done.stdout.strip() if done.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def _hash_file(path):
    """A digest of a file. Past LARGE_FILE_BYTES the file is not read whole (that made every command seconds long): its
    size, mtime and first and last SAMPLE_BYTES stand for it, so a same-size edit in the middle that also restores the
    mtime goes unseen."""
    info = path.stat()
    if info.st_size <= LARGE_FILE_BYTES:
        return _hash(path.read_bytes())
    digest = hashlib.sha256(('large:%d:%d' % (info.st_size, info.st_mtime_ns)).encode())
    with path.open('rb') as stream:
        digest.update(stream.read(SAMPLE_BYTES))
        stream.seek(max(0, info.st_size - SAMPLE_BYTES))
        digest.update(stream.read(SAMPLE_BYTES))
    return digest.hexdigest()


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return _hash(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


class Engine:
    def __init__(self, state_dir, repo, policy=None, clock=time.time, lock_wait=None):
        self._clock = clock
        self.lock_wait = lock_wait
        self.repo = Path(repo).resolve()
        self.state_dir = Path(state_dir).resolve()
        for protected in (self.repo, PACKAGE_ROOT.resolve()):
            if self.state_dir == protected or protected in self.state_dir.parents:
                raise EngineError('Run state must live outside the repository and immutable plugin root')
        self.policy = copy.deepcopy(DEFAULT)
        legacy = copy.deepcopy(DEFAULT_2_3)
        if policy:
            self.policy.update(copy.deepcopy(policy))
            legacy.update(copy.deepcopy(policy))
        if isinstance(self.policy['max_workers'], bool) or not isinstance(self.policy['max_workers'], int) or self.policy['max_workers'] < 1:
            raise EngineError('Invalid worker capacity')
        worktrees = self.policy.get('max_worktrees', MAX_WORKTREES)
        if isinstance(worktrees, bool) or not isinstance(worktrees, int) or worktrees < 1:
            raise EngineError('max_worktrees must be a positive integer')
        timeout = self.policy['gate_timeout_seconds']
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise EngineError('Gate timeout must be positive and finite')
        for key in ('release', 'secret_scan'):
            if not isinstance(self.policy[key], dict):
                raise EngineError('Invalid policy ' + key)
        if not isinstance(self.policy['required_checks'], list):
            raise EngineError('Invalid required checks')
        categories = self.policy.get('required_review_categories')  # an explicit override of the derived lenses
        if categories is not None and (not isinstance(categories, list) or not categories
                                       or any(not isinstance(c, str) or c not in CATEGORIES for c in categories)):
            raise EngineError('required_review_categories must be a non-empty list of known categories')
        globs = self.policy['sensitive_paths']
        if not isinstance(globs, list) or any(not isinstance(g, str) or not g for g in globs):
            raise EngineError('sensitive_paths must be a list of glob strings')
        stale = self.policy.get('worker_stale_seconds', WORKER_STALE_SECONDS)
        if isinstance(stale, bool) or not isinstance(stale, (int, float)) or not math.isfinite(stale) or stale <= 0:
            raise EngineError('worker_stale_seconds must be positive and finite')
        minimum = self.policy['standards_min_lines']
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
            raise EngineError('standards_min_lines must be a non-negative integer')
        budget = self.policy.get('file_budget_bytes')  # off when absent or null
        if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or budget < 1):
            raise EngineError('file_budget_bytes must be a positive integer')
        waivers = self.policy.get('file_budget_waivers', {})
        if not isinstance(waivers, dict) or any(not isinstance(g, str) or not g or not isinstance(r, str) or not r.strip()
                                                 for g, r in waivers.items()):
            raise EngineError('file_budget_waivers must map globs to reasons')
        if 'guard_mode' in self.policy and (not isinstance(self.policy['guard_mode'], str)
                                            or self.policy['guard_mode'] not in GUARD_MODES):
            raise EngineError('Invalid guard mode: use minimal, normal or protect')
        workflows = self.policy.get('release_workflows', [])
        if not isinstance(workflows, list) or any(not isinstance(g, str) or not g for g in workflows):
            raise EngineError('release_workflows must be a list of globs')
        if not isinstance(self.policy.get('parallel_waves', True), bool):
            raise EngineError('parallel_waves must be true or false')
        legacy.pop('guard_mode', None)
        self.modes, self.contract_hash = _contracts()
        hashed = {k: v for k, v in self.policy.items() if k != 'guard_mode'}
        self.policy_hash = _digest(dict(policy=hashed, contracts=self.contract_hash))
        self._policy_hash_2_3 = _digest(dict(policy=legacy, contracts=CONTRACT_HASH_2_3))
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

    def _sparse_hidden(self):
        """{path: index object id} of tracked paths a sparse checkout leaves out of the worktree (skip-worktree). Their
        content is not on disk, so the index's object id is what binds them: a commit that changes only a hidden path
        must still change the fingerprint."""
        hidden = set()
        for row in self._git('ls-files', '-t', '-z', '--cached').split(b'\0'):
            if row[:2] == b'S ':
                hidden.add(row[2:])
        if not hidden:
            return {}
        found = {}
        for row in self._git('ls-files', '-s', '-z').split(b'\0'):
            meta, _, name = row.partition(b'\t')
            if name in hidden:
                found[name] = b' '.join(meta.split(b' ')[:2]).decode()  # index mode and object id
        return found

    _NOISE_PARTS = frozenset(('__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.DS_Store'))

    @classmethod
    def _noise(cls, name):
        """Interpreter and OS leftovers that a command leaves behind without changing the work: never evidence."""
        parts = name.split('/')
        return name.endswith('.pyc') or any(part in cls._NOISE_PARTS for part in parts)

    def _file_entries(self, scope=None):
        """[name, value] for every tracked and untracked nonignored entry, limited to `scope` when given."""
        tracked = set(self._git('ls-files', '-z', '--cached').split(b'\0'))
        hidden = self._sparse_hidden()
        names = self._git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
        entries = []
        for raw in sorted(set(names) - {b''}):
            if scope is not None and not self._in_scope(os.fsdecode(raw), scope):
                continue
            if raw not in tracked and self._noise(os.fsdecode(raw)):
                continue
            path = self.repo / os.fsdecode(raw)
            if path.is_symlink():
                value = ['symlink', os.readlink(path)]
            elif path.is_file():
                value = ['file', path.stat().st_mode & 0o777, _hash_file(path)]
            elif path.is_dir():
                # Gitlinks need their nested HEAD, dirty state and contents bound too.
                value = ['directory', self._directory_hash(path)]
            elif raw in hidden:
                value = ['sparse', hidden[raw]]  # outside the sparse checkout: bound by the index's own object id
            else:
                continue  # Deleted (tracked, not yet staged): no content, and staging the deletion must not change the fingerprint
            entries.append([os.fsdecode(raw), value])
        return entries

    def _entry_digests(self):
        """{path: short digest} of every entry: what a final receipt keeps to tell later which files changed."""
        return {name: _digest(value)[:16] for name, value in self._file_entries()}

    def artifact(self, scope=None):
        """Whole-repo evidence, or with `scope` (repository-relative paths) evidence for those paths plus HEAD."""
        scope = sorted({Path(s).as_posix() for s in scope}) if scope else None
        # Hash every tracked and untracked nonignored entry. Index and status are also bound.
        entries = self._file_entries(scope)
        common = Path(self._git('rev-parse', '--git-common-dir').decode().strip())
        if not common.is_absolute():
            common = self.repo / common
        index = self._git('ls-files', '--stage', '-z')
        status = self._git('status', '--porcelain=v1', '-z', '--untracked-files=all')
        status = b'\0'.join(part for part in status.split(b'\0')
                            if not (part[:2] == b'??' and self._noise(os.fsdecode(part[3:]))))
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

    @staticmethod
    def _same(recorded, current):
        """Whether evidence recorded against `recorded` still holds for `current`: the artifacts are identical, HEAD, index
        and status included, so staging or committing after a review makes it stale and the review is recorded again."""
        return isinstance(recorded, dict) and isinstance(current, dict) and recorded == current

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
                entries.append([str(child.relative_to(path)), _hash_file(child)])
        return _digest(entries)

    @contextlib.contextmanager
    def _state(self, write=True, block=False, activity=True, wait=False):
        """`block` makes a read wait for the lock even when `lock_wait` is set (records that must not be dropped).
        A write bumps the `activity` counter the Stop signature reads, unless `activity` is False (the Stop hook's own
        bookkeeping, arming and harness rebinds are not progress). `wait` lets a write give up with StateBusy after
        `lock_wait` instead of blocking; other writes block."""
        if _contracts()[1] != self.contract_hash:
            raise EngineError('Role or method instructions changed; start a new run')
        with (self.state_dir / 'state.lock').open('a+') as lock:
            if (write and not wait) or block or self.lock_wait is None:
                portable.lock(lock, exclusive=write)
            else:
                end = time.monotonic() + self.lock_wait
                while True:
                    try:
                        portable.lock(lock, exclusive=write, blocking=False)
                        break
                    except OSError:
                        if time.monotonic() >= end:
                            raise StateBusy('Orchestra state is busy; retry') from None
                        time.sleep(0.05)
            if self.state_path.exists():
                try:
                    state = json.loads(self.state_path.read_text())
                    self._validate_state(state)
                except (ValueError, TypeError, KeyError, OSError) as exc:
                    raise EngineError('Malformed run state: ' + str(exc)) from exc
                if state['repo'] != str(self.repo) or not self.binds(state):
                    session = state.get('session')
                    if session is None or (isinstance(session, dict) and session.get('active') is False):
                        raise EngineError('Repository or policy changed; run `start --new-run`')
                    raise EngineError(ACTIVE_MISMATCH)
                state['policy'] = self.policy_hash  # a 2.3 binding is rebound on the next write
            else:
                state = dict(version=1, repo=str(self.repo), policy=self.policy_hash,
                             session=None, tasks={}, reviews=[], gates=[], permits=[], autonomy=None)
            try:
                yield state
            except (KeyError, TypeError, AttributeError, IndexError) as exc:
                raise EngineError('Malformed run state or request: ' + str(exc)) from exc
            if write:
                if activity:
                    state['activity'] = state.get('activity', 0) + 1
                fd, name = tempfile.mkstemp(dir=self.state_dir, prefix='.state-')
                try:
                    with os.fdopen(fd, 'w') as out:
                        json.dump(state, out, sort_keys=True, indent=2)
                        out.flush()
                        os.fsync(out.fileno())
                    os.replace(name, self.state_path)
                    if not portable.IS_WINDOWS:
                        directory = os.open(self.state_dir, os.O_RDONLY)
                        try:
                            os.fsync(directory)
                        finally:
                            os.close(directory)
                finally:
                    if os.path.exists(name):
                        os.unlink(name)

    def binds(self, state):
        """The state's policy hash is this engine's, or the one 2.3 computed for the same policy on a state with no
        `items` or `size` (contract item 3). Any other policy or roles change refuses."""
        session = state.get('session')
        return state.get('policy') == self.policy_hash or (
            state.get('policy') == self._policy_hash_2_3
            and not (isinstance(session, dict) and ('items' in session or 'size' in session)))

    @staticmethod
    def _route_for(items):
        return 'inline' if items <= INLINE_MAX_ITEMS else 'workflow'

    @classmethod
    def _validate_state(cls, state):
        if not isinstance(state, dict) or state.get('version') != 1:
            raise EngineError('Unsupported run state schema')
        for key, kind in [('repo', str), ('policy', str), ('tasks', dict),
                          ('reviews', list), ('gates', list), ('permits', list)]:
            if not isinstance(state.get(key), kind):
                raise EngineError('Invalid run state ' + key)
        if 'activity' in state and (type(state['activity']) is not int or state['activity'] < 0):
            raise EngineError('Invalid run state activity')
        brief = state.get('last_brief')
        if brief is not None and (not isinstance(brief, dict)
                                  or any(not isinstance(brief.get(k), str) for k in ('reason', 'at', 'text', 'path'))):
            raise EngineError('Invalid last_brief')
        for key in ('session', 'autonomy'):
            if key not in state or (state[key] is not None and not isinstance(state[key], dict)):
                raise EngineError('Invalid run state ' + key)
        auto = state['autonomy']
        if auto is not None:
            release = auto.get('release')
            if (('release' in auto and (not isinstance(release, dict) or any(
                        not isinstance(release.get(k), str) or not release[k] for k in ('remote', 'target'))))):
                raise EngineError('Invalid autonomy state')
            ints = ('passes', 'stalls', 'armed_gates', 'armed_reviews')
            if (not isinstance(auto.get('active'), bool)
                    or any(k in auto and (isinstance(auto[k], bool) or not isinstance(auto[k], int))
                           for k in ('max_passes', 'max_stalls')) or ('report' in auto and not isinstance(auto['report'], dict))
                    or ('pull_requests' in auto and not isinstance(auto['pull_requests'], bool))
                    or any(name in auto and (not isinstance(auto[name], dict) or any(
                        not isinstance(k, str) or not isinstance(v, str) or not k or not v
                        for k, v in auto[name].items())) for name in ('remote_defaults', 'remote_push_urls'))
                    or (auto['active'] and (any(isinstance(auto.get(k), bool) or not isinstance(auto.get(k), int) for k in ints)
                                            or any(not isinstance(auto.get(k), str) for k in ('goal', 'deadline'))
                                            or any(not isinstance(auto.get(k), list) for k in ('checks', 'accepted'))
                                            or not isinstance(auto.get('ledger'), dict)))):
                raise EngineError('Invalid autonomy state')
        session = state['session']
        if session is not None and (not isinstance(session.get('active'), bool)
                or any(not isinstance(session.get(k), str) or not session[k] for k in ('actor', 'lease'))):
            raise EngineError('Invalid session state')
        if session is not None:
            bound = session.get('harness_session')
            if 'harness_session' in session and (not isinstance(bound, str) or not bound):
                raise EngineError('Invalid harness session')
            if 'size' in session or 'asks' in session or 'owner_request' in session:
                log = session.get('route_log', [])
                if ('items' in session or session.get('size') not in SIZES or not cls._asks_ok(session.get('asks'))
                        or not isinstance(session.get('owner_request'), bool) or not isinstance(log, list)
                        or any(not isinstance(e, dict) or e.get('size') not in SIZES or not cls._asks_ok(e.get('asks'))
                               or not isinstance(e.get('reason'), str) or not isinstance(e.get('at'), str) for e in log)):
                    raise EngineError('Invalid session size')
            if 'items' in session:
                if (type(session['items']) is not int or session['items'] < 1
                        or session.get('route') != cls._route_for(session['items'])
                        or not isinstance(session.get('route_log', []), list)
                        or any(not isinstance(e, dict) or type(e.get('items')) is not int
                               or not isinstance(e.get('reason'), str) or not isinstance(e.get('at'), str)
                               for e in session.get('route_log', []))):
                    raise EngineError('Invalid session route')
            if 'base' in session and (not isinstance(session['base'], str) or not session['base']):
                raise EngineError('Invalid session base')
            baseline = session.get('baseline')
            if 'baseline' in session and (not isinstance(baseline, dict) or any(
                    not isinstance(k, str) or not isinstance(v, str) for k, v in baseline.items())):
                raise EngineError('Invalid session baseline')
            lines = session.get('baseline_lines')
            if 'baseline_lines' in session and (not isinstance(lines, dict) or any(
                    not isinstance(k, str) or type(v) is not int or v < 0 for k, v in lines.items())):
                raise EngineError('Invalid session baseline')
            pending = session.get('pending_rebind')
            if 'pending_rebind' in session and (not isinstance(pending, dict) or not isinstance(pending.get('from'), str)
                    or isinstance(pending.get('at'), bool) or not isinstance(pending.get('at'), (int, float))):
                raise EngineError('Invalid pending rebind')
        for name, task in state['tasks'].items():
            if not isinstance(task, dict) or task.get('id') != name or task.get('state') not in TASK_STATES:
                raise EngineError('Invalid task state')
            for key in ('role', 'mode'):
                if not isinstance(task.get(key), str):
                    raise EngineError('Invalid task ' + key)
            for key in ('inputs', 'acceptance', 'files', 'resources', 'dependencies'):
                if not isinstance(task.get(key), list) or any(not isinstance(v, str) or not v.strip() for v in task[key]):
                    raise EngineError('Invalid task ' + key)
            if any(dep not in state['tasks'] for dep in task['dependencies']):
                raise EngineError('Invalid stored dependency')
            if 'final_round' in task and (type(task['final_round']) is not int or task['final_round'] < 1):
                raise EngineError('Invalid task final_round')
            if 'final_findings' in task and (not isinstance(task['final_findings'], list)
                                             or any(not isinstance(f, str) or not f.strip() for f in task['final_findings'])):
                raise EngineError('Invalid task final_findings')
            if 'held_finding' in task and (not isinstance(task['held_finding'], str) or not task['held_finding'].strip()):
                raise EngineError('Invalid task held_finding')
            if 'helper_reason' in task and (not isinstance(task['helper_reason'], str) or not task['helper_reason'].strip()):
                raise EngineError('Invalid task helper_reason')
            if 'dispatch_policy' in task and not isinstance(task['dispatch_policy'], str):
                raise EngineError('Invalid task dispatch_policy')
            if 'report_sha' in task and not isinstance(task['report_sha'], str):
                raise EngineError('Invalid task report_sha')
            if 'size' in task and task['size'] not in CARD_SIZES:
                raise EngineError('Invalid task size')
            if 'self_review' in task and not cls._self_review_ok(task['self_review']):
                raise EngineError('Invalid task self_review')
            for key in ('repair_of', 'repaired_by'):
                if task.get(key) and (not isinstance(task[key], str) or task[key] not in state['tasks']):
                    raise EngineError('Invalid task ' + key)
            if 'review_since' in task and (type(task['review_since']) is not int or task['review_since'] < 0):
                raise EngineError('Invalid task review_since')
        for task in state['tasks'].values():  # a hand-edited cycle fails here instead of hanging a walk
            cls._walk(state['tasks'], task, 'repair_of')
            cls._walk(state['tasks'], task, 'repaired_by')
        prs = state.get('pull_requests', [])
        if not isinstance(prs, list) or any(
                not (isinstance(u, str) and u) and not (isinstance(u, dict) and isinstance(u.get('url'), str) and u['url'])
                for u in prs):
            raise EngineError('Invalid pull_requests state')
        if 'run_id' in state and not (isinstance(state['run_id'], str) and RUN_ID.fullmatch(state['run_id'])):
            raise EngineError('Invalid run state run_id')
        history = state.get('approval_history', [])
        if ('approval' in state and not isinstance(state['approval'], dict)) or not isinstance(history, list) or any(
                not isinstance(h, dict) for h in history):
            raise EngineError('Invalid run state approval')
        for key in ('local_branches_at_arm', 'remote_branches_at_arm'):
            names = (auto or {}).get(key, [])
            if not isinstance(names, list) or any(not isinstance(n, str) or not n for n in names):
                raise EngineError('Invalid autonomy state')
        findings = state.get('findings', [])
        if not isinstance(findings, list) or any(
                not isinstance(f, dict) or any(not isinstance(f.get(k), str) for k in ('id', 'fingerprint', 'text', 'reason', 'at'))
                or f.get('disposition') not in DISPOSITIONS['finding'] or not isinstance(f.get('source'), dict)
                for f in findings):
            raise EngineError('Invalid findings state')
        for review in state['reviews']:
            for key in ('out_of_scope', 'gate_receipts'):
                if key in review and (not isinstance(review[key], list) or any(not isinstance(v, str) for v in review[key])):
                    raise EngineError('Invalid reviews state')
            if 'source_sha256' in review and not isinstance(review['source_sha256'], str):
                raise EngineError('Invalid reviews state')
            if 'entries' in review and (not isinstance(review['entries'], dict)
                                        or any(not isinstance(k, str) or not isinstance(v, str) for k, v in review['entries'].items())):
                raise EngineError('Invalid reviews state')
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

    def _check_keep_remove(self, task):
        brief = Path(task['brief'])
        if not brief.is_absolute():
            brief = self.repo / brief
        text = brief.read_text(errors='replace')
        for heading in KEEP_REMOVE:
            if not re.search(r'^' + re.escape(heading) + r'[ \t]*$', text, re.M):
                raise EngineError('Builder brief needs the heading ' + heading)

    @staticmethod
    def _redact_leases(value):
        if isinstance(value, dict):
            return {k: Engine._redact_leases(v) for k, v in value.items() if k != 'lease'}
        if isinstance(value, list):
            return [Engine._redact_leases(v) for v in value]
        return value

    def status(self, lenses=False):
        """The run state without any lease: the board and `where` never see one (SPEC 11.2). `lenses` adds
        `required_lenses`, which reads the diff; the hooks never ask for it."""
        with self._state(False) as state:
            result = self._redact_leases(copy.deepcopy(state))
            if lenses:
                result['required_lenses'] = self._required_lenses(state)
            return result

    def current_gate_ids(self):
        """Ids of the passed gate receipts for the current whole-repository artifact; [] when there are none."""
        with self._state(False) as state:
            gates = [g for g in state['gates'] if g['passed']]
        if not gates:
            return []
        artifact = self.artifact()
        return [g['id'] for g in gates if self._same(g['artifact'], artifact) and self._intact(g)]

    @staticmethod
    def _glob_regex(glob):
        out, i = [], 0
        while i < len(glob):
            if glob.startswith('**/', i):
                out.append('(?:.*/)?')
                i += 3
            elif glob.startswith('/**', i) and i + 3 == len(glob):
                out.append('/.*')
                i += 3
            elif glob.startswith('**', i):
                out.append('.*')
                i += 2
            elif glob[i] == '*':
                out.append('[^/]*')
                i += 1
            elif glob[i] == '?':
                out.append('[^/]')
                i += 1
            else:
                out.append(re.escape(glob[i]))
                i += 1
        return re.compile(''.join(out))

    @staticmethod
    def _count_lines(path):
        """Lines in an untracked file; a file over LARGE_FILE_BYTES is estimated from its size, never read whole."""
        size = path.stat().st_size
        if size > LARGE_FILE_BYTES:
            return size // 40
        return len(path.read_bytes().splitlines())

    def _line_counts(self, base):
        """{path: changed lines} from `base` to the working tree: tracked files by numstat, untracked files by length."""
        counts = {}
        for row in self._git('diff', '--numstat', '-z', '--no-renames', base, '--').split(b'\0'):
            if row:
                added, deleted, name = row.decode(errors='replace').split('\t', 2)
                counts[name] = (int(added) + int(deleted)) if added.isdigit() and deleted.isdigit() else 0
        for row in self._git('diff', '--cached', '--numstat', '-z', '--no-renames', base, '--').split(b'\0'):
            if row:  # work that exists only in the index (staged, worktree put back) is still work
                added, deleted, name = row.decode(errors='replace').split('\t', 2)
                staged = (int(added) + int(deleted)) if added.isdigit() and deleted.isdigit() else 0
                counts[name] = max(counts.get(name, 0), staged)  # the larger of the index and worktree changes: neither masks the other
        for raw in self._git('ls-files', '-z', '--others', '--exclude-standard').split(b'\0'):
            if raw and not self._noise(os.fsdecode(raw)):
                path = self.repo / os.fsdecode(raw)
                counts[os.fsdecode(raw)] = self._count_lines(path) if path.is_file() and not path.is_symlink() else 0
        return counts

    def _baseline_view(self, names):
        """{path: 'worktree digest|index object id'} for `names`: both halves, so work staged but unlike the worktree
        (`MM`), and the run resetting the index, are visible. A path in neither is 'missing|none'."""
        digests = self._entry_digests()
        index = {}
        for row in self._git('ls-files', '-s', '-z').split(b'\0'):
            meta, _, name = row.partition(b'\t')
            if meta:
                index[os.fsdecode(name)] = b' '.join(meta.split(b' ')[:2]).decode()  # index mode and object id
        return {name: '%s|%s' % (digests.get(name, 'missing'), index.get(name, 'none')) for name in names}

    def _dirty_baseline(self):
        """(digests, line counts) of the work already in the tree when a run starts: modified tracked files, untracked
        files and anything staged. The run's size and review lenses count only what it changes after."""
        counts = self._line_counts('HEAD')
        staged = {os.fsdecode(r) for r in self._git('diff', '--cached', '--name-only', '-z', '--no-renames', 'HEAD', '--')
                  .split(b'\0') if r}
        names = sorted(set(counts) | staged)
        return self._baseline_view(names), {name: counts.get(name, 0) for name in names}

    def _changed(self, base, baseline=None, baseline_lines=None):
        """(paths, changed line count) from the run's base commit to the working tree, untracked files included. A path
        whose content still equals the `baseline` taken at the start is not the run's work, and a path already dirty then
        is charged only for the lines added since (`baseline_lines`)."""
        view = self._baseline_view(list(baseline)) if baseline else {}

        def inherited(name):
            return bool(baseline) and name in baseline and baseline[name] == view.get(name)

        paths, lines, counts = set(), 0, self._line_counts(base)
        for name, count in counts.items():
            if inherited(name):
                continue
            paths.add(name)
            # The distance from the baseline's own count: appending to pre-run work charges the new lines, reverting it
            # charges the lines taken out. A same-size rewrite of pre-run work is under-counted; its path still counts.
            lines += abs(count - (baseline_lines or {}).get(name, 0))
        for name in (baseline or {}):
            if not inherited(name):  # the run deleted, restored or rewrote work that was already in the tree
                paths.add(name)
                if name not in counts:
                    lines += (baseline_lines or {}).get(name, 0)  # fully reverted or deleted
        return sorted(paths), lines

    def _run_changed(self, state):
        """The run's own changes: from its base commit, less the dirty tree it started with. None when it has no base."""
        session = state['session'] or {}
        base = session.get('base')
        return None if base is None else self._changed(base, session.get('baseline'), session.get('baseline_lines'))

    def prepr(self):
        """Contract item 7: the pre-PR size check and reviewer choice. Read-only, no lease."""
        with self._state(False) as state:
            session = state['session'] or {}
            base = session.get('base')
            lenses = self._required_lenses(state)
            changed = self._run_changed(state)
            lines = changed[1] if changed is not None else None
            file_budget = self._file_budget(base, changed[0]) if changed is not None else None
        size, asks = session.get('size'), session.get('asks')
        budget = TIER_GUIDE[size] * asks if size in TIER_GUIDE else None
        over = budget is not None and lines is not None and lines > budget
        bound, *band = REVIEWER_BAND
        reviewer, agent = band if lines is not None and lines <= bound else REVIEWER_FULL
        warning = ('Size warning: declared %s with %d ask(s) budgets %d changed lines; the diff has %d. Run route --size TIER '
                   '--reason TEXT if the work grew.' % (size, asks, budget, lines)) if over else None
        return dict(base=base, changed_lines=lines, size=size, asks=asks, budget=budget, over_budget=over,
                    reviewer=reviewer, agent=agent, lenses=lenses, warning=warning, file_budget=file_budget)

    def _file_budget(self, base, paths):
        """Policy `file_budget_bytes`: the run's changed text files now over the budget and larger than at `base` (a
        renamed file compares with its old path), and the waived ones with their reasons. None when no budget is set.
        Sizes come from stat and `git ls-tree -l`; only the first 8000 bytes are read, to skip binary files."""
        budget = self.policy.get('file_budget_bytes')
        if budget is None:
            return None
        waivers = self.policy.get('file_budget_waivers', {})
        base_sizes = {}
        for row in self._git('ls-tree', '-r', '-l', '-z', base).split(b'\0'):
            if row:
                meta, name = row.split(b'\t', 1)
                size = meta.split()[-1]
                base_sizes[os.fsdecode(name)] = int(size) if size.isdigit() else 0
        renamed = {}
        fields = self._git('diff', '-z', '--name-status', '-M', base, '--').split(b'\0')
        for i, field in enumerate(fields):
            if field.startswith(b'R') and i + 2 < len(fields):
                renamed[os.fsdecode(fields[i + 2])] = os.fsdecode(fields[i + 1])
        grew, waived = [], []
        for name in paths:
            path = self.repo / name
            if path.is_symlink() or not path.is_file():
                continue  # deleted, a directory or a link
            size = path.stat().st_size
            was = base_sizes.get(renamed.get(name, name), 0)
            if size <= budget or size <= was:
                continue
            with path.open('rb') as handle:
                if b'\0' in handle.read(8000):
                    continue  # binary, as git judges it
            reason = next((r for g, r in waivers.items() if self._glob_regex(g).fullmatch(name)), None)
            if reason is not None:
                waived.append(dict(path=name, reason=reason))
            else:
                grew.append(dict(path=name, base_bytes=was, bytes=size))
        return dict(bytes=budget, grew=grew, waived=waived)

    def _required_lenses(self, state):
        """Contract item 6: the review categories completion needs. An explicit policy list overrides the derived set;
        a run with no stored base (made by 2.3) needs every category."""
        explicit = self.policy.get('required_review_categories')
        if explicit is not None:
            return list(explicit)
        base = (state['session'] or {}).get('base')
        if base is None:
            return list(CATEGORIES)
        paths, lines = self._run_changed(state)
        wanted = set(ALWAYS_LENSES)
        if any(self._glob_regex(g).fullmatch(p) for g in self.policy['sensitive_paths'] for p in paths):
            wanted.add('security')
        if lines > self.policy['standards_min_lines']:
            wanted.update(('standards', 'cleanup'))
        return [c for c in CATEGORIES if c in wanted]

    @staticmethod
    def _lease(state, actor, lease):
        session = state['session']
        if not session or not session['active'] or session['actor'] != actor or session['lease'] != lease:
            raise EngineError('Invalid or interrupted coordinator lease. If this session lost its lease, take it back with '
                              '`start --recover --harness-session ID` (the id is in the SessionStart context)')

    def validate_lease(self, actor, lease):
        """Check coordinator consistency; caller identifiers are not authentication."""
        with self._state(False) as state:
            self._lease(state, actor, lease)

    @staticmethod
    def _asks_ok(asks):
        return type(asks) is int and asks >= 1

    def _check_policy_keys(self):
        unknown = sorted(set(self.policy) - POLICY_KEYS)
        if unknown:
            raise EngineError('Unknown policy key: ' + ', '.join(unknown))

    def _check_start(self, size, asks, owner_request):
        """Contract item 2: what a new run must state. The CLI runs it before archiving an ended run."""
        self._check_policy_keys()
        if size is None:
            raise EngineError('A new run needs --size tiny, medium or large')
        if size not in SIZES:
            raise EngineError('Size must be tiny, medium or large')
        if asks is not None and not self._asks_ok(asks):
            raise EngineError(ASKS_ERROR)
        if size == 'large' and not owner_request:
            raise EngineError('A new run starts at tiny or medium; escalate with route --size large --reason TEXT, '
                              'or pass --owner-request when the owner asked for a map')

    @staticmethod
    def _check_items(items):
        if isinstance(items, bool) or not isinstance(items, int) or items < 1:
            raise EngineError('Items must be an integer of 1 or more')

    @staticmethod
    def _check_identity(actor, harness_session):
        """What open_session needs of the caller's names. The CLI runs it before archiving an ended run."""
        if not isinstance(actor, str) or not actor.strip():
            raise EngineError('Missing coordinator')
        if harness_session is not None and (not isinstance(harness_session, str) or not harness_session.strip()):
            raise EngineError('Invalid harness session id')

    def open_session(self, actor, harness_session=None, items=None, size=None, asks=None,
                     owner_request=False, require_size=False):
        """Open the coordinator session. A new run (no earlier session record) stores `size`, `asks`, `owner_request` and
        `base` (a 2.4 test run stores `items` and `route`); a resumed run keeps them. `require_size` is the CLI's rule that
        a new run states its size (contract items 2 and 3). Autonomy is never armed by opening: only a stopped run's
        report is kept, so a 2.5 state saved between relaunch passes is not re-armed."""
        self._check_identity(actor, harness_session)
        if items is not None:
            self._check_items(items)
            if size is not None:
                raise EngineError('Invalid session size')
        with self._state() as state:
            if state['session'] and state['session']['active']:
                raise EngineError('A coordinator session is already active. If this session lost its lease, take it back with '
                                  '`start --recover --harness-session ID`')
            lease = uuid.uuid4().hex
            prior = state['session']
            if prior is not None and items is not None:
                raise EngineError('--items applies only to a new run; use route to change it')
            if prior is not None and (size is not None or asks is not None or owner_request):
                raise EngineError('--size, --asks and --owner-request apply to a new run; use start --new-run, or route --size '
                                  'to change the tier')
            if prior is None:
                self._check_policy_keys()
            if prior is None and items is None and (require_size or size is not None or asks is not None or owner_request):
                self._check_start(size, asks, owner_request)
            state['session'] = dict(actor=actor, lease=lease, active=True)
            if prior is None:
                state['run_id'] = uuid.uuid4().hex[:16]
                state['session']['base'] = self._git('rev-parse', 'HEAD').decode().strip()
                state['session']['baseline'], state['session']['baseline_lines'] = self._dirty_baseline()
                if items is not None:
                    state['session'].update(items=items, route=self._route_for(items), route_log=[])
                elif size is not None:
                    state['session'].update(size=size, asks=1 if asks is None else asks, owner_request=bool(owner_request),
                                            route_log=[])
            else:
                for key in ('base', 'baseline', 'baseline_lines', 'items', 'route', 'route_log', 'size', 'asks', 'owner_request'):
                    if key in prior:
                        state['session'][key] = prior[key]
            if harness_session is not None:
                state['session']['harness_session'] = harness_session
            state['autonomy'] = self._kept_autonomy(state)
            self.requeued = []  # the restart receipt: cards a resumed run put back in the queue
            for task in state['tasks'].values():
                if task['state'] == 'running':
                    task['state'] = 'queued'
                    task.pop('assignment', None)
                    task.pop('started_at', None)
                    task.pop('report', None)
                    self.requeued.append(task['id'])
            state['permits'] = []
            return lease

    def set_route(self, actor, lease, items, reason, size=None, asks=None):
        """Change the tier (`size`, `asks`) of a size run, or the item count and the route it implies of a 2.4 run, and log
        why (contract items 3 and 4). Exactly one of `items` and `size`."""
        if (items is None) == (size is None):
            raise EngineError('Route needs exactly one of --size or --items')
        if size is None:
            self._check_items(items)
        elif size not in SIZES:
            raise EngineError('Size must be tiny, medium or large')
        if asks is not None and (size is None or not self._asks_ok(asks)):
            raise EngineError(ASKS_ERROR)
        if not isinstance(reason, str) or not reason.strip():
            raise EngineError('Route needs a reason')
        with self._state() as state:
            self._lease(state, actor, lease)
            session = state['session']
            at = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(timespec='seconds')
            if size is not None:
                if 'items' in session:
                    raise EngineError('This run routes by items; use route --items')
                if 'size' not in session:
                    raise EngineError('This run has no route; start a new run with --size')
                session.update(size=size, asks=session['asks'] if asks is None else asks)
                session.setdefault('route_log', []).append(dict(size=size, asks=session['asks'], reason=reason.strip(), at=at))
                return dict(size=size, asks=session['asks'])
            if 'size' in session:
                raise EngineError('This run routes by size; use route --size')
            session.update(items=items, route=self._route_for(items))
            session.setdefault('route_log', []).append(dict(items=items, reason=reason.strip(), at=at))
            return dict(items=items, route=session['route'])

    def interrupt(self, actor, lease):
        with self._state() as state:
            self._lease(state, actor, lease)
            self._end_run(state, 'interrupted')
            state['session']['active'] = False
            state['permits'] = []
            state['autonomy'] = self._kept_autonomy(state)

    def interrupt_active(self):
        """Interrupt the active session without a caller-supplied lease. Python only, for the Interrupt hook."""
        with self._state(False, block=True) as state:
            if not (state['session'] and state['session']['active']):
                return False  # Read-only unless there is a session to interrupt
        with self._state() as state:
            if not (state['session'] and state['session']['active']):
                return False
            self._end_run(state, 'interrupted')
            state['session']['active'] = False
            state['permits'] = []
            state['autonomy'] = self._kept_autonomy(state)
            return True

    def _end_run(self, state, reason):
        """Write the run brief for a session that ends. Active autonomy stops with `reason` instead, so the morning
        report exists and `start --new-run` stays refused until the owner approves or disarms. Call before the session
        is marked inactive."""
        if self._autonomy_on(state):
            self._stop_autonomy(state, reason)
        else:
            self._write_brief(state, reason)

    @staticmethod
    def _stopped_report_kept(state):
        auto = state['autonomy']
        return bool(auto and not auto['active'] and 'report' in auto)

    @staticmethod
    def _kept_autonomy(state):
        """Clear autonomy as today, except a stopped run's morning report stays until the next arm or disarm."""
        return state['autonomy'] if Engine._stopped_report_kept(state) else None

    @staticmethod
    def _bound_to(state, session_id):
        session = state['session']
        return bool(session and session['active'] and session.get('harness_session') == session_id)

    def end_harness_session(self, session_id):
        """The bound harness session ended: what interrupt does, with outcome 'ended'. Idempotent."""
        with self._state(False, block=True) as state:
            if not self._bound_to(state, session_id):
                return False  # A no-op never rewrites state.json
        with self._state() as state:
            if not self._bound_to(state, session_id):
                return False
            self._end_run(state, 'ended')
            state['session'].update(active=False, outcome='ended')
            state['session'].pop('pending_rebind', None)  # harness_session stays as a record
            state['permits'] = []
            state['autonomy'] = self._kept_autonomy(state)
            return True

    def mark_harness_rebind(self, session_id):
        """/clear or /resume: the process continues under a new id; record the pending hand-over."""
        with self._state(False) as state:
            if not self._bound_to(state, session_id):
                return False  # A no-op never rewrites state.json
        with self._state(activity=False) as state:
            if not self._bound_to(state, session_id):
                return False
            state['session']['pending_rebind'] = {'from': session_id, 'at': self._clock()}
            return True

    def apply_harness_rebind(self, session_id):
        """Bind the new id when a fresh pending rebind exists (age 0..60 s); one-shot, stale entries are removed."""
        with self._state(False) as state:
            if not state['session'] or 'pending_rebind' not in state['session']:
                return False  # Read-only unless a rebind is pending (SPEC 12.6)
        with self._state(activity=False) as state:
            session = state['session']
            pending = session.pop('pending_rebind', None) if session else None
            if pending is None:
                return False
            if not 0 <= self._clock() - pending['at'] <= REBIND_WINDOW_SECONDS:
                return False
            session['harness_session'] = session_id
            return True

    def add_task(self, actor, lease, task):
        if not isinstance(task, dict):
            raise EngineError('Task must be a JSON object')
        task = copy.deepcopy(task)
        with self._state() as state:
            self._lease(state, actor, lease)
            owned = [key for key in ENGINE_TASK_KEYS if key in task]
            if owned:
                raise EngineError('Task sets engine-owned keys: ' + ', '.join(owned))
            if 'repair_of' in task and (task.get('role'), task.get('mode')) != ('builder', 'repair'):
                raise EngineError('Only a builder repair card names repair_of')
            for key in ('id', 'role', 'mode'):
                if not isinstance(task.get(key), str) or not task[key].strip():
                    raise EngineError('Missing task ' + key)
            if task['id'] in state['tasks']:
                raise EngineError('Duplicate task')
            if 'wave' in task:
                raise EngineError('Waves are removed; use dependencies')
            self._check_contract(task)
            if task['role'] == 'designer-planner' and task['mode'] == 'plan' and state['session'].get('route') == 'inline':
                raise EngineError('Inline route: no plan card; the main session groups the work')
            session = state['session']
            if (task['role'] == 'designer-planner' and task['mode'] == 'plan' and 'size' in session
                    and session['size'] != 'large' and not session['owner_request'] and task.get('owner_request') is not True):
                raise EngineError('Plan card needs a large run or an owner request; escalate with route --size large --reason TEXT')
            if 'size' in task and task['size'] not in CARD_SIZES:
                raise EngineError('Invalid task size')
            if task['role'] == 'builder' and 'brief' in task:
                self._check_keep_remove(task)
            if self._is_release(task) and any(self._is_release(t) for t in state['tasks'].values()):
                raise EngineError('A run supports one terminal release task')
            for key in ('inputs', 'acceptance', 'files', 'resources', 'dependencies'):
                if key not in task:
                    if key in ('inputs', 'acceptance'):
                        raise EngineError('Missing task ' + key)
                    task[key] = []
                values = task[key]
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
            if task['role'] == 'code-reviewer' and not review_of:
                raise EngineError('A code-reviewer card needs review_of naming the tasks it reviews')
            if review_of and task['role'] not in REVIEW_ROLES:
                raise EngineError('Only independent review roles can use review_of')
            if set(review_of) & set(task['dependencies']):
                raise EngineError('Use review_of instead of an accepted dependency for reviewed work')
            if task['role'] == 'builder' and task['mode'] == 'repair':
                repair_of = task.get('repair_of')
                if repair_of not in state['tasks'] or state['tasks'][repair_of]['role'] != 'builder':
                    raise EngineError('Repair needs a specific earlier builder task')
                original = state['tasks'][repair_of]
                if original['state'] not in ('reported', 'accepted', 'held') or original.get('repaired_by'):
                    raise EngineError('Repair needs a reported builder without an existing repair')
                if repair_of in task['dependencies']:
                    raise EngineError('repair_of replaces an accepted dependency on the original')
                newest = self._newest_receipts(state, repair_of)  # stale findings still start a repair
                if not any(self._task_findings(r, repair_of) for r in newest.values()):
                    raise EngineError('Repair needs earlier checked coding findings')
                self._check_repair_ladder(state, original)
                final_findings = self._final_findings(state, repair_of, stale=True)
                if final_findings:
                    task['final_round'] = self._next_final_round(state)
                    task['final_findings'] = final_findings
                # Suspend the whole chain atomically. Reports and workers remain as history,
                # but none of those old assignments reserve capacity or writable files.
                original['repaired_by'] = task['id']
                for ancestor in [original, *self._walk(state['tasks'], original, 'repair_of')]:
                    ancestor['state'] = 'repairing'
                    ancestor['review_since'] = len(state['reviews'])
            # Dependencies refer only to existing immutable cards, making cycles impossible.
            task['state'] = 'queued'
            task['rev'] = '2.2'
            task['seq'] = len(state['tasks'])  # state.json is saved with sorted keys, so add order is stored
            state['tasks'][task['id']] = task

    def _check_repair_ladder(self, state, original):
        """The ladder ends in hold (SPEC 5.2 item 4): a repair of a repair, or of a card the repair-diff check
        blocked, needs the chain held or a current final receipt that blames it. 2.1 chains stay valid history."""
        if original['state'] == 'held' or self._final_blocks(state, original['id'], stale=True):
            return
        if original['mode'] == 'repair':
            raise EngineError('Escalation ends at one repair; hold the chain')
        if self._blocked_by_repair_check(state, original['id']):
            raise EngineError('Repair-diff check blocked %s; hold the chain' % original['id'])

    def _newest_receipts(self, state, task_id):
        """The newest intact receipt per category for the card, stale ones kept: a later receipt of a category, clean or
        not, supersedes an earlier one. Findings only block, so a stale finding can start a repair but approve nothing."""
        newest = {}
        for review in state['reviews'][state['tasks'][task_id].get('review_since', 0):]:
            if task_id in review['tasks'] and self._intact(review):
                for category in review['categories']:
                    newest[category] = review
        return newest

    def _final_receipts(self, state, task_id, stale=False):
        """The current final receipts for the card (with `stale`, the newest per category even when stale). Coverage of
        cards added since is not required, so a round's repairs, added together, each still see the receipts that blame
        their chains (SPEC 5.5 item 4)."""
        verdicts = self._newest_receipts(state, task_id) if stale else self._review_verdicts(state, {}, task_id=task_id)
        return [r for r in {r['id']: r for r in verdicts.values()}.values() if r['final']]

    def _final_blocks(self, state, task_id, stale=False):
        """A current final receipt with blocking findings attributed to the card."""
        return any(self._task_findings(r, task_id) for r in self._final_receipts(state, task_id, stale))

    def _final_findings(self, state, task_id, stale=False):
        """The blocking findings current final receipts attribute to the card, in order and without repeats."""
        return list(dict.fromkeys(f for r in self._final_receipts(state, task_id, stale) for f in self._task_findings(r, task_id)))

    @staticmethod
    def _next_final_round(state):
        """SPEC 5.5 item 4: 1 plus the highest `final_round` once a card of that round has reported, else that round; first is 1."""
        rounds = [t['final_round'] for t in state['tasks'].values() if 'final_round' in t]
        if not rounds:
            return 1
        top = max(rounds)
        return top + 1 if any('report' in t for t in state['tasks'].values() if t.get('final_round') == top) else top

    def _blocked_by_repair_check(self, state, task_id):
        """The card's current blocking verdict comes from a repair-diff check (`repair_check: true`, SPEC 5.2 item 2b)."""
        verdicts = self._review_verdicts(state, {}, task_id=task_id)
        return any(r.get('repair_check') and self._task_findings(r, task_id) for r in verdicts.values())

    @staticmethod
    def _pull_requests(state):
        """The recorded pull requests as objects; a 2.10 state holds bare URL strings."""
        return [dict(url=e, autonomous=False, verified_at=None) if isinstance(e, str) else e
                for e in state.get('pull_requests', [])]

    def _stamp(self):
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(timespec='seconds')

    def _gh_view(self, url):
        """The fields `gh pr view` reports for a pull request, or None when gh is missing, fails or answers oddly."""
        gh = shutil.which('gh')
        if not gh:
            return None
        try:
            done = subprocess.run([gh, 'pr', 'view', url, '--json',
                                   'number,state,baseRefName,headRefName,headRefOid,isCrossRepository'],
                                  cwd=self.repo, capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL,
                                  env=dict(os.environ, GH_PROMPT_DISABLED='1'))
            data = json.loads(done.stdout) if done.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
        ok = isinstance(data, dict) and type(data.get('number')) is int and all(
            isinstance(data.get(k), str) and data[k] for k in ('state', 'baseRefName', 'headRefName', 'headRefOid'))
        return data if ok else None

    def _local_branch(self, name):
        try:
            return self._git('rev-parse', '--verify', '-q', 'refs/heads/' + name).decode().strip()
        except EngineError:
            return None

    def _default_branch(self, auto):
        """The default branch: the one a remote reported at arm, else origin/HEAD, else a local `main` or `master`."""
        defaults = (auto or {}).get('remote_defaults') or {}
        if defaults:
            return defaults.get('origin') or sorted(defaults.values())[0]
        try:
            ref = self._git('symbolic-ref', '--short', '-q', 'refs/remotes/origin/HEAD').decode().strip()
            if ref.startswith('origin/'):
                return ref[len('origin/'):]
        except EngineError:
            pass
        for name in ('main', 'master'):
            if self._local_branch(name):
                return name
        raise EngineError('The default branch is unknown: no remote reported one and there is no main or master')

    def _run_branches(self, auto, prs):
        """Branches the run made: local branches absent at arm, and the head of every recorded pull request."""
        made = set()
        if auto and 'local_branches_at_arm' in auto:
            known = set(auto['local_branches_at_arm']) | set(auto.get('remote_branches_at_arm', []))
            made = set(self._git('for-each-ref', '--format=%(refname:short)', 'refs/heads').decode().split()) - known
        return made | {e['head_ref'] for e in prs if e.get('head_ref')}

    def record_pr(self, actor, lease, url, tasks=None):
        """Record a pull request the run opened, so the run brief asks the owner to review and merge it. `gh pr view`
        (no lock held) must find it open, from this repository, based on the default or a run branch, and headed by the
        tip of the local branch; without gh the entry is recorded unverified. A rerun refreshes the entry in place."""
        url = url.strip() if isinstance(url, str) else ''
        parts = urllib.parse.urlsplit(url) if url and not any(c.isspace() for c in url) else None
        if not parts or parts.scheme not in ('http', 'https') or not parts.hostname:
            raise EngineError('A pull request is recorded by its http(s) URL with a host')
        tasks = list(tasks or [])
        with self._state(False) as state:
            self._lease(state, actor, lease)
            unknown = [t for t in tasks if t not in state['tasks']]
            if unknown:
                raise EngineError('Unknown task: ' + ', '.join(map(str, unknown)))
            auto, seen = copy.deepcopy(state['autonomy']), self._pull_requests(state)
        match = PR_URL.fullmatch(url)
        number, repo = (int(match.group(2)), match.group(1)) if match else (None, None)
        view = self._gh_view(url)
        if view:
            number = view['number']
            if view['state'] != 'OPEN':
                raise EngineError('Pull request %s is not open (%s)' % (url, view['state']))
            if view.get('isCrossRepository') is True:
                raise EngineError('Pull request %s comes from another repository' % url)
            base, head = view['baseRefName'], view['headRefName']
            if base != self._default_branch(auto) and base not in self._run_branches(auto, seen):
                raise EngineError('Pull request base %s is neither the default branch nor a run branch' % base)
            tip = self._local_branch(head)
            if tip is None:
                raise EngineError('Pull request head %s has no local branch' % head)
            if tip != view['headRefOid']:
                raise EngineError('Pull request head %s is not the local tip of %s' % (view['headRefOid'][:12], head))
        with self._state() as state:
            self._lease(state, actor, lease)
            prs = self._pull_requests(state)
            now = self._stamp()
            entry = next((e for e in prs if e['url'] == url or (number is not None and e.get('number') == number
                                                              and e.get('repo') == repo)), None)
            if entry is None:
                entry = dict(url=url, number=number, repo=repo, head_ref=None, head_sha=None, base_ref=None,
                             autonomous=False, tasks=[], reviewed=False, verified_at=None, recorded_at=now)
                prs.append(entry)
            if view:
                sha = view['headRefOid']
                entry.update(number=number, head_ref=view['headRefName'], head_sha=sha, base_ref=view['baseRefName'],
                             verified_at=now, reviewed=any(
                                 not r['findings'] and r['artifact'].get('head') == sha and self._intact(r)
                                 for r in state['reviews']))
            entry['autonomous'] = bool(entry.get('autonomous')) or self._autonomy_on(state)
            entry['tasks'] = list(dict.fromkeys([*entry.get('tasks', []), *tasks]))
            state['pull_requests'] = prs
            return copy.deepcopy(prs)

    def base(self, task_id):
        """The branch a card's pull request should be based on (read-only, no lease). The nearest dependency cards with a
        recorded run pull request that is still open are the parents: none gives the default branch, one gives its head
        branch, two or more defer the card until they merge."""
        with self._state(False) as state:
            tasks = state['tasks']
            if task_id not in tasks:
                raise EngineError('Unknown task: ' + str(task_id))
            prs, parents, queue, seen = self._pull_requests(state), {}, list(tasks[task_id].get('dependencies', [])), set()
            while queue:
                dep = queue.pop(0)
                if dep in seen or dep not in tasks:
                    continue
                seen.add(dep)
                entry = next((e for e in prs if e.get('autonomous') and dep in e.get('tasks', [])), None)
                if entry:
                    parents[entry['url']] = entry  # the nearest one; its own parents are behind it
                else:
                    queue.extend(tasks[dep].get('dependencies', []))
            default = self._default_branch(state['autonomy'])
        open_ = []
        for entry in parents.values():
            view = self._gh_view(entry['url'])
            if view is None:
                raise EngineError('Could not read pull request %s: run gh auth status, then try again' % (entry.get('number') or entry['url']))
            if view['state'] == 'OPEN':
                open_.append((view['number'], view['headRefName']))
        if len(open_) > 1:
            raise EngineError('deferred: wait for pull request(s) %s to merge' % ', '.join(str(n) for n, _ in sorted(open_)))
        return open_[0][1] if open_ else default

    def hold(self, actor, lease, task_id, finding):
        """End the repair ladder: move the whole chain to `held` and log it (SPEC 5.2 item 2)."""
        if not isinstance(finding, str) or not finding.strip():
            raise EngineError('Hold needs a finding')
        finding = finding.strip()
        with self._state() as state:
            self._lease(state, actor, lease)
            task = state['tasks'].get(task_id)
            if not task or task['role'] != 'builder' or task['state'] != 'reported' or task.get('repaired_by'):
                raise EngineError('Hold needs a reported builder card without an existing repair')
            blocked = any(self._task_findings(r, task_id) for r in self._review_verdicts(state, {}, task_id=task_id).values())
            if not ((task['mode'] == 'repair' and blocked)
                    or (task['mode'] != 'repair' and self._blocked_by_repair_check(state, task_id))):
                raise EngineError('Hold needs a repair card with current blocking findings, '
                                  'or a card blocked by a repair-diff check')
            chain = [task_id, *(t['id'] for t in self._walk(state['tasks'], task, 'repair_of'))]
            for ident in chain:
                state['tasks'][ident]['state'] = 'held'
            task['held_finding'] = finding
            at = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(timespec='seconds')
            _append_progress(self.state_dir, '- held %s (chain %s): %s (at %s)' % (task_id, ', '.join(chain), finding, at))
            return dict(held=chain, finding=finding)

    @staticmethod
    def _is_release(task):
        return task['role'] == 'operator' and task['mode'] == 'release'

    @staticmethod
    def _paths_overlap(xs, ys):
        """The path rule of `_collides`: a path equal to, or a parent of, a path on the other side."""
        return any(x == y or x in y.parents or y in x.parents for x in map(Path, xs) for y in map(Path, ys))

    @staticmethod
    def _collides(a, b):
        if set(a['resources']) & set(b['resources']):
            return True
        return Engine._paths_overlap(a['files'], b['files'])

    @staticmethod
    def _task_findings(receipt, task_id):
        """One receipt's blocking findings for one task (SPEC 5.1 item 4). An absent key is clean."""
        per_task = receipt.get('task_findings')
        return receipt['findings'] if per_task is None else per_task.get(task_id, [])

    @staticmethod
    def _read_review(task):
        return bool(task.get('review_of')) and task['role'] in REVIEW_ROLES

    def park(self, actor, lease, task_id, reason):
        """An approval boundary: set the card aside and release its assignment, reservation and capacity (SPEC 12.4)."""
        if not isinstance(reason, str) or not reason.strip():
            raise EngineError('Parking needs a reason')
        with self._state() as state:
            self._lease(state, actor, lease)
            task = state['tasks'].get(task_id)
            if task and task.get('repaired_by'):  # O30: park the open repair card instead
                raise EngineError('A card under repair cannot be parked; park its open repair card '
                                  + self._open_repair(state, task)['id'])
            if not task or task['state'] not in PARKABLE:
                raise EngineError('Only a queued, running or reported card can be parked')
            self._set_aside(state, task, reason.strip())

    def _set_aside(self, state, task, reason):
        """Park a card: drop its assignment, reservation and report, and put its repair chain under repair again."""
        task.update(state='parked', parked_reason=reason)
        for key in ('assignment', 'worker', 'lease', 'inline', 'report', 'report_artifact', 'report_sha', 'started_at'):
            task.pop(key, None)
        for ancestor in self._walk(state['tasks'], task, 'repair_of'):  # the repair's report is dropped: its chain is under repair again
            ancestor['state'] = 'repairing'
            ancestor['review_since'] = len(state['reviews'])

    def cancel(self, actor, lease, task_id, reason):
        """Drop a card that should never run (a mis-specified or superseded one) so it stops blocking completion. Only
        a card nothing else depends on and no review or repair chain mentions can go; the drop is recorded."""
        if not isinstance(reason, str) or not reason.strip():
            raise EngineError('Cancelling needs a reason')
        with self._state() as state:
            self._lease(state, actor, lease)
            task = state['tasks'].get(task_id)
            if not task:
                raise EngineError('Unknown task: ' + str(task_id))
            if task['state'] not in ('queued', 'parked'):
                raise EngineError('Only a queued or parked card can be cancelled; park a running or reported card first')
            if task.get('repair_of') or task.get('repaired_by') or task.get('held_finding'):
                raise EngineError('A card in a repair chain cannot be cancelled')
            users = [t['id'] for t in state['tasks'].values()
                     if task_id in t.get('dependencies', []) or task_id in t.get('review_of', [])]
            if users:
                raise EngineError('Cancel or change the cards that depend on it first: ' + ', '.join(sorted(users)))
            if any(task_id in r.get('tasks', []) for r in state['reviews']):
                raise EngineError('A review covers this card, so it stays in the record')
            del state['tasks'][task_id]
            state.setdefault('cancelled', []).append(dict(id=task_id, reason=reason.strip(), at=self._clock(),
                                                          was=task['state']))

    def recover_lease(self, actor, harness_session):
        """Issue a fresh coordinator lease to the session that already owns the run. The lease is a consistency token, not
        a credential (README, Safety): when the coordinator has lost it (compaction, a restart) the same harness session,
        named by the SessionStart context, takes it back. Running cards keep their assignments."""
        self._check_identity(actor, harness_session)
        if not harness_session:
            raise EngineError('Recovering the lease needs --harness-session from the SessionStart context')
        with self._state() as state:
            session = state['session']
            if not session or not session['active']:
                raise EngineError('No active run to recover; use start')
            if session['actor'] != actor or session.get('harness_session') != harness_session:
                raise EngineError('This run belongs to another session; the owner ends it with interrupt or starts over. After a '
                                  'crash, read session.lease from %s, then `interrupt --lease LEASE`' % self.state_path)
            lease = uuid.uuid4().hex
            session['lease'] = lease
            for task in state['tasks'].values():
                if 'lease' in task:
                    task['lease'] = lease
            state['permits'] = []
            return lease

    @staticmethod
    def _walk(tasks, task, key):
        """The cards reached from `task` along `key` (repair_of or repaired_by), nearest first. A cycle refuses."""
        seen, chain = {task['id']}, []
        while task.get(key):
            task = tasks[task[key]]
            if task['id'] in seen:
                raise EngineError('Repair chain cycles at ' + task['id'])
            seen.add(task['id'])
            chain.append(task)
        return chain

    @staticmethod
    def _open_repair(state, task):
        """The last card of a repair chain: the one without `repaired_by`."""
        return ([task] + Engine._walk(state['tasks'], task, 'repaired_by'))[-1]

    def unpark(self, actor, lease, task_id):
        with self._state() as state:
            self._lease(state, actor, lease)
            task = state['tasks'].get(task_id)
            if not task or task['state'] != 'parked':
                raise EngineError('Task is not parked')
            task['state'] = 'queued'
            task.pop('parked_reason', None)

    @staticmethod
    def _reservation(task, state):
        files, resources = set(task['files']), set(task['resources'])
        for task in Engine._walk(state['tasks'], task, 'repair_of'):
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
                and all(state['tasks'][d]['state'] in ('accepted', 'held') for d in t['dependencies'])
                and all(state['tasks'][d]['state'] in ('reported', 'accepted', 'held') for d in t.get('review_of', []))
                and not any(other['id'] != t['id']
                            and self._collides(self._reservation(t, state), self._reservation(other, state))
                            and not (other['id'] in t.get('review_of', []) and other['state'] == 'reported'
                                     and not set(t['resources']) & set(other['resources']))
                            and not (self._read_review(t) and self._read_review(other)
                                     and not set(t['resources']) & set(other['resources']))
                            # Overlapping queued repairs: the lowest id starts first instead of each blocking the other.
                            and not (t.get('repair_of') and other['state'] == 'queued' and other.get('repair_of')
                                     and t['id'] < other['id'])
                            for other in occupied)]

    def _not_ready_reason(self, state, task_id):
        """Why `_ready` leaves this card out, in the order it checks."""
        tasks = state['tasks']
        task = tasks.get(task_id)
        if task is None:
            return 'unknown task %s' % task_id
        if task['state'] != 'queued':
            return '%s is %s' % (task_id, task['state'])
        running = sum(t['state'] == 'running' for t in tasks.values())
        if running >= self.policy['max_workers']:
            return '%d of %d workers running' % (running, self.policy['max_workers'])
        deps = [d for d in task['dependencies'] if tasks[d]['state'] not in ('accepted', 'held')]
        if deps:
            return 'open dependencies: ' + ', '.join(deps)
        targets = [d for d in task.get('review_of', []) if tasks[d]['state'] not in ('reported', 'accepted', 'held')]
        if targets:
            return 'review targets not reported: ' + ', '.join(targets)
        return 'its files or resources overlap a running, reported or repair card'

    def ready(self, actor, lease):
        with self._state(False) as state:
            self._lease(state, actor, lease)
            return self._ready(state)

    def dispatch(self, actor, lease, task_id, worker=None, helper=None, serial=None):
        if worker is None:
            worker = 'orchestra-' + str(task_id)
        return self._start_assignment(actor, lease, task_id, worker, inline=False, helper=helper, serial=serial)

    def start_inline(self, actor, lease, task_id, serial=None):
        return self._start_assignment(actor, lease, task_id, actor, inline=True, serial=serial)

    @staticmethod
    def _check_route(state, task, inline, helper):
        """Contract item 3. A state with no `route` (made by 2.3) is not checked."""
        session = state['session']
        if task['role'] == 'builder' and 'size' in session:
            size = task.get('size') or ('medium' if session['size'] == 'large' else session['size'])
            if size == 'tiny' and not inline and not (isinstance(helper, str) and helper.strip()):
                raise EngineError('Tiny unit: the main session does this work; pass --helper REASON to dispatch a helper')
            return
        route = session.get('route')
        if route is None or task['role'] != 'builder':
            return
        if route == 'workflow':
            if not any(t['role'] == 'designer-planner' and t['mode'] == 'plan' and t['state'] == 'accepted'
                       for t in state['tasks'].values()):
                raise EngineError('Workflow route: accept the designer-planner plan card first')
        elif not inline and not (isinstance(helper, str) and helper.strip()):
            raise EngineError('Inline route: the main session does this work; pass --helper REASON to dispatch a helper')

    def _start_checks(self, state, actor, task_id, worker, inline, helper=None, ready=None, cheap=False, contract=True):
        """Every refusal a start can make, with no change to the state. `ready` is a precomputed `_ready` list. `cheap`
        swaps the repair check, which hashes files, for a plain overlap test that can only refuse more."""
        if not isinstance(worker, str) or not worker.strip() or (worker == actor and not inline):
            raise EngineError('Worker must differ from coordinator')
        task = state['tasks'].get(task_id)
        if inline and task and task['role'] in REVIEW_ROLES:
            raise EngineError('Independent review roles need a separate worker')
        if any(t.get('worker') == worker and t['state'] in ('running', 'reported') for t in state['tasks'].values()):
            raise EngineError('Worker is already reserved')
        if task:
            self._check_route(state, task, inline, helper)
        if task and task['role'] == 'builder' and task['mode'] == 'repair':
            if cheap:
                reserved = self._reservation(task, state)['files']
                if any(t['state'] == 'reported' and t['id'] != task_id and (
                        not reserved or not self._reservation(t, state)['files']
                        or self._paths_overlap(self._reservation(t, state)['files'], reserved))
                       for t in state['tasks'].values()):
                    raise EngineError('Accept the reported cards first; a repair would make their evidence stale')
            else:
                self._check_accept_before_repair(state, task)
        if (task and task['role'] == 'builder' and not inline and sum(
                t['role'] == 'builder' and t['state'] == 'running' and not t.get('inline')
                for t in state['tasks'].values()) >= self.policy.get('max_worktrees', MAX_WORKTREES)):
            raise EngineError('Worktree cap: %d builder cards are already running; wait for one to report'
                              % self.policy.get('max_worktrees', MAX_WORKTREES))
        if task_id not in (self._ready(state) if ready is None else ready):
            raise EngineError('Task is not ready or capacity is exhausted: ' + self._not_ready_reason(state, task_id))
        if contract:
            self._check_contract(state['tasks'][task_id])

    def _mark_running(self, state, task_id, worker, inline, helper, lease):
        token = uuid.uuid4().hex
        state['tasks'][task_id].update(state='running', worker=worker, assignment=token, lease=lease, inline=inline,
                                       started_at=self._clock(), dispatch_policy=self.policy_hash)
        if isinstance(helper, str) and helper.strip():
            state['tasks'][task_id]['helper_reason'] = helper.strip()
        return token

    @staticmethod
    def _check_serial(serial):
        if serial is not None and (not isinstance(serial, str) or not serial.strip()):
            raise EngineError('--serial needs a reason')
        return serial.strip() if serial else None

    def _log_serial(self, task_ids, reason):
        _append_progress(self.state_dir, '- serial start %s: %s (at %s)' % (', '.join(task_ids), reason, self._stamp()))

    def _start_assignment(self, actor, lease, task_id, worker, inline, helper=None, serial=None):
        serial = self._check_serial(serial)
        with self._state() as state:
            self._lease(state, actor, lease)
            self._start_checks(state, actor, task_id, worker, inline, helper)
            if not serial:
                self._checkpoint(state, actor, task_id, inline)
            token = self._mark_running(state, task_id, worker, inline, helper, lease)
        if serial:
            self._log_serial([task_id], serial)  # after the state write succeeded
        return token

    def wave(self, actor, lease, task_ids, inline=None, helper=None, serial=None):
        """Start every named card in one state write; any refusal leaves the state unsaved."""
        serial = self._check_serial(serial)
        if not isinstance(task_ids, list) or not task_ids or any(not isinstance(i, str) for i in task_ids):
            raise EngineError('A wave needs one or more task ids')
        if inline is not None and inline not in task_ids:
            task_ids = [inline, *task_ids]  # `wave --inline A B C`: argparse gives A to --inline
        if len(set(task_ids)) != len(task_ids):
            raise EngineError('Duplicate task in wave')
        with self._state() as state:
            self._lease(state, actor, lease)
            tokens, workers = {}, {}
            for task_id in task_ids:
                is_inline = task_id == inline
                worker = workers[task_id] = actor if is_inline else 'orchestra-' + task_id
                self._start_checks(state, actor, task_id, worker, is_inline, helper)
                if len(task_ids) == 1 and not serial:
                    self._checkpoint(state, actor, task_id, is_inline)
                tokens[task_id] = self._mark_running(state, task_id, worker, is_inline, helper, lease)
        if serial:
            self._log_serial(task_ids, serial)
        return dict(assignments=tokens, workers=workers, inline=inline)

    def _slot_free(self, state, actor):
        return not any(t.get('worker') == actor and t['state'] in ('running', 'reported') for t in state['tasks'].values())

    def _modes(self, state, actor, task_id, ready, cheap):
        """How a card could start now: 'worker', 'inline', both or neither (a dry run of the real checks)."""
        try:
            self._check_contract(state['tasks'][task_id])
        except EngineError:
            return set()
        modes = set()
        for inline in (False, True):
            try:
                self._start_checks(state, actor, task_id, actor if inline else 'orchestra-' + task_id, inline,
                                   ready=ready, cheap=cheap, contract=False)
            except EngineError:
                continue
            modes.add('inline' if inline else 'worker')
        return modes

    @staticmethod
    def _by_seq(tasks):
        return sorted(tasks, key=lambda t: t.get('seq', 0))

    def _startable(self, state, actor, cheap=False):
        """Queued card id to the modes it could start in now, in seq order."""
        ready = self._ready(state)
        found = {}
        for task in self._by_seq(t for t in state['tasks'].values() if t['state'] == 'queued' and t['id'] in ready):
            modes = self._modes(state, actor, task['id'], ready, cheap)
            if modes:
                found[task['id']] = modes
        return found

    def _overlap(self, state, a, b):
        """The waves view of a clash: `_collides` over reservations (repair chains included) with `_ready`'s review
        exemptions, and a builder that reserves no files counting against every other builder."""
        if not set(a['resources']) & set(b['resources']) and (
                b['id'] in a.get('review_of', []) or a['id'] in b.get('review_of', [])
                or (self._read_review(a) and self._read_review(b))):
            return False
        ra, rb = self._reservation(a, state), self._reservation(b, state)
        return self._collides(ra, rb) or (a['role'] == b['role'] == 'builder' and not (ra['files'] and rb['files']))

    def _caps(self, state, free):
        """(workers, worktrees) a wave may use: what is free now, or the full policy caps."""
        full = (self.policy['max_workers'], self.policy.get('max_worktrees', MAX_WORKTREES))
        if not free:
            return full
        running = [t for t in state['tasks'].values() if t['state'] == 'running']
        return (full[0] - len(running),
                full[1] - sum(t['role'] == 'builder' and not t.get('inline') for t in running))

    def _fit(self, state, actor, chosen):
        """The card of `chosen` ((id, modes) pairs) to run inline, '' for none, or None when they cannot all start
        together: one inline slot, review roles never inline, the worker cap and the worktree cap."""
        tasks = state['tasks']
        inline_only = [i for i, m in chosen if m == {'inline'}]
        slot = self._slot_free(state, actor)
        if len(inline_only) > 1 or (inline_only and not slot):
            return None
        inline_id = inline_only[0] if inline_only else ''
        workers, worktrees = self._caps(state, True)
        if len(chosen) > workers:
            return None
        if sum(tasks[i]['role'] == 'builder' and i != inline_id for i, _ in chosen) > worktrees and not inline_id and slot:
            inline_id = next((i for i, m in chosen if 'inline' in m and tasks[i]['role'] == 'builder'), '')  # saves a worktree
        if sum(tasks[i]['role'] == 'builder' and i != inline_id for i, _ in chosen) > worktrees:
            return None
        return inline_id

    def _checkpoint(self, state, actor, task_id, inline):
        """Refuse a lone start while a disjoint card could start beside it. `parallel_waves: false` turns it off."""
        if not self.policy.get('parallel_waves', True):
            return
        chosen = [(task_id, {'inline' if inline else 'worker'})]
        for other_id, modes in self._startable(state, actor).items():
            if other_id != task_id and not any(self._overlap(state, state['tasks'][other_id], state['tasks'][i])
                                               for i, _ in chosen) and self._fit(state, actor, chosen + [(other_id, modes)]) is not None:
                chosen.append((other_id, modes))
        if len(chosen) > 1:
            inline_id = self._fit(state, actor, chosen)
            flag = '--inline %s ' % inline_id if inline_id else ''
            raise EngineError('Start the whole wave: wave %s%s (or pass --serial REASON to start %s alone)'
                              % (flag, ' '.join(i for i, _ in chosen if i != inline_id), task_id))

    def waves(self, actor='main'):
        with self._state(False) as state:
            return self._waves(state, actor)

    def _waves(self, state, actor, cheap=False):
        """The checkpoint view: overlaps, unmet prerequisites, ordered waves and the cards a start would accept now."""
        tasks = state['tasks']
        open_cards = self._by_seq(t for t in tasks.values() if t['state'] not in ('accepted', 'held', 'parked'))
        overlaps = [[a['id'], b['id']] for n, a in enumerate(open_cards) for b in open_cards[n + 1:]
                    if self._overlap(state, a, b)]
        chains, blocked, layer = {}, [], {}
        for task in open_cards:
            deps = [d for d in task['dependencies'] if tasks[d]['state'] not in ('accepted', 'held')]
            reviews = [d for d in task.get('review_of', []) if tasks[d]['state'] not in ('reported', 'accepted', 'held')]
            if deps or reviews:
                chains[task['id']] = dict(dependencies=deps, review_of=reviews)
            if task['state'] != 'queued':
                continue
            if any(tasks[d]['state'] == 'parked' or d in blocked for d in deps + reviews):
                blocked.append(task['id'])
                continue
            layer[task['id']] = max([layer[d] + 1 if d in layer else 1 for d in deps + reviews], default=0)
        waves, free = [], True
        for depth in sorted(set(layer.values())):
            pending = [t['id'] for t in open_cards if layer.get(t['id']) == depth]
            while pending:
                workers, worktrees = self._caps(state, free)
                free = False  # only the first wave is cut to what is free now
                wave, rest = [], []
                for task_id in pending:
                    if (len(wave) < workers and (tasks[task_id]['role'] != 'builder' or sum(
                            tasks[i]['role'] == 'builder' for i in wave) < worktrees)
                            and not any(self._overlap(state, tasks[task_id], tasks[i]) for i in wave)):
                        wave.append(task_id)
                    else:
                        rest.append(task_id)
                if wave:
                    waves.append(wave)
                pending = rest
        return dict(overlaps=overlaps, chains=chains, blocked=blocked, waves=waves,
                    startable_now=list(self._startable(state, actor, cheap)))

    def view(self, actor='main', session=None):
        """The lease-free board the Kanban mod reads. Built field by field from an allowlist, never from `status()`: no
        lens, file hash or diff, and no lease, assignment token or harness session id."""
        with self._state(False) as state:
            tasks, run = state['tasks'], state['session'] or {}
            plan = self._waves(state, actor, cheap=True)
            ordered = self._by_seq(tasks.values())
            cards = []
            for t in ordered:
                card = dict(id=t['id'], role=t['role'], mode=t['mode'], state=t['state'], worker=t.get('worker'),
                            inline=bool(t.get('inline')), dependencies=list(t['dependencies']),
                            deps_open=[d for d in t['dependencies'] if tasks[d]['state'] not in ('accepted', 'held')],
                            review_of=list(t.get('review_of', [])), files=list(t['files']),
                            started_at=t.get('started_at'), seq=t.get('seq'),
                            landed=self._landed(t['report_sha']) if t.get('report_sha') else None)
                if 'outcome' in t:
                    card['outcome'] = t['outcome']
                cards.append(card)
            states = ('queued', 'running', 'reported', 'repairing', 'held', 'parked', 'accepted')
            review = state['reviews'][-1] if state['reviews'] else None
            gate = state['gates'][-1] if state['gates'] else None
            head = lambda receipt: str((receipt.get('artifact') or {}).get('head', ''))[:7]
            prs = [{k: e.get(k) for k in ('url', 'number', 'base_ref', 'head_ref', 'autonomous', 'tasks', 'reviewed', 'verified_at')}
                   for e in self._pull_requests(state)]
            startable = plan['startable_now']
            return dict(
                run_id=state.get('run_id'), session=dict(active=bool(run.get('active')), size=run.get('size')),
                bound=session is not None and run.get('harness_session') == session,
                autonomy=dict(active=self._autonomy_on(state)),
                counts={s: sum(t['state'] == s for t in ordered) for s in states},
                counts_note='running includes inline cards',
                columns={s: [t['id'] for t in ordered if t['state'] == s] for s in states},
                cards=cards, startable_now=startable,
                next_wave=[i for i in plan['waves'][0] if i in startable] if plan['waves'] else [],
                latest_review=None if review is None else dict(
                    id=review['id'], verdict='BLOCKED' if review['findings'] else 'CLEAN',
                    categories=list(review['categories']), head=head(review)),
                latest_gate=None if gate is None else dict(name=gate['name'], passed=gate['passed'], head=head(gate)),
                pull_requests=prs, guard_mode=self.policy.get('guard_mode', 'minimal'))

    def _evidence_scopes(self, state, task_id):
        """The scopes a card's acceptance depends on; None means the whole repository (SPEC 5.1 item 10)."""
        task = state['tasks'][task_id]
        if not task.get('review_required', False):
            return [self._scope_of(state, [task_id])]  # accepted on its own report artifact
        receipts = {r['id']: r for r in self._review_verdicts(state, {}, task_id=task_id).values()}
        return [r.get('scope') for r in receipts.values()]

    def _check_accept_before_repair(self, state, repair):
        """A repair lands in the shared tree: refuse while an acceptable reported card's evidence overlaps it."""
        reserved = self._reservation(repair, state)['files']
        for other in state['tasks'].values():
            if other['state'] != 'reported' or self._accept_refusal(state, {}, other['id']) is not None:
                continue
            if not reserved or any(scope is None or self._paths_overlap(scope, reserved)
                                   for scope in self._evidence_scopes(state, other['id'])):
                raise EngineError('Accept %s first; a repair would make its evidence stale' % other['id'])

    @staticmethod
    def _self_review_ok(review):
        """The SELF_REVIEW shape of contract item 1: non-empty `checks` and `criteria`, each entry well typed."""
        if not isinstance(review, dict):
            return False
        checks, criteria = review.get('checks'), review.get('criteria')
        return (isinstance(checks, list) and bool(checks) and isinstance(criteria, list) and bool(criteria)
                and all(isinstance(c, dict) and isinstance(c.get('command'), str) and c['command'].strip()
                        and type(c.get('exit_code')) is int and c.get('expect', 'pass') in ('pass', 'fail') for c in checks)
                and all(isinstance(c, dict) and isinstance(c.get('criterion'), str) and c['criterion'].strip()
                        and type(c.get('met')) is bool and isinstance(c.get('evidence'), str) for c in criteria))

    @staticmethod
    def _checks_pass(checks):
        """Every check exits 0, except a red-first check (`expect: fail`): that one exits non-zero and a later check of the
        same command, with no `expect`, exits 0 (the failing run, then the passing one)."""
        for i, check in enumerate(checks):
            if check.get('expect') == 'fail':
                if check['exit_code'] == 0 or not any(
                        later['command'] == check['command'] and later.get('expect', 'pass') == 'pass' and later['exit_code'] == 0
                        for later in checks[i + 1:]):
                    return False
            elif check['exit_code'] != 0:
                return False
        return True

    @classmethod
    def _parse_self_review(cls, report):
        lines = [line for line in report.splitlines() if line.startswith('SELF_REVIEW: ')]
        if len(lines) != 1:
            raise EngineError(SELF_REVIEW_ERROR)
        try:
            review = json.loads(lines[0][len('SELF_REVIEW: '):])
        except ValueError:
            raise EngineError(SELF_REVIEW_ERROR) from None
        if not cls._self_review_ok(review):
            raise EngineError(SELF_REVIEW_ERROR)
        return review

    def report(self, worker, token, report):
        if not isinstance(report, str) or not report.strip():
            raise EngineError('Empty worker report')
        with self._state() as state:
            self._report_in(state, worker, token, report)

    def _report_in(self, state, worker, token, report):
        task = next((t for t in state['tasks'].values() if t.get('assignment') == token), None)
        replacing = bool(task) and task['state'] == 'reported'  # a repair needs a covering review, refused below
        if not task or task['worker'] != worker or not (task['state'] == 'running' or replacing):
            raise EngineError('Invalid assignment')
        covered = replacing and any(task['id'] in r.get('tasks', []) for r in state['reviews'])
        if covered:
            # The review bound the reported work and files. Only the command text of the builder's checks may be
            # corrected (F32); exit codes, criteria and the reported artifact stay as reviewed (PR4).
            def body(text):
                return [line for line in text.splitlines() if not line.startswith('SELF_REVIEW: ')]

            def results(review):
                if not isinstance(review, dict):
                    return None
                return ([(c.get('exit_code'), c.get('expect', 'pass')) for c in review.get('checks', [])],
                        review.get('criteria'))
            try:
                corrected = self._parse_self_review(report) if task['role'] == 'builder' else None
            except EngineError:
                corrected = None
            if (body(report) != body(task.get('report', ''))
                    or results(corrected) != results(task.get('self_review'))
                    or self.artifact(self._scope_of(state, [task['id']])) != task.get('report_artifact')):
                raise EngineError('A review covers this report; route a change through a repair card')
        self._lease(state, state['session']['actor'], task['lease'])
        lines = report.splitlines()
        blocked = next((line[len('BLOCKED:'):].strip() for line in lines if line.startswith('BLOCKED:')), '')
        if not blocked and lines and lines[0].startswith('STATUS: BLOCKED'):
            blocked = lines[0][len('STATUS: BLOCKED'):].strip() or 'worker reported STATUS: BLOCKED'
        if blocked and not replacing:
            # A worker that cannot do the card says so instead of faking a self-review: the card is parked with the
            # reason, and the coordinator decides (unpark with a changed card, or cancel it).
            self._set_aside(state, task, 'blocked: ' + blocked)
            return
        review = self._parse_self_review(report) if task['role'] == 'builder' else None
        if task['role'] == 'builder' and not any(
                line.startswith('ARTIFACT:') and line[len('ARTIFACT:'):].strip() for line in report.splitlines()):
            raise EngineError('Builder report needs a nonempty ARTIFACT line')
        task.update(state='reported', report=report,
                    report_artifact=self.artifact(self._scope_of(state, [task['id']])))
        task.pop('report_sha', None)
        sha = self._reported_commit(report) if task['role'] == 'builder' else None
        if sha:
            task['report_sha'] = sha
        if review is not None:
            task['self_review'] = review
        for ancestor in self._walk(state['tasks'], task, 'repair_of'):
            ancestor['state'] = 'reported'
            ancestor['report_artifact'] = self.artifact(self._scope_of(state, [ancestor['id']]))  # the repair changed its files

    def _reported_commit(self, report):
        """The commit named by the first 7 to 40 hex characters of the report's first ARTIFACT line, or None."""
        line = next((line for line in report.splitlines() if line.startswith('ARTIFACT:')), '')
        found = re.match(r'\s*([0-9a-fA-F]{7,40})\b', line[len('ARTIFACT:'):])
        if not found:
            return None
        try:
            return self._git('rev-parse', '--verify', '--quiet', found.group(1) + '^{commit}').decode().strip()
        except EngineError:
            return None

    def _landed(self, sha):
        """Whether HEAD holds a reported commit: it is an ancestor, or `git cherry` finds each of its commits applied."""
        if subprocess.run(['git', '-C', str(self.repo), 'merge-base', '--is-ancestor', sha, 'HEAD'],
                          capture_output=True).returncode == 0:
            return True
        try:
            return not any(line.startswith('+') for line in self._git('cherry', 'HEAD', sha).decode().splitlines())
        except EngineError:
            return False

    def _snapshot(self, path, kind, normalized=None):
        """Copy the file under the state directory. With `normalized` bytes the copy holds those instead, and the receipt
        keeps `source_sha256` of the original so a changed original is still noticed."""
        path = Path(path).resolve()
        if not path.is_file() or not path.read_bytes().strip():
            raise EngineError('Evidence report must be a nonempty file')
        data = path.read_bytes()
        kept = data if normalized is None else normalized
        target = self.state_dir / (kind + '-' + uuid.uuid4().hex)
        with target.open('xb') as out:
            out.write(kept)
            out.flush()
            os.fsync(out.fileno())
        evidence = dict(source=str(path), path=str(target), sha256=_hash(kept))
        if normalized is not None:
            evidence['source_sha256'] = _hash(data)
        return evidence

    @staticmethod
    def _intact(receipt):
        for key in ('path', 'source'):
            if key in receipt:
                p = Path(receipt[key])
                expected = receipt.get('source_sha256', receipt['sha256']) if key == 'source' else receipt['sha256']
                if not p.is_file() or _hash(p.read_bytes()) != expected:
                    return False
        return True

    def record_review(self, actor, lease, reviewer, report_path, categories, task_ids=None, final=False, findings=None):
        with self._state() as state:
            return self._record_review(state, actor, lease, reviewer, report_path, categories, task_ids, final, findings)

    def _record_review(self, state, actor, lease, reviewer, report_path, categories, task_ids=None, final=False, findings=None):
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
            raise EngineError('Review needs task coverage')
        if any(i not in state['tasks'] for i in ids):
            raise EngineError('Unknown reviewed task')
        if final and (len(ids) != len(set(ids)) or set(ids) not in (set(state['tasks']), self._pre_release_ids(state))):
            missing = sorted(self._pre_release_ids(state) - set(ids))
            raise EngineError('Final review must explicitly cover every task' + ('; missing: ' + ', '.join(missing) if missing else ''))
        covered = [state['tasks'][i] for i in ids]
        if any(t.get('worker') == reviewer and not self._read_review(t) for t in covered):
            raise EngineError('Worker cannot review own artifact')
        if any(t['state'] not in ('reported', 'accepted', 'held') for t in covered):
            raise EngineError('Review covers incomplete work')
        scope = None if final else self._scope_of(state, ids)
        artifact = self.artifact(scope)
        try:
            body = json.loads(Path(report_path).read_text())
        except (ValueError, OSError) as exc:
            raise EngineError('Review report must be structured JSON') from exc
        normalized = None
        if isinstance(body, dict) and isinstance(body.get('artifact'), str):
            # The string a reviewer saw: only "<HEAD sha, 7+ hex> clean". The engine's own record replaces it, so the
            # receipt binds what is on disk now; anything else is refused as a mismatch below.
            if self._saw_clean_head(state, body['artifact'], reviewer, artifact):
                body = dict(body, artifact=artifact)
                normalized = (json.dumps(body, indent=1, sort_keys=True) + '\n').encode()
        expected = dict(reviewer=reviewer, categories=categories, tasks=ids, findings=findings,
                        verdict='BLOCKED' if findings else 'CLEAN', artifact=artifact, final=bool(final))
        if not isinstance(body, dict) or any(body.get(k) != v for k, v in expected.items()):
            raise EngineError('Review report metadata, verdict or artifact does not match')
        if not isinstance(body.get('summary'), str) or not body['summary'].strip():
            raise EngineError('Review needs a nonempty semantic summary')
        task_findings = self._check_task_findings(state, body, ids, findings)
        repair_check = self._check_repair_marker(body, final)
        if not final and repair_check:
            self._check_fix_review(state, covered)
        elif not final and not any(t['role'] == 'critic' and t.get('worker') == reviewer for t in state['tasks'].values()):
            raise EngineError('Only the pre-PR review and the fix re-review are recorded')
        if not final and findings and (repair_check or any(t.get('repaired_by') for t in covered)):
            self._check_chain_tips(state, covered, task_findings)
        if final and findings and covered:
            self._check_chain_tips(state, covered, task_findings, 'final')
        cleared = self._check_cleared(state, body, final, task_findings)
        notes = self._check_issues(body, findings, covered)
        out_of_scope = self._check_out_of_scope(body, final)
        gate_receipts = self._check_gate_receipts(state, body, findings)
        evidence = self._snapshot(report_path, 'review', normalized)
        receipt = dict(id=uuid.uuid4().hex, reviewer=reviewer, categories=categories,
                       tasks=ids, final=bool(final), findings=findings, notes=notes, artifact=artifact,
                       out_of_scope=out_of_scope, gate_receipts=gate_receipts, cleared=cleared,
                       scope=scope, action='review', **evidence)
        if task_findings is not None:
            receipt['task_findings'] = task_findings
        if repair_check:
            receipt['repair_check'] = True
        if final:
            receipt['entries'] = self._entry_digests()  # lets a clean fix re-review tell which files changed since
        state['reviews'].append(receipt)
        return copy.deepcopy(receipt)

    def _saw_clean_head(self, state, text, reviewer, artifact):
        """Whether a reviewer's artifact string `<sha> clean` holds: the sha is a prefix of HEAD, nothing in the receipt's
        scope is modified, and the policy is unchanged since the reviewer's newest card was dispatched."""
        found = re.fullmatch(r'([0-9a-f]{7,40}) clean', text)
        if not found or not artifact['head'].startswith(found.group(1)) or artifact['status'] != _hash(b''):
            return False
        cards = [t for t in state['tasks'].values()
                 if t.get('worker') == reviewer and t['role'] in REVIEW_ROLES and 'started_at' in t]
        card = max(cards, key=lambda t: t['started_at'], default=None)
        return card is not None and card.get('dispatch_policy') == self.policy_hash

    def review_with_token(self, actor, lease, token, report_path):
        """Report the review card and record its final receipt in one transaction, then accept the card when every accept
        check passes. The card is the one assigned TOKEN to the receipt's reviewer; the receipt file is its report."""
        try:
            text = Path(report_path).read_text()
            body = json.loads(text)
        except (ValueError, OSError) as exc:
            raise EngineError('Review report must be structured JSON') from exc
        missing = [k for k in ('reviewer', 'categories', 'tasks', 'final', 'findings') if not isinstance(body, dict) or k not in body]
        if missing:
            raise EngineError('Review report is missing: ' + ', '.join(missing))
        with self._state() as state:
            self._lease(state, actor, lease)
            card = next((t for t in state['tasks'].values() if t.get('assignment') == token), None)
            if (not card or card['role'] not in REVIEW_ROLES or card['worker'] != body['reviewer']
                    or card['state'] not in ('running', 'reported')):
                raise EngineError('Invalid assignment')
            if body['final'] is not True:
                raise EngineError('review --token records final receipts only')
            if card['state'] == 'running':
                self._report_in(state, card['worker'], token, text)
                if card['state'] != 'reported':
                    raise EngineError('The review card did not take the report')
            receipt = self._record_review(state, actor, lease, body['reviewer'], report_path, body['categories'],
                                          body['tasks'], True, body['findings'])
            refusal = self._accept_refusal(state, {}, card['id'])
            if refusal is None:
                card['state'] = 'accepted'
            return dict(receipt=receipt, card=card['id'], accepted=refusal is None, refusal=refusal)

    def _check_task_findings(self, state, body, ids, findings):
        """Per-task findings (SPEC 5.1 item 4): covered keys only, and the ordered union equals `findings`."""
        if 'task_findings' not in body:
            return None
        per_task = body['task_findings']
        if not isinstance(per_task, dict) or any(
                not isinstance(v, list) or any(not isinstance(f, str) or not f.strip() for f in v)
                for v in per_task.values()):
            raise EngineError('Invalid task findings')
        if any(key not in ids for key in per_task):
            raise EngineError('Task findings name an uncovered task')
        if list(dict.fromkeys(f for v in per_task.values() for f in v)) != findings:
            raise EngineError('Task findings must match the review findings')
        return per_task

    @staticmethod
    def _check_repair_marker(body, final):
        """`repair_check` marks the fix re-review; only the value true, and never on the final receipt (contract item 4)."""
        if 'repair_check' not in body:
            return False
        if body['repair_check'] is not True or final:
            raise EngineError('repair_check must be true on a non-final fix re-review')
        return True

    @staticmethod
    def _check_fix_review(state, covered):
        """The fix re-review covers repair cards whose chain starts at a final-review finding, plus their ancestors."""
        repairs = [t for t in covered if t['role'] == 'builder' and t['mode'] == 'repair']
        allowed, fixes = set(), 0
        for repair in repairs:
            chain = [repair, *Engine._walk(state['tasks'], repair, 'repair_of')]
            if any(t.get('final_findings') for t in chain):
                fixes += 1
                allowed.update(t['id'] for t in chain)
        if not fixes or fixes != len(repairs) or any(t['id'] not in allowed for t in covered):
            raise EngineError('A fix re-review covers repair cards of a final-review finding and their ancestors')

    def _check_chain_tips(self, state, covered, task_findings, kind='repair-diff'):
        """Tip rule (SPEC 5.1 item 6, 5.5 item 3): a blocked repair-diff check or final receipt names chain tips, never an ancestor."""
        if task_findings is None:
            raise EngineError('Attribute %s findings to the chain tip %s' % (kind, self._open_repair(state, covered[0])['id']))
        for key, found in task_findings.items():
            if found and state['tasks'][key].get('repaired_by'):
                raise EngineError('Attribute %s findings to the chain tip %s' % (kind, self._open_repair(state, state['tasks'][key])['id']))

    def _check_cleared(self, state, body, final, task_findings):
        """SPEC 5.5 item 3: `cleared` maps a held tip to a reason, on final receipts only; a final receipt addresses every held tip."""
        cleared = body.get('cleared', {})
        if not final:
            if cleared:
                raise EngineError('Cleared entries are allowed only on final receipts')
            return {}
        held = [t['id'] for t in state['tasks'].values() if t['state'] == 'held' and not t.get('repaired_by')]
        if (not isinstance(cleared, dict)
                or any(key not in held or not isinstance(reason, str) or not reason.strip() for key, reason in cleared.items())):
            raise EngineError('Invalid cleared entries: each names a held tip with a non-empty reason')
        for tip in held:
            if tip not in cleared and not (task_findings or {}).get(tip):
                raise EngineError('Final receipt must address held tip ' + tip)
        return cleared

    @staticmethod
    def _check_out_of_scope(body, final):
        """Out-of-scope items never change the verdict and exist only on final receipts (SPEC 5.7 item 2)."""
        items = body.get('out_of_scope', [])
        if not final and items:
            raise EngineError('Out-of-scope findings are raised only at the final review')
        if not isinstance(items, list) or any(not isinstance(i, str) or not i.strip() for i in items):
            raise EngineError('Invalid out-of-scope findings')
        return items

    def _check_gate_receipts(self, state, body, findings):
        """A cited gate receipt must exist, be intact and match the current whole-repository artifact (SPEC 5.11 item 1)."""
        cited = body.get('gate_receipts', [])
        if not isinstance(cited, list) or any(not isinstance(c, str) or not c for c in cited):
            raise EngineError('Invalid gate receipts')
        current = self.artifact() if cited else None
        failed = False
        for ident in cited:
            gate = next((g for g in state['gates'] if g['id'] == ident), None)
            if gate is None:
                raise EngineError('Review cites an unknown gate receipt: ' + ident)
            if not self._intact(gate):
                raise EngineError('Review cites an altered gate receipt: ' + ident)
            if not self._same(gate['artifact'], current):
                raise EngineError('Review cites a stale gate receipt: ' + ident)
            failed = failed or not gate['passed']
        if failed and not findings:
            raise EngineError('A failed gate receipt needs a blocking finding')
        return cited

    @staticmethod
    def _check_issues(body, findings, covered):
        """Materiality (SPEC 5.6): blocking issues are the findings; note texts are returned."""
        if 'issues' not in body:
            if any('rev' in t for t in covered):
                raise EngineError('Review needs `issues`: a list of {text, severity, impact}, or [] when clean')
            return []
        issues = body['issues']
        if not isinstance(issues, list) or any(
                not isinstance(i, dict) or not isinstance(i.get('text'), str) or not i['text'].strip()
                or i.get('severity') not in ('blocking', 'note') for i in issues):
            raise EngineError('Review issues need text and a severity of blocking or note')
        if any(i['severity'] == 'blocking' and (not isinstance(i.get('impact'), str) or not i['impact'].strip())
               for i in issues):
            raise EngineError('A blocking issue needs an impact')
        if findings != [i['text'] for i in issues if i['severity'] == 'blocking']:
            raise EngineError('Review findings must equal the blocking issues in order')
        return [i['text'] for i in issues if i['severity'] == 'note']

    def _kept_current(self, state, review, cache):
        """Ids a CLEAN fix re-review resolves when a stale final review stays current for completion, else None.
        Every file changed since the final review must belong to a repair card that a later, current, CLEAN fix
        re-review covered (contract item 5)."""
        if not review['final'] or 'entries' not in review:
            return None
        ids = [r['id'] for r in state['reviews']]
        later = [r for r in state['reviews'][ids.index(review['id']) + 1:]
                 if r.get('repair_check') and not r['findings'] and self._intact(r)
                 and self._same(r['artifact'], self._artifact_cached(cache, r.get('scope')))]
        repairs = {i for r in later for i in r['tasks']
                   if state['tasks'][i]['role'] == 'builder' and state['tasks'][i]['mode'] == 'repair'}
        scope = self._scope_of(state, sorted(repairs)) if repairs else None
        if scope is None:
            return None
        if 'entries' not in cache:
            cache['entries'] = self._entry_digests()
        old, now = review['entries'], cache['entries']
        if any(old.get(name) != now.get(name) and not self._in_scope(name, scope) for name in old.keys() | now.keys()):
            return None
        if any(review['artifact'][k] != self._artifact_cached(cache, None)[k] for k in ('repo', 'identity', 'policy')):
            return None
        return {i for r in later for i in r['tasks']}

    def _review_verdicts(self, state, cache, task_id=None, final=False, keep=False, strict=False):
        """Newest relevant verdict wins; altered evidence cannot restore an older verdict. With `keep`, a stale final
        review that a CLEAN fix re-review keeps current counts as current (`cache['resolved']` records the ids).
        With `strict`, verdicts voided by a stale receipt with findings return None instead of {} (no verdicts)."""
        verdicts = {}
        since = state['tasks'][task_id].get('review_since', 0) if task_id is not None else 0
        for review in state['reviews'][since:]:
            if task_id is not None and task_id not in review['tasks']:
                continue
            if final and not review['final']:
                continue
            # Each receipt is compared against the artifact recomputed with its own stored scope.
            # A stale newest receipt leaves its categories without a current verdict (O19).
            current = self._same(review['artifact'], self._artifact_cached(cache, review.get('scope')))
            resolved = None
            if not current and keep and review['final']:
                resolved = self._kept_current(state, review, cache)
                if resolved is not None:
                    current = True
            if final and not self._pre_release_ids(state) <= set(review['tasks']) | (resolved or set()):
                continue  # a repair card the fix re-review covered counts as covered by the final review it fixed
            if resolved is not None:
                cache.setdefault('resolved', {})[review['id']] = resolved
            for category in review['categories']:
                verdicts[category] = (review, current)
        # A stale non-CLEAN newest receipt in any category voids every verdict until re-review (O22).
        # Per task, the receipt voids only when its findings for that task are non-empty (SPEC 5.1 item 4).
        if any(not current and (self._task_findings(review, task_id) if task_id is not None else review['findings'])
               for review, current in verdicts.values()):
            return None if strict else {}
        verdicts = {category: review for category, (review, current) in verdicts.items() if current}
        if any(not self._intact(review) for review in verdicts.values()):
            kind = 'final' if final else 'task'
            raise EngineError('Current ' + kind + ' review evidence is missing or altered')
        return verdicts

    def _fix_rechecked(self, state, cache, task):
        """A repair, or an ancestor under repair, that a final review blamed (current or stale) waits for a CLEAN review
        of the chain's tip repair at the current artifact: a fix re-review (`repair_check: true`) or a later final review."""
        if task['state'] == 'held':
            return True  # the chain left the repair ladder; a clean review of it accepts it
        tip, chain = task, [task['id']]
        while tip.get('repaired_by'):
            tip = state['tasks'][tip['repaired_by']]
            chain.append(tip['id'])
        chain += [t['id'] for t in self._walk(state['tasks'], tip, 'repair_of')]
        reviews = state['reviews'][task.get('review_since', 0):]
        if not any(r['final'] and any(self._task_findings(r, i) for i in chain) for r in reviews):
            return True
        # A receipt that blames another chain still clears this one: only findings for a card of this chain count.
        return any((r.get('repair_check') or r['final']) and not any(self._task_findings(r, i) for i in chain)
                   and tip['id'] in r['tasks'] and self._intact(r)
                   and self._same(r['artifact'], self._artifact_cached(cache, r.get('scope'))) for r in reviews)

    def _accept_refusal(self, state, cache, task_id):
        """Why `accept` would refuse this card now, or None when every accept check passes."""
        task = state['tasks'].get(task_id)
        if not task or task['state'] not in ('reported', 'held'):
            return 'Task has no reported result'
        verdicts = self._review_verdicts(state, cache, task_id=task_id, strict=True)
        if verdicts is None:
            return STALE_REVIEW
        if any(self._task_findings(r, task_id) for r in verdicts.values()):
            return 'Task has current review findings'
        if task.get('repaired_by') and state['tasks'][task['repaired_by']]['state'] != 'accepted':
            return 'Task repair must be accepted first'
        if (task['role'] == 'builder' and (task['mode'] == 'repair' or task.get('repaired_by'))
                and not self._fix_rechecked(state, cache, task)):
            return 'A repair needs a clean fix re-review at the current artifact before accept'
        if task['role'] == 'builder':
            review = task.get('self_review')
            if review is None:
                return SELF_REVIEW_ERROR
            if not self._checks_pass(review['checks']) or not all(c['met'] for c in review['criteria']):
                return 'Self-review has a failing check or unmet criterion'
        elif task.get('review_required', False):
            return None if verdicts else 'Task needs current independent review'
        reported, now = task['report_artifact'], self._artifact_cached(cache, self._scope_of(state, [task_id]))
        # A commit after the report moves HEAD but not the reported content, and the independent review above is current
        # on the committed tree. The report stays good only when it is unchanged outright, or when nothing is staged,
        # modified or untracked any more (within its scope): then HEAD holds exactly the reported files.
        clean = now.get('status') == _hash(b'')
        if any(reported.get(k) != now.get(k) for k in ('repo', 'identity', 'policy', 'fingerprint', 'scope')) or (
                reported != now and not clean):
            return 'Reported artifact is stale: the files in its scope changed after the report; re-report or send a repair card'
        return None

    def accept(self, actor, lease, task_id):
        with self._state() as state:
            self._lease(state, actor, lease)
            refusal = self._accept_refusal(state, {}, task_id)
            if refusal:
                raise EngineError(refusal)
            state['tasks'][task_id]['state'] = 'accepted'

    def add_finding(self, actor, lease, review_id, kind, index, disposition, reason, card=None):
        """Record the coordinator's disposition of one receipt item (SPEC 5.12). A rejection accepts no card."""
        with self._state() as state:
            self._lease(state, actor, lease)
            review = next((r for r in state['reviews'] if r['id'] == review_id), None)
            if review is None:
                raise EngineError('Unknown review: ' + str(review_id))
            if kind not in DISPOSITIONS:
                raise EngineError('Finding kind must be finding or out_of_scope')
            if disposition not in DISPOSITIONS[kind]:
                raise EngineError('Disposition for %s must be one of %s' % (kind, ', '.join(DISPOSITIONS[kind])))
            items = review['findings'] if kind == 'finding' else review.get('out_of_scope', [])
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(items):
                raise EngineError('Finding index does not name an item of that receipt')
            if not isinstance(reason, str) or not reason.strip():
                raise EngineError('Finding needs a reason')
            if card is not None and (not isinstance(card, str) or not card.strip()):
                raise EngineError('Finding card must be a nonempty id')
            entry = dict(id=uuid.uuid4().hex, fingerprint=_fingerprint(items[index]), text=items[index],
                         source=dict(review=review_id, kind=kind, index=index), disposition=disposition,
                         reason=reason, at=datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(timespec='seconds'))
            if card is not None:
                entry['card'] = card
            state.setdefault('findings', []).append(entry)
            return copy.deepcopy(entry)

    def list_findings(self, for_brief=False):
        """Lease-free read of the ledger; for_brief renders the block reviewer briefs carry."""
        with self._state(False) as state:
            entries = copy.deepcopy(state.get('findings', []))
        if not for_brief:
            return entries
        lines = ['Known findings']
        lines += ['- %s [%s] %s -- %s' % (e['id'], e['disposition'], e['text'], e['reason']) for e in entries]
        return '\n'.join(lines if entries else lines + ['- none'])

    def run_secret_scan(self, actor, lease):
        return self.run_gate(actor, lease, 'secret-scan', self.policy['secret_scan'].get('argv', []))

    def run_gate(self, actor, lease, name, argv, again=False, timeout=None):
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                                    or not math.isfinite(timeout) or timeout <= 0):
            raise EngineError('Gate timeout must be positive and finite')
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
        if decision is not None and (decision.boundary or decision.category in ('boundary', 'merged-delete')):
            raise EngineError('Gate command forbidden: boundary actions run only through the guarded hook')  # SPEC 5.14 item 5
        with self._state(False) as state:
            self._lease(state, actor, lease)
            gates = list(state['gates'])
        before = self.artifact()
        if not again:  # SPEC 5.11 item 2: a failed gate always reruns
            for gate in gates:
                if (gate['name'] == name and gate['argv'] == argv and gate['passed']
                        and self._same(gate['artifact'], before) and self._intact(gate)):
                    raise EngineError('Gate %s already passed on this artifact (receipt %s); pass --again to rerun'
                                      % (name, gate['id']))
        log = self.state_dir / ('gate-' + uuid.uuid4().hex + '.log')
        with log.open('xb') as out:
            try:
                if unavailable:
                    out.write(b'Optional secret scanner unavailable: no command configured\n')
                    code = 126
                else:
                    process = subprocess.Popen(argv, cwd=self.repo, stdout=out, stderr=subprocess.STDOUT,
                                               **portable.group_kwargs())
                    portable.track(process)
                    try:
                        code = process.wait(timeout=timeout or self.policy['gate_timeout_seconds'])
                    except subprocess.TimeoutExpired:
                        portable.kill_group(process)
                        process.wait()
                        portable.release(process)
                        raise
                    # Anything the gate left running in its own process group (on Windows, its job object) could still
                    # change the tree; a POSIX new session escapes this.
                    if portable.group_alive(process):
                        with contextlib.suppress(OSError):
                            portable.kill_group(process)
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline and portable.group_alive(process):  # the kill is asynchronous: wait until the group is gone before `after`
                            time.sleep(0.02)
                        out.write(b'\nGate left background processes running; stopped them\n')
                    portable.release(process)
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
        open_cards = [t for t in self._by_seq(state['tasks'].values()) if t['id'] in required_ids and t['state'] != 'accepted']
        if open_cards:
            held = ('; a CLEAN final review with `cleared` closes held tips'
                    if any(t['state'] == 'held' for t in open_cards) else '')
            raise EngineError('All tasks must be accepted: %s%s'
                              % (', '.join('%s (%s)' % (t['id'], t['state']) for t in open_cards), held))
        artifact = self.artifact()
        cache = {None: artifact}
        verdicts = self._review_verdicts(state, cache, final=True, keep=True)

        def open_findings(review):
            resolved = cache.get('resolved', {}).get(review['id'])
            if resolved is None:
                return review['findings']
            return [f for key, found in (review.get('task_findings') or {}).items() if key not in resolved for f in found]

        categories = {category for category, review in verdicts.items() if not open_findings(review)}
        if any(open_findings(review) for review in verdicts.values()):
            raise EngineError('Current final review has findings' + FINDING_ROUTES)
        for task_id in state['tasks']:
            task_verdicts = self._review_verdicts(state, cache, task_id=task_id, strict=True)
            if task_verdicts is None:
                raise EngineError(STALE_REVIEW + ': ' + task_id)
            if any(self._task_findings(r, task_id) for r in task_verdicts.values()):
                raise EngineError('Current task review has findings: ' + task_id + FINDING_ROUTES)
        required_categories = set(self._required_lenses(state))
        changed = self._run_changed(state)
        owed = require_review or bool(state['tasks']) or bool(changed and changed[0])  # unreviewed changes need a review
        if owed and not required_categories <= categories:
            raise EngineError('Current final review coverage is incomplete')
        triaged = {f['fingerprint'] for f in state.get('findings', []) if f['source'].get('kind') == 'out_of_scope'}
        for review in {r['id']: r for r in verdicts.values()}.values():  # SPEC 5.7 item 4
            for item in review.get('out_of_scope', []):
                if _fingerprint(item) not in triaged:
                    raise EngineError('Out-of-scope finding needs triage: ' + item)
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
            if not matching or not matching[-1]['passed'] or not self._same(matching[-1]['artifact'], artifact) or not self._intact(matching[-1]):
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
            missing = ['%s (%s)' % (t['id'], t['report_sha'][:8]) for t in self._by_seq(state['tasks'].values())
                       if t['role'] == 'builder' and t['state'] == 'accepted' and t.get('report_sha')
                       and not self._landed(t['report_sha'])]
            if missing:
                raise EngineError('Accepted work is not in HEAD: %s; merge it, or hold the card' % ', '.join(missing))
            self._end_run(state, 'finished' if self._autonomy_on(state) else 'closed')
            state['session'].update(active=False, outcome='completed')
            state['permits'] = []
            state['autonomy'] = self._kept_autonomy(state)
            return artifact

    def release_permit(self, actor, lease, remote, target, action='release'):
        with self._state() as state:
            self._lease(state, actor, lease)
            self._refuse_under_autonomy(state, 'release_permit', remote, target)
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
            self._refuse_under_autonomy(state, 'check_release', remote, target)
            artifact = self._release_evidence(state, remote, target, action, argv)
            for permit in reversed(state['permits']):
                if (permit['artifact'] == artifact and permit['remote'] == remote and permit['target'] == target
                        and permit['action'] == action and permit['lease'] == session['lease']):
                    return copy.deepcopy(permit)
            raise EngineError('No current explicit release permit')

    @staticmethod
    def _autonomy_on(state):
        """Armed autonomy with an active session. A 2.5 `relaunch` flag left in the state no longer counts."""
        auto = state['autonomy']
        return bool(auto and auto['active'] and state['session'] and state['session']['active'])

    def _refuse_under_autonomy(self, state, action, remote=None, target=None):
        """A permit or its check passes only for the exact pair the ledger pre-authorized (SPEC 5.8 item 8.3)."""
        if not self._autonomy_on(state):
            return
        release = state['autonomy'].get('release')
        if (action in ('release_permit', 'check_release') and release
                and (remote, target) == (release['remote'], release['target'])):
            return
        raise EngineError('Release and permits are approval boundaries while autonomy is active')

    def autonomy_active(self):
        with self._state(False) as state:
            return self._autonomy_on(state)

    def arm_autonomy(self, home=None):
        """Arm the loop from `<state>/autonomy.md` (SPEC 12.1). Takes no lease, by design (O8). The ledger and the
        release pre-authorization are checked first, then the remotes are asked for their default branches with no
        lock held, and only then is the armed state written: an arm interrupted or refused before that changes
        nothing. The write requires the very session the arm began with, so a session that replaced it meanwhile is
        never armed by the stale request."""
        path = self.state_dir / 'autonomy.md'
        with self._state(False) as state:
            self._refuse_rearm(state)
            self._armable(state, path, snapshot=False)  # read-only: no ledger copy yet
            lease = state['session']['lease']
        remote_heads, remote_defaults = ensure_remote_heads(self.repo)  # outside the state lock: it may reach the network
        remote_push_urls = {r: push_url_digest(url) for r in remote_defaults if (url := effective_push_url(self.repo, r))}
        current = self._git('branch', '--show-current').decode().strip()  # '' on a detached HEAD
        trunk = {*remote_defaults.values(), 'main', 'master'}
        if current in trunk:
            raise EngineError('Autonomy does not run on the default branch %s: switch to a work branch first '
                              '(git switch -c NAME), then arm again' % current)
        local = sorted(self._git('for-each-ref', '--format=%(refname:short)', 'refs/heads').decode().split())
        remotes = sorted(self._git('remote').decode().split(), key=len, reverse=True)
        remote_branches = set()
        for ref in self._git('for-each-ref', '--format=%(refname:lstrip=2)', 'refs/remotes').decode().split():
            remote = next((r for r in remotes if ref.startswith(r + '/')), None)
            if remote and ref[len(remote) + 1:] != 'HEAD':
                remote_branches.add(ref[len(remote) + 1:])
        with self._state(activity=False) as state:
            self._refuse_rearm(state)  # A second arm may have won while the remotes were asked
            fields, snapshot = self._armable(state, path)
            if state['session']['lease'] != lease:
                raise EngineError('The coordinator session changed while arming; arm again')
            if 'approval' in state:  # a receipt never survives a re-arm
                state.setdefault('approval_history', []).append(state.pop('approval'))
            state.setdefault('run_id', uuid.uuid4().hex[:16])  # a state written before 2.11 has none
            state['autonomy'] = dict(
                active=True, ledger=snapshot, passes=0, stalls=0, armed_at=self._clock(),
                armed_gates=len(state['gates']), armed_reviews=len(state['reviews']),
                accepted=self._accepted(state), remote_defaults=remote_defaults,
                remote_push_urls=remote_push_urls, local_branches_at_arm=local,
                remote_branches_at_arm=sorted(remote_branches), **fields)
        preconditions = autonomy_preconditions(self.repo, home)
        preconditions['remote_heads'] = remote_heads
        return dict(active=True, ledger=str(path), preconditions=preconditions)

    @staticmethod
    def _refuse_rearm(state):
        if (state.get('autonomy') or {}).get('active') is True:
            raise EngineError('Autonomy is already armed; disarm it first (/orchestra-autonomy off), then edit the ledger and arm again')

    def _armable(self, state, path, snapshot=True):
        """The checks arming needs before any change: an active session, a filled ledger that parses, and a release
        pre-authorization equal to policy.release. Returns the ledger fields and its snapshot."""
        if not state['session'] or not state['session']['active']:
            raise EngineError('Autonomy needs an armed run (an active session)')
        if not path.is_file():
            shutil.copyfile(AUTONOMY_TEMPLATE, path)
            raise EngineError('Ledger template written to %s: fill the ledger, then arm again' % path)
        data = path.read_bytes()
        fields = parse_ledger(data.decode(errors='replace'), self._clock())
        release = fields.get('release')
        policy = self.policy['release']
        if release and not (policy.get('enabled') is True and policy.get('remote') == release['remote']
                            and policy.get('target') == release['target']):
            raise EngineError('Release pre-authorization must match policy.release')
        if not snapshot:
            return fields, None
        copy_ = self._snapshot(path, 'ledger')
        if copy_['sha256'] != _hash(data):
            raise EngineError('Ledger changed while arming; arm again')
        return fields, copy_

    def disarm_autonomy(self):
        """Safe at any time; a no-op never rewrites state.json."""
        with self._state(False) as state:
            auto = state['autonomy']
            if not auto or (not auto['active'] and 'report' not in auto):
                return dict(was_active=False)
        with self._state(activity=False) as state:
            auto = state['autonomy']
            if not auto:
                return dict(was_active=False)
            if auto['active']:
                return dict(was_active=True, reason='disarmed', text=self._stop_autonomy(state, 'disarmed'))
            auto.pop('report', None)  # clear the report shown from the previous stop
            return dict(was_active=False)

    RECEIPT_PR_KEYS = {'order': int, 'number': int, 'repo': str, 'url': str, 'head_ref': str, 'head_sha': str, 'base_ref': str}

    def record_owner_approval(self, prs, excluded, evidence):
        """Write the owner's receipt for the stopped run and return it. The only writer: the prompt hook calls it in
        process and no CLI subcommand reaches it. A later call replaces the receipt. Refused while autonomy is active
        and for a run that never stopped (no kept report and no earlier receipt), so approval never pre-authorizes a
        run in progress. `prs` are the merge order, bottom of the stack first; `evidence` carries a prompt hash, never
        the prompt text."""
        if not (isinstance(prs, list) and all(
                isinstance(p, dict) and all(type(p.get(k)) is t for k, t in self.RECEIPT_PR_KEYS.items()) for p in prs)):
            raise EngineError('Approval prs must be a list of pull request entries with order, number, repo, url, head_ref, '
                              'head_sha and base_ref')
        if not (isinstance(excluded, list) and all(
                isinstance(e, dict) and type(e.get('number')) is int and isinstance(e.get('reason'), str) for e in excluded)):
            raise EngineError('Approval excluded must be a list of entries with number and reason')
        if not isinstance(evidence, dict):
            raise EngineError('Approval evidence must be an object')
        with self._state(activity=False, wait=True) as state:
            auto = state['autonomy'] or {}
            if auto.get('active'):
                raise EngineError('Approval is refused while autonomy is active')
            run = state.get('run_id')
            if run is None or ('report' not in auto and (state.get('approval') or {}).get('run') != run):
                raise EngineError('Approval is refused: the run never stopped')
            try:
                default = self._default_branch(auto)
            except EngineError:
                default = None
            state['approval'] = dict(version=1, run=run, recorded_at=self._clock(), evidence=copy.deepcopy(evidence),
                                     default_branch=default, prs=copy.deepcopy(prs), excluded=copy.deepcopy(excluded))
            return copy.deepcopy(state['approval'])

    def stop_stale_autonomy(self, session_id, now=None):
        """Stop an armed loop nobody is driving; True when this call stopped it. The Stop hook only fires in the
        running session, so a prompt from another session reaches here first. `deadline` when the ledger deadline has
        passed. `stale` when the run is bound to another harness session and `state.json` was last written more than
        `worker_stale_seconds` before `now` (default: the engine clock). A no-op never rewrites `state.json`. Gives up with
        StateBusy after `lock_wait` when the state lock is held."""
        now = self._clock() if now is None else now
        with self._state(False) as state:
            if self._stale_reason(state, session_id, now) is None:
                return False
        with self._state(activity=False, wait=True) as state:
            reason = self._stale_reason(state, session_id, now)
            if reason is None:
                return False
            self._stop_autonomy(state, reason)
            return True

    def _stale_reason(self, state, session_id, now):
        auto = state['autonomy']
        if not (auto and auto['active']):
            return None
        if now >= datetime.fromisoformat(auto['deadline']).timestamp():
            return 'deadline'
        if (state['session'] or {}).get('harness_session') == session_id:
            return None
        try:
            written = self.state_path.stat().st_mtime
        except OSError:
            return None
        return 'stale' if now - written > self.policy.get('worker_stale_seconds', WORKER_STALE_SECONDS) else None

    def _silent_workers(self, state):
        """Running background cards with no report for longer than `worker_stale_seconds`."""
        stale_after = self.policy.get('worker_stale_seconds', WORKER_STALE_SECONDS)
        return [t for t in state['tasks'].values() if t['state'] == 'running' and not t.get('inline')
                and self._clock() - t.get('started_at', self._clock()) > stale_after]

    def autonomy_status(self):
        """Read-only. `running` counts background workers, `silent` names those past `worker_stale_seconds`: the Stop
        hook that stops a stalled run fires only at the end of a turn, so a session idle on a lost worker is seen here,
        by the status band, and nowhere else. A run that stopped on `gate-failing` (a required gate failed three times
        in a row) shows it in `last_stop_reason`."""
        with self._state(False) as state:
            auto = state['autonomy'] or {}
            parked = [dict(id=t['id'], reason=t.get('parked_reason', ''))
                      for t in state['tasks'].values() if t['state'] == 'parked']
            silent = self._silent_workers(state)
            running = sum(1 for t in state['tasks'].values() if t['state'] == 'running' and not t.get('inline'))
            keys = ('passes', 'max_passes', 'stalls', 'max_stalls', 'deadline')
            return dict(active=self._autonomy_on(state), parked=parked, signature=self._signature(state),
                        last_stop_reason=auto.get('last_stop_reason'), pull_requests=auto.get('pull_requests') is True,
                        running=running, silent=[dict(id=t['id'], minutes=round((self._clock() - t['started_at']) / 60))
                                                 for t in silent if 'started_at' in t],
                        **{k: auto.get(k) for k in keys})

    @staticmethod
    def _signature(state):
        """SPEC 5.10 item 7: SHA-256 of canonical JSON of the sorted (id, state, report fingerprint, repaired_by)
        tuples, the counts of reviews, gates and findings, and the `activity` write counter (a park then unpark in
        one turn is progress). A pass that leaves it unchanged is a stall."""
        tasks = sorted([t['id'], t['state'], (t.get('report_artifact') or {}).get('fingerprint'), t.get('repaired_by')]
                       for t in state['tasks'].values())
        return _digest(dict(tasks=tasks, reviews=len(state['reviews']), gates=len(state['gates']),
                            findings=len(state.get('findings', [])), activity=state.get('activity', 0)))

    def autonomy_report(self):
        """The morning report shown at SessionStart, or None. Read-only."""
        with self._state(False) as state:
            return copy.deepcopy((state['autonomy'] or {}).get('report'))

    @staticmethod
    def _accepted(state):
        return sorted(t['id'] for t in state['tasks'].values() if t['state'] == 'accepted')

    def _write_brief(self, state, reason, stops=False):
        """SPEC 5.9: append the run brief to progress.md and remember it as `last_brief`. A stopped run's brief stays
        the remembered one when an end path that does not stop autonomy follows it (the progress entry still lands)."""
        at = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat(timespec='seconds')
        text = self._brief_text(state, reason, at)
        _append_progress(self.state_dir, text)
        brief = dict(reason=reason, at=at, text=text, path=str(self.state_dir / 'progress.md'))
        if stops or not self._stopped_report_kept(state):
            state['last_brief'] = brief
        return brief

    def brief(self):
        """The newest run brief's text, or None. Lease-free and read-only."""
        with self._state(False) as state:
            return (state.get('last_brief') or {}).get('text')

    def _stop_autonomy(self, state, reason):
        auto = state['autonomy']
        auto.update(active=False, last_stop_reason=reason)
        brief = self._write_brief(state, reason, stops=True)
        auto['report'] = dict(brief)
        return brief['text']

    def _brief_text(self, state, reason, at):
        """The run brief of SPEC 5.9: what needs the owner first, the 2.1 report lines last."""
        def listing(items):
            return ['  - ' + i for i in items] or ['  - none']

        def section(title, items):
            return ['### ' + title, *listing(items)]

        auto = state['autonomy']
        tasks = state['tasks']
        findings = state.get('findings', [])
        chain_of = lambda tip: self._brief_chain(tasks, tip)
        header = ['## Run brief ' + at, '', '- stop reason: ' + reason]
        if auto:
            header += ['- deadline: ' + str(auto.get('deadline')),
                       '- passes: %d' % auto['passes'],
                       '- stalls: %d' % auto['stalls']]
            caps = ['%s %d' % (k, auto[k]) for k in ('max_passes', 'max_stalls') if k in auto]
            if caps:
                header += ['- caps from the 2.1 ledger: %s (recorded, not enforced)' % ', '.join(caps)]
        else:
            header += ['- autonomy: not armed']
        parked = ['%s: %s' % (t['id'], t.get('parked_reason', '')) for t in tasks.values() if t['state'] == 'parked']
        needs = list(parked)
        needs += ['%s -- %s' % (e['text'], e['reason']) for e in findings if e['disposition'] == 'brief']
        needs += ['%s -- %s' % (e['text'], e['reason']) for e in findings if e['disposition'] == 'deferred']
        needs += ['review and merge pull request ' + entry['url'] for entry in self._pull_requests(state)]
        if reason == 'stalled' and (auto or {}).get('pr_gap'):
            needs.append('publish the work: ' + auto['pr_gap'])
        gate = self._failing_gate(state) if reason == 'gate-failing' else None
        if gate:
            log = [g['path'] for g in state['gates'] if g['name'] == gate][-1]
            needs.append('required gate %s failed %d times in a row -- read its log %s, fix the cause, then arm again'
                         % (gate, GATE_FAILURE_LIMIT, log))
        if (reason in ('closed', 'finished', 'complete') and not any(self._is_release(t) for t in tasks.values())
                and not (auto or {}).get('release')):
            needs.append('ready to release')
        cleared_by = {}
        for review in state['reviews']:
            if review.get('final'):
                cleared_by.update(review.get('cleared') or {})
        held_tips = [t for t in tasks.values() if t.get('held_finding')]
        if any(t['state'] == 'parked' and not self._is_release(t) for t in tasks.values()):
            needs += ['%s (chain %s): held -- %s' % (t['id'], ', '.join(chain_of(t['id'])), t['held_finding'])
                      for t in held_tips if t['id'] not in cleared_by and not t.get('repaired_by')]
        failing = []
        cache = {}
        for task in tasks.values():
            if task['role'] != 'builder' or task.get('repaired_by') or task['state'] == 'held':
                continue
            try:
                verdicts = self._review_verdicts(state, cache, task_id=task['id'])
            except EngineError:
                continue
            blocking = list(dict.fromkeys(f for r in verdicts.values() for f in self._task_findings(r, task['id'])))
            if blocking:
                failing.append('%s (chain %s): %s' % (task['id'], ', '.join(chain_of(task['id'])), '; '.join(blocking)))
        for tip in held_tips:
            if tip['id'] in cleared_by or tip.get('repaired_by'):
                continue
            rounds = [t['final_round'] for t in tasks.values() if t.get('final_round') and t.get('repair_of') in chain_of(tip['id'])]
            failing.append('%s (chain %s): %s; final round: %s' % (
                tip['id'], ', '.join(chain_of(tip['id'])), tip['held_finding'], max(rounds) if rounds else 'none'))
        failing += ['%s (%s/%s): %s, not finished' % (t['id'], t['role'], t['mode'], t['state']) for t in tasks.values()
                    if t['state'] in ('queued', 'running', 'reported', 'repairing')]  # what a stopped run left undone
        held_log = []
        for tip in held_tips:
            if tip.get('repaired_by'):
                fix = tasks[tip['repaired_by']]
                status = ('fixed in final round %s by %s' % (fix['final_round'], fix['id']) if fix.get('final_round')
                          else 'repaired by ' + fix['id'])
            elif tip['id'] in cleared_by:
                status = 'cleared by a lens: ' + cleared_by[tip['id']]
            else:
                status = 'still ' + tip['state']
            held_log.append('%s (chain %s): %s -- %s' % (tip['id'], ', '.join(chain_of(tip['id'])), tip['held_finding'], status))
        rounds = {}
        for task in tasks.values():
            if task.get('final_round'):
                rounds.setdefault(task['final_round'], []).append(task)
        final_rounds = []
        for number in sorted(rounds):
            cards = sorted(rounds[number], key=lambda t: t.get('seq', 0))
            open_ = [t for t in cards if t['state'] != 'accepted']
            names = ', '.join('%s (chain %s)' % (t['id'], ', '.join(self._brief_chain(tasks, t['id'], full=True))) for t in cards)
            cleared = list(dict.fromkeys(f for t in cards for f in t.get('final_findings', [])))
            final_rounds.append('round %d: %s %s: %s' % (number, names, 'open' if open_ else 'cleared', '; '.join(cleared) or 'none'))
        notes = [str(n) for r in state['reviews'] for n in r.get('notes', [])]
        deferred = ['%s -- %s' % (e['text'], e['reason']) for e in findings if e['disposition'] == 'deferred']
        accepted = []
        for t in tasks.values():
            if t['state'] != 'accepted':
                continue
            line = '%s (%s/%s)' % (t['id'], t['role'], t['mode'])
            if t.get('repair_of') or t.get('repaired_by'):
                line += ' repaired (%s)' % ', '.join(self._brief_chain(tasks, t['id'], full=True))
            accepted.append(line)
        start_gates = auto['armed_gates'] if auto else 0
        start_reviews = auto['armed_reviews'] if auto else 0
        failures = ['gate %s: exit %d' % (g['name'], g['exit_code']) for g in state['gates'][start_gates:] if not g['passed']]
        failures += ['review %s: BLOCKED (%s)' % (r['reviewer'], '; '.join(map(str, r['findings'])))
                     for r in state['reviews'][start_reviews:] if r['findings']]
        lines = header + ['']
        for part in (section('Needs you', needs), section('Still failing / next phase', failing),
                     section('Held log', held_log), section('Final rounds', final_rounds), section('Notes', notes),
                     section('Deferred findings', deferred), section('Parked', parked), section('Accepted', accepted),
                     section('Failures', failures)):
            lines += part
        return '\n'.join(lines)

    @staticmethod
    def _brief_chain(tasks, tip, full=False):
        """Card ids of a repair chain: tip first (as `hold` logs it), or oldest first from the whole chain of `tip`."""
        chain = [tip, *(t['id'] for t in Engine._walk(tasks, tasks[tip], 'repair_of'))]
        if not full:
            return chain
        chain.reverse()
        return chain + [t['id'] for t in Engine._walk(tasks, tasks[tip], 'repaired_by')]

    def _complete(self, state):
        """SPEC 5.8 item 3: the cheap all-accepted check first, then the ledger checks, then the completion evidence."""
        if any(t['state'] != 'accepted' for t in state['tasks'].values()):
            return False
        auto = state['autonomy']
        matches = []
        for check in auto['checks']:
            same = [g for g in state['gates'] if g['name'] == check['name'] and g['argv'] == check['argv']]
            if not same or not same[-1]['passed'] or not self._intact(same[-1]):
                return False
            matches.append(same[-1])
        artifact = self.artifact()
        if not all(self._same(g['artifact'], artifact) for g in matches):
            return False
        try:
            self._completion_evidence(state)
        except EngineError:
            return False
        return True

    def _stop_check(self, state):
        """The Stop decision: (reason, message). A reason stops autonomy; a message continues the turn; neither lets
        the turn end with autonomy still armed.

        The turn continues only when the coordinator has work it can do now: a ready card, a reported card no running
        reviewer is judging, its own inline card, an open final finding, a held chain no current final receipt covers,
        or the final phase once every card is accepted. Running workers alone end the turn quietly, since the harness
        wakes the session when a background worker finishes. A message is never sent twice for the same progress
        signature: a turn that changed nothing since the last continuation ends, counted as a stall, and with no
        worker running to wake the session the run stops as `stalled`."""
        auto = state['autonomy']
        tasks = list(state['tasks'].values())
        if not self._intact(auto['ledger']):
            return 'ledger-tampered', None
        if self._clock() >= datetime.fromisoformat(auto['deadline']).timestamp():
            return 'deadline', None
        if self._complete(state):
            gap = self._publication_gap(state)
            if gap is None:
                return 'complete', None
            passes = auto.get('pr_passes', 0)
            if passes >= PR_CONTINUATIONS:
                auto['stalls'] += 1
                auto['pr_gap'] = gap
                return 'stalled', None
            auto.update(pr_passes=passes + 1, accepted=self._accepted(state))
            auto['passes'] += 1
            return None, 'Autonomy pass %d: %s; push the branch, open the pull request, then record it with `pr URL`.' % (
                auto['passes'], gap)
        auto.pop('pr_passes', None)  # consecutive means no other work came between
        auto.pop('pr_gap', None)
        parked = any(t['state'] == 'parked' for t in tasks)
        held = (not any(t['state'] == 'parked' and not self._is_release(t) for t in tasks)
                and any(t['state'] == 'held' and not t.get('repaired_by') and not self._final_receipts(state, t['id'])
                        for t in tasks))
        failing = self._failing_gate(state)
        if failing:
            return 'gate-failing', None
        stale_after = self.policy.get('worker_stale_seconds', WORKER_STALE_SECONDS)
        silent = self._silent_workers(state)
        running = any(t['state'] == 'running' and not t.get('inline') and t not in silent for t in tasks)
        judged = {i for t in tasks if t['state'] == 'running' for i in t.get('review_of', [])}
        actionable = (any(t['state'] == 'reported' and t['id'] not in judged for t in tasks)
                      or any(t['state'] == 'running' and t.get('inline') for t in tasks) or bool(self._ready(state)))
        final_open = not (running or actionable) and any(
            t['role'] == 'builder' and t['state'] == 'accepted' and not t.get('repaired_by')
            and self._final_blocks(state, t['id']) for t in tasks)
        base = (state['session'] or {}).get('base')
        final_owed = (not (running or actionable or held or final_open or parked)
                      and all(t['state'] == 'accepted' for t in tasks)
                      and bool(tasks or (base is not None and self._run_changed(state)[0])))
        if silent and not (running or actionable or held or final_open or final_owed):
            auto['accepted'] = self._accepted(state)
            names = ', '.join(t['id'] for t in silent)
            span = '%d minutes' % round(stale_after / 60) if stale_after >= 60 else '%d seconds' % round(stale_after)
            message = ('the worker for %s has been silent for over %s and may be gone: park the card with `park CARD '
                       '--reason lost-worker`, `unpark` it and dispatch it again, or wait if it is a long task.'
                       % (names, span))
            signature = self._signature(state)
            if signature == auto.get('signature'):
                auto['stalls'] += 1
                return 'stalled', None
            auto['signature'] = signature
            auto['stalls'] = 0
            auto['passes'] += 1
            return None, 'Autonomy pass %d: %s' % (auto['passes'], message)
        if not (running or actionable or held or final_open or final_owed):
            return ('parked-only' if parked else 'no-ready-card'), None
        auto['accepted'] = self._accepted(state)
        if actionable:
            message = 'continue with the next ready or reported card; park any card that reaches an approval boundary.'
        elif running:
            return None, None  # Waiting on workers: the harness wakes the session when one finishes
        elif final_open:
            message = 'start the final repair round; a current final finding is still open.'
        elif held:
            message = 'start or continue the final phase; held work is still owed a final review.'
        else:
            message = ('every card is accepted; commit the work, run the final review and the completion gates, '
                       'then push the branch and open the pull request.')
        signature = self._signature(state)
        if signature == auto.get('signature'):
            auto['stalls'] += 1  # The last continuation changed nothing: end the turn instead of repeating it
            return (None if running else 'stalled'), None  # with no worker to wake the session, stop and brief
        auto['signature'] = signature
        auto['stalls'] = 0
        auto['passes'] += 1
        return None, 'Autonomy pass %d: %s' % (auto['passes'], message)

    def _publication_gap(self, state):
        """Why finished work is not yet published, or None: the branch holds commits beyond the session base and no
        verified pull request the run opened has the current head."""
        base = (state['session'] or {}).get('base')
        try:
            head = self._git('rev-parse', 'HEAD').decode().strip()
            ahead = base is None or int(self._git('rev-list', '--count', base + '..HEAD').decode()) > 0
        except (EngineError, ValueError):
            return 'the work branch cannot be compared with its base'
        if not ahead or any(e.get('autonomous') and e.get('verified_at') and e.get('head_sha') == head
                            for e in self._pull_requests(state)):
            return None
        return 'every card is accepted and the checks passed, but the branch holds commits and no verified pull request has head ' + head[:12]

    def _failing_gate(self, state):
        """The name of a required gate whose last GATE_FAILURE_LIMIT receipts all failed, else None: an unattended run
        stops instead of repeating it until the deadline."""
        names = [c['name'] if isinstance(c, dict) else c for c in self.policy['required_checks']]
        names += [c['name'] for c in (state['autonomy'] or {}).get('checks', []) if isinstance(c, dict)]  # the ledger's checks
        if self.policy['secret_scan'].get('required'):
            names.append('secret-scan')
        for name in names:
            recent = [g for g in state['gates'] if g['name'] == name][-GATE_FAILURE_LIMIT:]
            if len(recent) == GATE_FAILURE_LIMIT and not any(g['passed'] for g in recent):
                return name
        return None

    def hook_stop(self):
        """The Stop continuation of SPEC 5.8: no count stops it, only the deadline, completion, tamper, disarm, an
        idle run, a required gate that failed three times in a row (`gate-failing`) and a stall with no worker running
        (`stalled`). When every worker is silent past `worker_stale_seconds` the turn continues once with a message to
        park or re-dispatch the lost card, then stops as `stalled`. Finished work counts as `complete` only once a
        verified pull request has the current head or nothing lies beyond the base; two nudges to push and open it
        come first. Caller identifiers do not authenticate."""
        with self._state(False) as state:
            if not self._autonomy_on(state):
                return None  # Read-only unless autonomy is active in a session
        with self._state(activity=False) as state:
            if not self._autonomy_on(state):
                return None
            reason, message = self._stop_check(state)
            if reason is None:
                return message
            self._stop_autonomy(state, reason)
            return None
