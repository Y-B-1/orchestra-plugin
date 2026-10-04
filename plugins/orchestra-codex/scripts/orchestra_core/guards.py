"""Bounded shell guard. Not an interpreter, alias or hostile-worker sandbox.

The rules table (config/guard-rules.json) and the corpus (config/guard-corpus.json)
are shared with the TypeScript mod; the corpus is the parity contract.
"""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex

RULES_PATH = Path(__file__).resolve().parents[2] / 'config/guard-rules.json'
RULES = {key: value for key, value in json.loads(RULES_PATH.read_text(encoding='utf-8')).items()
         if not key.startswith('_')}  # Underscore keys (_doc) are documentation only.
GUARD_DIGEST_FILES = ('config/guard-rules.json', 'scripts/orchestra_core/guards.py',
                      'scripts/orchestra_core/hooks.py', 'hooks/mod/guard.ts')
_SHELLS = frozenset(RULES['shells'])
_SHELL_VALUE_FLAGS = frozenset(RULES['shell_value_flags'])
_WRAPPER_VALUES = {name: set(values) for name, values in RULES['wrappers'].items()}
_GIT = {key: (set(value) if isinstance(value, list) else value) for key, value in RULES['git'].items()}
_RELEASE = RULES['release']
_BOUNDARY = RULES['boundary']
_MULTI = 'releasemulti'  # Decision.category of a release-class segment inside a multi-segment command.


def guard_digest(root=None):
    """SHA-256 over the plugin-root guard files (SPEC 10.3). Per file: relative path, NUL, decimal
    byte length, NUL, bytes. A missing file counts as zero bytes. Computed at runtime, never stored."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for rel in GUARD_DIGEST_FILES:
        try:
            data = (root / rel).read_bytes()
        except OSError:
            data = b''
        digest.update(rel.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
    return digest.hexdigest()


@dataclass(frozen=True)
class Decision:
    action: str = 'allow'
    reason: str = ''
    category: str = ''
    remote: str | None = None
    target: str | None = None
    argv: tuple[str, ...] = ()
    source: str | None = None
    boundary: str | None = None  # 'delete' or 'merge' for class boundary; action stays allow.

    @property
    def klass(self):
        """The SPEC 5.1 class: allow, deny, release, release-multi or boundary."""
        if self.boundary:
            return 'boundary'
        if self.category == _MULTI:
            return 'release-multi'
        return self.action


def _deny(reason, category='destructiveGit'):
    return Decision('deny', reason, category)


def _split(command):
    # Split operators only outside quotes; quoted messages remain ordinary arguments.
    # Yields (segment, operator that ended it); the last segment has operator ''.
    start, quote, escaped = 0, None, False
    for i, char in enumerate(command):
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == '&' and ((i and command[i - 1] in '<>') or command[i + 1:i + 2] == '>'):
            continue  # Descriptor duplication and Bash's combined redirect are not control operators.
        elif char == '|' and i and command[i - 1] == '>':
            continue
        elif char in ';|&()\n':
            yield command[start:i], char
            start = i + 1
    yield command[start:], ''


def _segments(command):
    for segment, _ in _split(command):
        yield segment


def _pipelines(command):
    """Group non-empty segments joined by a single `|` (or `|&`, or a pipe before a newline)."""
    parts = list(_split(command))
    pipelines, current, k = [], [], 0
    while k < len(parts):
        segment, op = parts[k]
        if segment.strip():
            current.append(segment)
        join = False
        if op == '|' and k + 1 < len(parts):
            following, following_op = parts[k + 1]
            if following.strip():
                join = True
            elif following_op in {'&', '\n'}:
                join = True
                k += 1
        if not join and current:
            pipelines.append(current)
            current = []
        k += 1
    if current:
        pipelines.append(current)
    return pipelines


_MARK = '\ue000'  # Private-use delimiter for the placeholder that stands in for a heredoc operator.
_MARK_RE = re.compile('<<' + _MARK + r'\d+' + _MARK)
_REDIRECT = re.compile(r'(?:[0-9]*(?:>&|<&|>>|>\||<>|>|<)|&>>?)(.*)')
_HEREDOC = re.compile(r'<<(-?)[ \t]*("[^"\n]*"|\'[^\'\n]*\'|\\?[A-Za-z_0-9][A-Za-z_0-9.\-]*)')


def _strip_heredocs(command):
    """Remove heredoc bodies before segmentation. Returns (text, [(body, quoted_delimiter)]).
    Each operator becomes a numbered placeholder so the pipeline that consumes it can be found."""
    out, docs, pending = [], [], []
    quote, escaped, i, n = None, False, 0, len(command)
    while i < n:
        char = command[i]
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == '<' and command.startswith('<<', i) and not command.startswith('<<<', i) and (i == 0 or command[i - 1] != '<'):
            match = _HEREDOC.match(command, i)
            # An all-digit word is shell arithmetic (1 << 2), not a heredoc.
            if match and not match.group(2).isdigit():
                word = match.group(2)
                quoted = word[0] in '\'"\\'
                word = word[1:-1] if word[0] in '\'"' else word.removeprefix('\\')
                pending.append((word, match.group(1) == '-', quoted))
                out.append('<<' + _MARK + str(len(docs) + len(pending) - 1) + _MARK)
                i = match.end()
                continue
        elif char == '\n':
            out.append(char)
            i += 1
            for word, strip, quoted in pending:
                body, found = [], False
                while i < n:
                    end = command.find('\n', i)
                    line = command[i:end if end >= 0 else n]
                    i = end + 1 if end >= 0 else n
                    if (line.lstrip('\t') if strip else line) == word:
                        found = True
                        break
                    body.append(line)
                if not found:
                    raise ValueError('Heredoc has no terminator')
                docs.append(('\n'.join(body), quoted))
            pending = []
            continue
        out.append(char)
        i += 1
    if pending:
        raise ValueError('Heredoc has no terminator')
    return ''.join(out), docs


def _unwrap(words):
    while words:
        name = PurePosixPath(words[0]).name
        redirect = _REDIRECT.fullmatch(words[0])
        if redirect:
            words = words[1:] if redirect.group(1) else words[2:]
        elif re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[0]):
            words = words[1:]
        elif name in _WRAPPER_VALUES:
            wrapper = name
            words = words[1:]
            while words and (words[0].startswith('-') or
                             re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[0])):
                option = words.pop(0)
                if option == '--':
                    break
                value = None
                value_option = option
                if option.startswith('--') and '=' in option:
                    value_option, value = option.split('=', 1)
                elif option.startswith('-') and not option.startswith('--'):
                    # A value-taking short flag ends the cluster; its suffix is its value.
                    for i, char in enumerate(option[1:], 1):
                        if '-' + char in _WRAPPER_VALUES[wrapper]:
                            value_option = '-' + char
                            value = option[i + 1:] or None
                            break
                if value_option in _WRAPPER_VALUES[wrapper]:
                    if value is None:
                        if not words:
                            raise ValueError('Missing wrapper option value')
                        value = words.pop(0)
                    if wrapper == 'env' and value_option in {'-S', '--split-string'}:
                        words = shlex.split(value) + words
                        break
            if wrapper == 'timeout' and words:
                words.pop(0)
        else:
            return words
    return words


def _shell_payload(words):
    """Return the literal -c argument, ignoring long flags and option values."""
    i = 1
    while i < len(words):
        token = words[i]
        if token == '--' or not token.startswith(('-', '+')):
            return None
        if token in _SHELL_VALUE_FLAGS:
            i += 2
            continue
        if re.fullmatch(r'-[A-Za-z]+', token) and 'c' in token[1:]:
            return words[i + 1] if i + 1 < len(words) else ''
        i += 1
    return None


def _boundary(kind, reason):
    return Decision('allow', reason, 'boundary', boundary=kind)


def _git(words):
    args = words[1:]
    changed_repo = False
    while args and args[0].startswith('-'):
        opt = args.pop(0)
        if opt in _GIT['global_value_options']:
            if not args:
                return _deny('Malformed Git global option', 'malformed')
            args.pop(0)
        if opt.startswith('-C') or opt.startswith(('--git-dir', '--work-tree')):
            changed_repo = True
    if not args:
        return Decision()
    verb, args = args[0], args[1:]
    options = args[:args.index('--')] if '--' in args else args
    if verb in {'clean', 'push'}:
        value_options = _GIT['clean_value_options'] if verb == 'clean' else _GIT['push_value_options']
        filtered, i = [], 0
        while i < len(options):
            if options[i] in value_options:
                i += 2
            else:
                filtered.append(options[i])
                i += 1
        options = filtered
    flags = [x for x in options if x.startswith('-')]
    short = ''.join(x[1:] for x in flags if not x.startswith('--'))
    if verb == 'stash':
        if args and args[0] in _GIT['stash_allowed']:
            return Decision()
        return _deny('Git stash shares state across worktrees', 'stash')
    if verb == 'reset' and any(x == '--hard' or x.startswith('--hard=') for x in flags):
        return _deny('Hard reset discards work')
    if verb == 'clean' and ('f' in short or '--force' in flags) and not ('n' in short or '--dry-run' in flags):
        return _deny('Forced clean discards files')
    if verb == 'branch' and ('D' in short or (('d' in short or '--delete' in flags) and ('f' in short or '--force' in flags))):
        return _deny('Forced branch deletion discards refs')
    wholesale = '.' in args or ':/' in args
    if verb == 'checkout' and (wholesale or '--force' in flags or 'f' in short):
        return _deny('Wholesale restore discards work')
    if verb == 'switch' and ('f' in short or any(x in flags for x in _GIT['switch_force_flags'])):
        return _deny('Wholesale restore discards work')
    if verb == 'restore':
        staged_only = ('--staged' in flags or 'S' in short) and not ('--worktree' in flags or 'W' in short)
        if '--force' in flags or (wholesale and not staged_only):
            return _deny('Wholesale restore discards work')
    if verb == 'add' and (any(x in flags for x in ['--all', '--update']) or 'A' in short or 'u' in short or '.' in args or ':/' in args):
        return _deny('Stage explicit paths only', 'wholesaleStage')
    if verb == 'commit':
        # A message beginning with a dash is still a message.
        opts = []
        i = 0
        while i < len(options):
            token = options[i]
            if token in _GIT['commit_value_options']:
                i += 2
                continue
            if token.startswith(('--message=', '--file=')) or token.startswith('-m'):
                i += 1
                continue
            opts.append(token)
            i += 1
        if '--all' in opts or any(x.startswith('-') and not x.startswith('--') and 'a' in x[1:] for x in opts):
            return _deny('Commit explicit staged paths only', 'wholesaleStage')
    if verb == 'push':
        if any(x.startswith('--force') or x == '--mirror' for x in flags) or 'f' in short or any(x.startswith('+') for x in args):
            return _deny('Force push rewrites remote history')
        dry_run = '--dry-run' in flags or 'n' in short
        positional = [x for x in options if not x.startswith('-')]
        if len(positional) > 2 or any(x in flags for x in _GIT['push_multi_flags']) or 'd' in short:
            return _deny('Push needs one explicit remote and refspec', 'release')
        remote, target = (positional + [None, None])[:2]
        source = target.split(':', 1)[0] if target else None
        if target:
            if target.startswith(':') or '*' in target or target.count(':') > 1:
                return _deny('Push needs one non-deleting refspec', 'release')
            target = target.split(':')[-1].removeprefix('refs/heads/')
        if changed_repo:
            remote = target = source = None  # Native cwd cannot attest a different Git repository.
        if dry_run:
            return Decision('allow', 'Dry-run push does not release', 'gitpush', remote, target, tuple(words), source)
        return Decision('release', 'Push needs an exact current release permit', 'gitpush', remote, target, tuple(words), source)
    if (verb == 'rm' or (verb == 'branch' and ('d' in short or '--delete' in flags)) or
            (verb == 'tag' and ('d' in short or '--delete' in flags)) or
            (verb == 'worktree' and args and args[0] in _GIT['worktree_delete'])):
        return _boundary('delete', 'Deletion is a boundary action')
    if verb in _GIT['boundary_merge_verbs']:
        return _boundary('merge', 'Local merge is a boundary action')
    return Decision()


def _is_release(name, words):
    return ((name == 'gh' and words[1:3] in _RELEASE['gh']) or
            (name == 'az' and (all(x in words for x in _RELEASE['az_requires']) or
                               (words[1:4] == _RELEASE['az_pr_update']['prefix'] and _RELEASE['az_pr_update']['word'] in words))) or
            (name in _RELEASE['package_tools'] and _RELEASE['package_verb'] in words[1:]) or
            (name in _RELEASE['deploy_tools'] and any(x in words[1:] for x in _RELEASE['deploy_words'])))


def _classify_segment(words, depth):
    name = PurePosixPath(words[0]).name
    if name in _SHELLS:
        payload = _shell_payload(words)
        return classify_command(payload, depth + 1) if payload is not None else Decision()
    if name == 'eval':
        return classify_command(' '.join(words[1:]), depth + 1)
    if name == 'git':
        return _git(words)
    if _is_release(name, words):
        return Decision('release', 'Provider release needs structured authorization', 'providerrelease', argv=tuple(words))
    if (name in _BOUNDARY['delete_commands'] or (name == 'find' and _BOUNDARY['find_delete_flag'] in words[1:]) or
            (name == 'gh' and words[1:3] in _BOUNDARY['gh'])):
        return _boundary('delete', 'Deletion is a boundary action')
    return Decision()


def _hard_deny(decision):
    """An always-deny verdict: not a malformed payload and not a release-class multi-segment verdict."""
    return decision.action == 'deny' and decision.category not in {'malformed', _MULTI}


def _scan_lines(body, depth, keep_release=False):
    """Classify each line of a body on its own (continuations joined). A line that fails to parse
    is skipped, never denied as malformed. Returns the first always-deny verdict, else (if asked)
    the first release-class verdict, else allow."""
    release = Decision()
    for line in body.replace('\\\n', '').split('\n'):
        if not line.strip():
            continue
        decision = classify_command(line, depth + 1)
        if _hard_deny(decision):
            return decision
        if keep_release and decision.action == 'release' and release.action == 'allow':
            release = decision
    return release


def _substitutions(body):
    """Command substitutions in an unquoted heredoc body. Quote characters are literal there, so the
    scan is quote-blind; an escaped dollar or backtick and `$((` arithmetic are skipped."""
    found, i, n = [], 0, len(body)
    while i < n:
        char = body[i]
        if char == '\\':
            i += 2
        elif body.startswith('$((', i):
            i += 3
        elif body.startswith('$(', i):
            depth, j = 1, i + 2
            while j < n and depth:
                if body[j] == '\\':
                    j += 1
                elif body[j] == '(':
                    depth += 1
                elif body[j] == ')':
                    depth -= 1
                j += 1
            content = body[i + 2:j - 1 if depth == 0 else j]
            found.append(content)
            found.extend(_substitutions(content))
            i = j
        elif char == '`':
            j = i + 1
            while j < n and body[j] != '`':
                j += 2 if body[j] == '\\' else 1
            content = body[i + 1:j]
            found.append(content)
            found.extend(_substitutions(content))
            i = j + 1
        else:
            i += 1
    return found


def _consumer_mode(segment):
    """How a pipeline segment reads a heredoc: 'c' (shell with -c), 'script' (shell without -c,
    source, `.` or eval) or None. Wrappers are unwrapped first."""
    words = _unwrap(shlex.split(segment, comments=True))
    kept, skip = [], False
    for word in words:
        if skip:
            skip = False
            continue
        redirect = _REDIRECT.fullmatch(word)
        if redirect:
            skip = not redirect.group(1)
        else:
            kept.append(word)
    if not kept:
        return None
    if PurePosixPath(kept[0]).name in _SHELLS:
        return 'c' if _shell_payload(kept) is not None else 'script'
    if kept[0] in {'.', 'source', 'eval'}:
        return 'script'
    return None


def _heredoc_items(docs, pipelines, depth):
    """SPEC A5 rules (1) to (5): extra (decision, argv, counts) items for each heredoc body."""
    items = []
    for index, (body, quoted) in enumerate(docs):
        marker = '<<' + _MARK + str(index) + _MARK
        modes, argv = set(), ()
        for pipeline in pipelines:
            where = next((i for i, segment in enumerate(pipeline) if marker in segment), None)
            if where is not None:
                argv = tuple(_MARK_RE.sub('<<HEREDOC', word) for word in shlex.split(pipeline[where], comments=True))
                # Rules (1) to (3): the consumer and every later command of its pipeline.
                modes = {_consumer_mode(segment) for segment in pipeline[where:]}
                break
        if 'script' in modes or 'c' in modes:
            if not body.strip():
                decision = Decision()
            elif 'script' in modes:
                decision = classify_command(body, depth + 1)
            else:  # Under -c the body is not what the shell runs, so an unparsable body is ignored.
                decision = classify_command(body, depth + 1)
                if decision.category == 'malformed':
                    decision = _scan_lines(body, depth, keep_release=True)
            items.append((decision, argv, False))
        if not quoted:  # Rule (4)
            for content in _substitutions(body):
                decision = classify_command(content, depth + 1)
                if _hard_deny(decision):
                    items.append((decision, argv, False))
        decision = _scan_lines(body, depth)  # Rule (5)
        if decision.action == 'deny':
            items.append((decision, argv, False))
    return items


def classify_command(command: str, _depth=0) -> Decision:
    if not isinstance(command, str) or not command.strip() or len(command) > 131072 or _depth > 8:
        return _deny('Invalid or excessively nested command', 'malformed')
    try:
        text, docs = _strip_heredocs(command)
        segments = [[_MARK_RE.sub('<<HEREDOC', word) for word in shlex.split(segment, comments=True)]
                    for segment in _segments(text)]
        segments = [words for words in segments if words]
        items = []  # (decision, original words, counts as a segment)
        for original in segments:
            words = _unwrap(original.copy())
            if words:
                items.append((_classify_segment(words, _depth), original, True))
        items.extend(_heredoc_items(docs, _pipelines(text), _depth))
    except ValueError as exc:
        return _deny('Malformed heredoc' if str(exc).startswith('Heredoc') else 'Malformed shell quoting', 'malformed')
    for decision, _, _ in items:
        if decision.action == 'deny' and decision.category != _MULTI:
            return decision
    total = sum(1 for _, _, counts in items if counts)
    releases = [(d, o) for d, o, _ in items if d.action == 'release']
    if any(d.category == _MULTI for d, _, _ in items) or len(releases) > 1 or (releases and total > 1):
        return _deny('Execute release actions separately', _MULTI)
    if releases:
        # A prior cd/env or nested shell must not inherit a plain Git permit.
        return replace(releases[0][0], argv=tuple(releases[0][1]))
    for kind in ('delete', 'merge'):
        for decision, _, _ in items:
            if decision.boundary == kind:
                return decision
    result = Decision()
    for decision, original, _ in items:
        if decision.category:
            result = replace(decision, argv=tuple(original))
    return result
