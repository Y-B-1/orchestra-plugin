"""The merge guard: after the owner types "approved", a run's pull requests merge to the default branch only in the
receipt's order, at the recorded head, with the printed command. Read-only: it reads `state.json` and asks `gh`;
it never writes state. Best effort for a cooperating agent, not isolation from a hostile one."""
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from subprocess import TimeoutExpired

APPROVAL_PROMPT = re.compile(r'\s*approved[\s.!]*', re.I)
GH_TIMEOUT = 6  # seconds; below the mod's 8 s delegate timeout and the hook's 10 s
LIST_LIMIT = 1000
PR_URL = re.compile(r'https?://[^/]+/([^/]+/[^/]+)/pull/([0-9]+)/?')
MERGE_SEGMENT = re.compile(r'\bgh\b[^;&|\n]*\bpr\s+merge\b|\bgh\b[^;&|\n]*\bapi\b[^;&|\n]*/merge\b|'
                           r'\bgh\b[^;&|\n]*\bapi\b[^;&|\n]*\bgraphql\b[^;&|\n]*(?:(?i:merge)|=@)|'  # a merge mutation, or a
                           r'\bgh\b[^;&|\n]*\brepo\s+set-default\b')  # query the guard cannot read
SET_DEFAULT = re.compile(r'\bgh\b[^;&|\n]*\brepo\s+set-default\b')
SET_DEFAULT_REASON = 'gh repo set-default changes which repository gh merges into; pass -R OWNER/REPO instead'
METHOD_FLAGS = {'--merge', '-m'}  # F119: `_parse` refuses every other method flag on a gated merge
METHOD_REASON = 'add --merge: the guard allows only a merge commit on a run pull request'
COMPOUND = re.compile(r'[;&|\n`<>()]|\$\(')
API_PULL = re.compile(r'pulls/([0-9]+)/merge\b')
ENV_WORDS = {'env', 'export', 'command', 'sudo', 'exec', 'nohup', 'time'}
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=')
TRUNK = {'main', 'master'}
LIST_FIELDS = 'number,state,baseRefName,headRefName,headRefOid'
ALONE = 'run the merge alone, as one plain gh pr merge command'


class GhError(Exception):
    """gh is missing, failed, timed out or answered something unreadable."""


class GhTimeout(GhError):
    """gh did not answer within the time it was given."""


def run_gh(args, cwd, timeout=None):
    """Run `gh ARGS` and return its stdout; GhError on any failure. `timeout` (seconds) is capped at GH_TIMEOUT."""
    limit = GH_TIMEOUT if timeout is None else min(GH_TIMEOUT, timeout)
    gh = shutil.which('gh')
    if not gh:
        raise GhError('gh is not installed')
    try:
        done = subprocess.run([gh, *args], cwd=cwd if cwd and Path(cwd).is_dir() else None, capture_output=True,
                              text=True, timeout=limit, stdin=subprocess.DEVNULL,
                              env=dict(os.environ, GH_PROMPT_DISABLED='1'))
    except (OSError, subprocess.SubprocessError) as exc:
        if isinstance(exc, TimeoutExpired):
            raise GhTimeout('gh did not answer within %ss' % limit) from exc
        raise GhError('gh did not answer within %ss: %s' % (limit, type(exc).__name__)) from exc
    if done.returncode:
        raise GhError('gh exited %d' % done.returncode)
    return done.stdout


def raw_unattended(state):
    """True for a stopped run whose report is kept and whose receipt for this run is not recorded yet: the unattended
    lock of the morning-after window. Reads raw state only."""
    auto = state.get('autonomy') if isinstance(state, dict) else None
    if not isinstance(auto, dict) or auto.get('active') is True or 'report' not in auto:
        return False
    receipt = state.get('approval')
    return not (isinstance(receipt, dict) and receipt.get('run') is not None and receipt.get('run') == state.get('run_id'))


def _entries(state):
    """The recorded pull requests as dicts with number and repo; a 2.10 state holds bare URL strings."""
    out = []
    for item in state.get('pull_requests') or []:
        entry = dict(url=item, autonomous=False) if isinstance(item, str) else dict(item) if isinstance(item, dict) else None
        if entry is None:
            continue
        found = PR_URL.fullmatch(entry.get('url') or '')
        if found:
            entry.setdefault('repo', found.group(1))
            entry.setdefault('number', int(found.group(2)))
        out.append(entry)
    return out


def _correct(number, sha, slug='OWNER/REPO'):
    return 'gh pr merge %s -R %s --merge --delete-branch --match-head-commit %s' % (number, slug, sha or 'SHA')


def _parse(command):
    """(number, url slug or None, head commit or None, -R slug or None) of a plain `gh pr merge`, or a deny reason
    string."""
    if COMPOUND.search(command):
        return ALONE
    try:
        words = shlex.split(command)
    except ValueError:
        return ALONE
    if not words or words[0] in ENV_WORDS or ASSIGNMENT.match(words[0]) or os.path.basename(words[0]) != 'gh':
        return ALONE
    if words[1:2] == ['api']:
        found = API_PULL.search(command)
        return 'a merge through gh api is not allowed: use ' + _correct(found.group(1) if found else 'N', None)
    if words[1:3] != ['pr', 'merge']:
        return ALONE
    sha, named, positional, rest = None, None, [], iter(words[3:])
    for word in rest:
        if word in ('--merge', '-m', '--delete-branch', '-d'):
            continue
        if word in ('-R', '--repo'):
            named = next(rest, None) or ''
            continue
        if word.startswith(('--repo=', '-R')):
            named = word.split('=', 1)[1] if word.startswith('--repo=') else word[2:]
            continue
        if word == '--match-head-commit':
            sha = next(rest, None)
        elif word.startswith('--match-head-commit='):
            sha = word.split('=', 1)[1]
        elif word.startswith('-'):
            return ('merge flag %s is not allowed: only -R OWNER/REPO, --merge, --delete-branch and --match-head-commit SHA'
                    % word.split('=')[0])
        else:
            positional.append(word)
    if len(positional) != 1:
        return 'name the pull request by its number: ' + _correct('NUMBER', None)
    if named is not None and not re.fullmatch(r'[^/\s]+/[^/\s]+', named):
        return '-R takes OWNER/REPO: ' + _correct('NUMBER', None)
    if positional[0].isdigit():
        return int(positional[0]), None, sha, named
    found = PR_URL.fullmatch(positional[0])
    if not found:
        return 'name the pull request by its number, not a branch: ' + _correct('NUMBER', None)
    return int(found.group(2)), found.group(1), sha, named


def _default_branches(state):
    auto = state.get('autonomy') if isinstance(state.get('autonomy'), dict) else {}
    receipt = state.get('approval') if isinstance(state.get('approval'), dict) else {}
    names = set(TRUNK) | set((auto.get('remote_defaults') or {}).values())
    if isinstance(receipt.get('default_branch'), str):
        names.add(receipt['default_branch'])
    return names


def _default_name(state, parent):
    auto = state.get('autonomy') if isinstance(state.get('autonomy'), dict) else {}
    receipt = state.get('approval') if isinstance(state.get('approval'), dict) else {}
    defaults = auto.get('remote_defaults') or {}
    return (receipt.get('default_branch') or defaults.get('origin') or (sorted(defaults.values()) or [None])[0]
            or parent.get('base_ref') or 'main')


def _step_five(state, number, sha, found, live):
    """The receipt path: a run pull request that targets the default branch."""
    auto = state.get('autonomy') if isinstance(state.get('autonomy'), dict) else {}
    if auto.get('active') is True:
        return 'deny', 'autonomy is active: the run does not merge; stop it, then type approved in the owner session'
    receipt = state.get('approval')
    if not (isinstance(receipt, dict) and receipt.get('run') is not None and receipt.get('run') == state.get('run_id')):
        return 'deny', 'no owner approval for this run: type approved in the owner session first'
    prs = receipt.get('prs') if isinstance(receipt.get('prs'), list) else []
    row = next((p for p in prs if isinstance(p, dict) and p.get('number') == number), None)
    if row is None:
        return 'deny', 'pull request %d is not in the owner receipt; type approved again after the run records it' % number
    want = row.get('head_sha')
    fix = _correct(number, want, row.get('repo') or 'OWNER/REPO')
    if found['headRefOid'] != want:
        return 'deny', 'pull request %d head moved since approval (%s, receipt %s): type approved again' % (
            number, str(found['headRefOid'])[:12], str(want)[:12])
    if sha != want:
        return 'deny', 'the merge must pin the approved head: ' + fix
    for lower in sorted((p for p in prs if isinstance(p, dict) and isinstance(p.get('order'), int)
                         and p['order'] < row.get('order', 0)), key=lambda p: p['order']):
        other = live.get(lower.get('number'))
        if other is not None and other.get('state') == 'CLOSED':
            return 'deny', ('pull request %s was closed without merging; type approved again so the receipt drops it'
                            % lower.get('number'))
        if other is None or other.get('state') != 'MERGED':
            return 'deny', 'merge pull request %s first (receipt order %s); then run: %s' % (lower.get('number'), lower['order'], fix)
    return 'allow', ''


def merge_decision(command, cwd, state_dir, repo, gh=None):
    """`_decide`, except that a merge it would allow must name a method (N5) and the recorded repository (RS N1:
    without -R or a URL, gh picks the repository from the checkout's remotes, which the guard does not check)."""
    result = _decide(command, cwd, state_dir, repo, gh)
    if result == ('allow', '') and not SET_DEFAULT.search(command):
        try:
            words = shlex.split(command)
        except ValueError:
            return result
        if not METHOD_FLAGS.intersection(words):
            return 'deny', METHOD_REASON
        parsed = _parse(command)
        if not isinstance(parsed, str) and parsed[1] is None and parsed[3] is None:
            return 'deny', 'name the recorded repository, so the checkout remotes cannot pick another: ' + _correct(
                parsed[0], parsed[2], _recorded_slug(state_dir, parsed[0]))
    return result


def _recorded_slug(state_dir, number):
    try:
        runs = [e for e in _entries(json.loads((Path(state_dir) / 'state.json').read_text())) if e.get('autonomous') is True]
    except (OSError, ValueError, AttributeError):
        return 'OWNER/REPO'
    found = next((e for e in runs if e.get('number') == number), None) or (runs[0] if runs else {})
    return found.get('repo') if isinstance(found.get('repo'), str) else 'OWNER/REPO'


def _decide(command, cwd, state_dir, repo, gh=None):
    """None: not gated, the caller continues. ('allow', ''): the merge may run. ('deny', reason). `gh(args, cwd)`
    returns gh's stdout or raises GhError; it defaults to the real gh."""
    if not isinstance(command, str) or not MERGE_SEGMENT.search(command):
        return None
    try:
        state = json.loads((Path(state_dir) / 'state.json').read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return 'deny', 'the run state is unreadable, so the merge cannot be checked; run orchestra.py status'
    if not isinstance(state, dict):
        return 'deny', 'the run state is unreadable, so the merge cannot be checked; run orchestra.py status'
    auto = state.get('autonomy') if isinstance(state.get('autonomy'), dict) else {}
    entries = _entries(state)
    runs = [e for e in entries if e.get('autonomous') is True]
    active, unattended = auto.get('active') is True, raw_unattended(state)
    if SET_DEFAULT.search(command):  # N1: the cwd remotes would point a later gh pr merge at another repository
        return ('deny', SET_DEFAULT_REASON) if active or unattended else None
    if not (runs or active or unattended):
        return None
    parsed = _parse(command)
    if isinstance(parsed, str):
        return 'deny', parsed
    number, url_slug, sha, named = parsed
    slugs = sorted({e['repo'] for e in runs if isinstance(e.get('repo'), str)})
    recorded = next((e for e in runs if e.get('number') == number), None)
    slug = recorded['repo'] if recorded and isinstance(recorded.get('repo'), str) else slugs[0] if slugs else None
    if slug is None:
        return 'deny', 'no recorded pull request names the repository, so pull request %d cannot be checked' % number
    if url_slug is not None and url_slug.lower() != slug.lower():
        return 'deny', 'the pull request URL names %s, not the recorded %s' % (url_slug, slug)
    if named is not None and named.lower() != slug.lower():
        return 'deny', 'the merge names %s, not the recorded %s: %s' % (named, slug, _correct(number, sha, slug))
    must = active or unattended or recorded is not None
    try:
        listing = json.loads((gh or run_gh)(['pr', 'list', '--state', 'all', '-R', slug, '--json', LIST_FIELDS,
                                              '--limit', str(LIST_LIMIT)], str(repo)))
        live = {p['number']: p for p in listing if isinstance(p, dict) and type(p.get('number')) is int}
    except (GhError, ValueError, TypeError, KeyError) as exc:
        return ('deny', 'gh could not list pull requests (%s); try again' % exc) if must else None
    trunk, run_branches = _default_branches(state), {e.get('head_ref') for e in runs if e.get('head_ref')}
    found = live.get(number)
    if recorded is None:  # a pull request the run did not open
        if not (active or unattended):
            return None
        if found is None:
            return 'deny', 'pull request %d is unreachable, so its base cannot be checked' % number
        if found.get('baseRefName') in trunk:
            return 'deny', 'pull request %d targets %s and the run did not open it; merge it yourself in your terminal' % (
                number, found['baseRefName'])
        return ('allow', '') if found.get('baseRefName') in run_branches else None
    if found is None:
        return 'deny', 'pull request %d is unreachable: gh did not list it' % number
    if found.get('state') != 'OPEN':
        return 'deny', 'pull request %d is not open (%s)' % (number, found.get('state'))
    base = found.get('baseRefName')
    if base in run_branches and base not in trunk:
        parent = next((e for e in runs if e.get('head_ref') == base), None)
        above = live.get(parent.get('number')) if parent else None
        if above is not None and above.get('state') == 'MERGED':
            return 'deny', ('pull request %d is still based on %s, whose pull request merged: run gh pr edit %d --base %s, '
                            'then merge it' % (number, base, number, _default_name(state, parent)))
        if above is not None and above.get('state') == 'OPEN':
            return 'allow', ''
        return 'deny', 'the parent pull request of %d (base %s) is not open or listed' % (number, base)
    if base in trunk:
        return _step_five(state, number, sha, found, live)
    return 'deny', 'pull request %d has base %s, which is neither the default branch nor a run branch' % (number, base)
