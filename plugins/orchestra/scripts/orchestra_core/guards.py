"""Bounded shell guard. Not an interpreter, alias or hostile-worker sandbox."""
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
import re
import shlex


@dataclass(frozen=True)
class Decision:
    action: str = 'allow'
    reason: str = ''
    category: str = ''
    remote: str | None = None
    target: str | None = None
    argv: tuple[str, ...] = ()


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
        elif char in ';|&()\n':
            yield command[start:i]
            start = i + 1
    yield command[start:]


# Each wrapper has different flag/value rules (sudo -n has no value; nice -n does).
_WRAPPER_VALUES = {
    'exec': {'-a'}, 'command': set(), 'builtin': set(), 'nohup': set(),
    'env': {'-u', '--unset', '-C', '--chdir', '-S', '--split-string'},
    'sudo': {'-u', '--user', '-g', '--group', '-h', '--host', '-p', '--prompt',
             '-C', '--close-from', '-T', '--command-timeout', '-R', '--chroot',
             '-D', '--chdir', '-r', '--role', '-t', '--type'},
    'nice': {'-n', '--adjustment'},
    'timeout': {'-s', '--signal', '-k', '--kill-after'},
    'time': {'-f', '--format', '-o', '--output'},
}


def _unwrap(words):
    while words:
        name = PurePosixPath(words[0]).name
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[0]):
            words = words[1:]
        elif name in _WRAPPER_VALUES:
            wrapper = name
            words = words[1:]
            while words and (words[0].startswith('-') or
                             re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[0])):
                option = words.pop(0)
                if option == '--':
                    break
                if wrapper == 'env' and option.startswith('--split-string='):
                    words = shlex.split(option.split('=', 1)[1]) + words
                    break
                if option in _WRAPPER_VALUES[wrapper]:
                    if not words:
                        raise ValueError('Missing wrapper option value')
                    value = words.pop(0)
                    if wrapper == 'env' and option in {'-S', '--split-string'}:
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
        if token in {'-o', '+o', '-O', '+O', '--rcfile', '--init-file'}:
            i += 2
            continue
        if re.fullmatch(r'-[A-Za-z]+', token) and 'c' in token[1:]:
            return words[i + 1] if i + 1 < len(words) else ''
        i += 1
    return None


def _git(words):
    args = words[1:]
    changed_repo = False
    while args and args[0].startswith('-'):
        opt = args.pop(0)
        if opt in {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env', '--exec-path', '--super-prefix', '--attr-source'}:
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
        value_options = {'-e', '--exclude'} if verb == 'clean' else {'-o', '--push-option', '--receive-pack', '--exec'}
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
        return _deny('Git stash shares state across worktrees', 'stash')
    if verb == 'reset' and any(x == '--hard' or x.startswith('--hard=') for x in flags):
        return _deny('Hard reset discards work')
    if verb == 'clean' and ('f' in short or '--force' in flags) and not ('n' in short or '--dry-run' in flags):
        return _deny('Forced clean discards files')
    if verb == 'branch' and ('D' in short or (('d' in short or '--delete' in flags) and ('f' in short or '--force' in flags))):
        return _deny('Forced branch deletion discards refs')
    if verb in {'checkout', 'restore'} and ('.' in args or ':/' in args or '--force' in flags or (verb == 'checkout' and 'f' in short)):
        return _deny('Wholesale restore discards work')
    if verb == 'add' and (any(x in flags for x in ['--all', '--update']) or 'A' in short or 'u' in short or '.' in args or ':/' in args):
        return _deny('Stage explicit paths only', 'wholesaleStage')
    if verb == 'commit':
        # A message beginning with a dash is still a message.
        opts = []
        i = 0
        while i < len(options):
            token = options[i]
            if token in {'-m', '--message', '-F', '--file', '-C', '-c', '--reuse-message', '--reedit-message'}:
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
        if len(positional) > 2 or any(x in flags for x in {'--all', '--tags', '--follow-tags', '--delete', '--prune'}) or 'd' in short:
            return _deny('Push needs one explicit remote and refspec', 'release')
        remote, target = (positional + [None, None])[:2]
        if target:
            if target.startswith(':') or '*' in target:
                return _deny('Push needs one non-deleting refspec', 'release')
            target = target.split(':')[-1].removeprefix('refs/heads/')
        if changed_repo:
            remote = target = None  # Native cwd cannot attest a different Git repository.
        if dry_run:
            return Decision('allow', 'Dry-run push does not release', 'gitpush', remote, target, tuple(words))
        return Decision('release', 'Push needs an exact current release permit', 'gitpush', remote, target, tuple(words))
    return Decision()


def classify_command(command: str, _depth=0) -> Decision:
    if not isinstance(command, str) or not command.strip() or len(command) > 131072 or _depth > 8:
        return _deny('Invalid or excessively nested command', 'malformed')
    result = Decision()
    try:
        segments = [shlex.split(segment, comments=True) for segment in _segments(command)]
        segments = [words for words in segments if words]
        for original in segments:
            words = _unwrap(original.copy())
            if not words:
                continue
            name = PurePosixPath(words[0]).name
            if name in {'sh', 'bash', 'zsh', 'dash', 'ksh'}:
                payload = _shell_payload(words)
                decision = classify_command(payload, _depth + 1) if payload is not None else Decision()
            elif name == 'eval':
                decision = classify_command(' '.join(words[1:]), _depth + 1)
            elif name == 'git':
                decision = _git(words)
            elif ((name == 'gh' and words[1:3] in [['pr', 'merge'], ['release', 'create']]) or
                  (name == 'az' and ('deployment' in words or (words[1:4] == ['repos', 'pr', 'update'] and 'completed' in words))) or
                  (name in {'npm', 'pnpm'} and 'publish' in words[1:]) or
                  (name in {'vercel', 'netlify', 'flyctl', 'wrangler', 'swa'} and any(x in words[1:] for x in {'deploy', 'publish', '--prod'}))):
                decision = Decision('release', 'Provider release needs structured authorization', 'providerrelease', argv=tuple(words))
            else:
                decision = Decision()
            if decision.action == 'deny':
                return decision
            if decision.action == 'release':
                # A prior cd/env or nested shell must not inherit a plain Git permit.
                decision = replace(decision, argv=tuple(original))
                if len(segments) != 1 or result.action == 'release':
                    return _deny('Execute release actions separately', 'release')
                result = decision
            elif decision.category and result.action != 'release':
                result = replace(decision, argv=tuple(original))
    except ValueError:
        return _deny('Malformed shell quoting', 'malformed')
    return result
