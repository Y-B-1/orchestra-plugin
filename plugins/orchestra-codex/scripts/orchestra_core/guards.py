"""Bounded shell guard. Not an interpreter, alias or hostile-worker sandbox.

The rules table (config/guard-rules.json) and the corpus (config/guard-corpus.json)
are shared with the TypeScript mod; the corpus is the parity contract.
"""
from dataclasses import dataclass, replace
import json
from pathlib import Path, PurePosixPath
import re
import shlex

RULES_PATH = Path(__file__).resolve().parents[2] / 'config/guard-rules.json'
RULES = json.loads(RULES_PATH.read_text(encoding='utf-8'))
_SHELLS = frozenset(RULES['shells'])
_SHELL_VALUE_FLAGS = frozenset(RULES['shell_value_flags'])
_WRAPPER_VALUES = {name: set(values) for name, values in RULES['wrappers'].items()}
_GIT = {key: (set(value) if isinstance(value, list) else value) for key, value in RULES['git'].items()}
_RELEASE = RULES['release']
_BOUNDARY = RULES['boundary']
_MULTI = 'releasemulti'  # Decision.category of a release-class segment inside a multi-segment command.


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


def _segments(command):
    # Split operators only outside quotes; quoted messages remain ordinary arguments.
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
            yield command[start:i]
            start = i + 1
    yield command[start:]


_HEREDOC = re.compile(r'<<(-?)[ \t]*("[^"\n]*"|\'[^\'\n]*\'|\\?[A-Za-z_0-9][A-Za-z_0-9.\-]*)')


def _strip_heredocs(command):
    """Remove heredoc bodies before segmentation. Returns (text, [(body, consumer_text)])."""
    out, docs, pending = [], [], []
    quote, escaped, seg, i, n = None, False, '', 0, len(command)
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
                word = word[1:-1] if word[0] in '\'"' else word.removeprefix('\\')
                pending.append((word, match.group(1) == '-', seg))
                out.append('<<HEREDOC')
                seg += '<<HEREDOC'
                i = match.end()
                continue
        elif char == '\n':
            out.append(char)
            seg = ''
            i += 1
            for word, strip, consumer in pending:
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
                docs.append(('\n'.join(body), consumer))
            pending = []
            continue
        elif char in ';|&()':
            out.append(char)
            seg = ''
            i += 1
            continue
        out.append(char)
        seg += char
        i += 1
    if pending:
        raise ValueError('Heredoc has no terminator')
    return ''.join(out), docs


def _unwrap(words):
    while words:
        name = PurePosixPath(words[0]).name
        redirect = re.fullmatch(r'(?:[0-9]*(?:>&|<&|>>|>\||<>|>|<)|&>>?)(.*)', words[0])
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


def classify_command(command: str, _depth=0) -> Decision:
    if not isinstance(command, str) or not command.strip() or len(command) > 131072 or _depth > 8:
        return _deny('Invalid or excessively nested command', 'malformed')
    try:
        text, docs = _strip_heredocs(command)
        segments = [shlex.split(segment, comments=True) for segment in _segments(text)]
        segments = [words for words in segments if words]
        items = []  # (decision, original words, counts as a segment)
        for original in segments:
            words = _unwrap(original.copy())
            if words:
                items.append((_classify_segment(words, _depth), original, True))
        for body, consumer in docs:
            # A shell interpreter reading the heredoc runs the body as a script.
            consumer_words = _unwrap(shlex.split(consumer, comments=True)) if consumer.strip() else []
            if consumer_words and PurePosixPath(consumer_words[0]).name in _SHELLS and _shell_payload(consumer_words) is None:
                items.append((classify_command(body, _depth + 1), shlex.split(consumer, comments=True), False))
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
