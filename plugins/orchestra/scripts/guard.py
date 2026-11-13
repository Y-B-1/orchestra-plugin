"""Orchestra guard: the PreToolUse hook. Denies merging into the default branch, a second Fable critic and, during a
run, an agent that inherits the main session's model. Loaded by lean.py for `hook pre-tool-use`."""
import fnmatch, json, os, re, shlex, time
from pathlib import Path

import lean


SEPARATORS = ('&&', '||', '$(', ';', '|', '&', '\n', '`', '(', ')', '{', '}')
HEREDOC = re.compile(r'<<(-?)[ \t]*(?:\'([^\']*)\'|"([^"]*)"|(\\?)([A-Za-z_][A-Za-z0-9_]*))')
SUBSTITUTION = re.compile(r'\$\(([^)]*)\)|`([^`]*)`')


def skip_heredocs(command, i, pending, shell):
    """From the newline at i, skip the bodies of the pending heredocs. Returns (text still to scan, index of the
    end of the last terminator line). A quoted body is plain text unless a shell reads it; an unquoted one can
    still run its $( ) and backtick spans."""
    j, scan = i + 1, []
    for dash, quoted, delim in pending:
        start = j
        while j < len(command):
            end = command.find('\n', j)
            end = len(command) if end < 0 else end
            if (command[j:end].lstrip('\t') if dash else command[j:end]) == delim:
                break
            j = end + 1
        body = command[start:j]
        if shell:
            scan.append(body)
        elif not quoted:
            scan.extend(m.group(1) or m.group(2) for m in SUBSTITUTION.finditer(body))
        end = command.find('\n', j)
        j = len(command) if end < 0 else end
    return scan, j


def split_commands(command):
    """Split a shell line into simple commands at operators, subshells and command substitutions.
    Quoted text stays whole, except that $( and ` inside double quotes still start a new command.
    Heredoc bodies are not commands; ${...} is one word."""
    command = command.replace('\\\n', '')
    parts, buf, quote, sub, pending, i = [], [], None, False, [], 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            buf.append(c)
            quote = None if c == "'" else quote
            i += 1
            continue
        if c == '\\' and i + 1 < len(command):
            buf.append(command[i:i + 2])
            i += 2
            continue
        if c == '<' and command.startswith('<<', i) and not command.startswith('<<<', i) and (quote is None or sub):
            m = HEREDOC.match(command, i)
            if m:
                pending.append((m.group(1) == '-', m.group(2) is not None or m.group(3) is not None or bool(m.group(4)),
                                m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None else m.group(5)))
                buf.append(m.group())
                i = m.end()
                continue
        if c == '\n' and pending:
            line = command[command.rfind('\n', 0, i) + 1:i]
            scan, i = skip_heredocs(command, i, pending, bool(re.search(r'\b(sh|bash|zsh|dash|ksh)\b', line)))
            pending = []
            parts.append(''.join(buf))
            buf = []
            for text in scan:
                parts.extend(split_commands(text))
            continue
        sep = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if quote == '"':
            if c == '"':
                quote, sub = None, False
            elif sep in ('$(', '`'):
                parts.append(''.join(buf))
                buf, sub, i = [], True, i + len(sep)
                continue
            buf.append(c)
            i += 1
            continue
        if c == '$' and command.startswith('${', i) and command.find('}', i) > 0:
            end = command.find('}', i) + 1
            buf.append(command[i:end])
            i = end
            continue
        if c in '\'"':
            quote = c
        elif sep:
            parts.append(''.join(buf))
            buf, i = [], i + len(sep)
            continue
        buf.append(c)
        i += 1
    parts.append(''.join(buf))
    return [x for x in parts if x.strip()]


SHELLS = ('sh', 'bash', 'zsh', 'dash', 'ksh')
KEYWORDS = ('if', 'then', 'elif', 'else', 'do', 'while', 'until', '!')
PREFIX = ('sudo', 'env', 'command', 'time', 'nohup', 'exec', 'xargs', 'nice', 'timeout', 'npx', 'bunx', 'pnpx')
PREFIX_VALUE_OPTS = {'sudo': ('-u', '-g', '-h', '-p', '-C', '-D', '-R', '-T', '-U'), 'env': ('-u', '-C', '-S'),
                     'nice': ('-n',), 'xargs': ('-n', '-I', '-P', '-L', '-s', '-d', '-E', '-a'),
                     'timeout': ('-s', '--signal', '-k', '--kill-after'), 'npx': ('-p', '--package', '-c')}
GIT_VALUE_OPTS = ('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env')
PUSH_VALUE_OPTS = ('-o', '--push-option', '--repo', '--receive-pack', '--exec')
GH_VALUE_OPTS = ('-R', '--repo')
API_VALUE_OPTS = ('-X', '--method', '-f', '-F', '--field', '--raw-field', '-H', '--header', '--jq', '-q', '--input',
                  '-t', '--template', '--hostname', '-p', '--preview', '--cache')


def tool_name(word):
    return re.sub(r'\.exe$', '', os.path.basename(word).lower())


def command_words(words):
    """The words from the command's own name on: skips VAR=value, shell keywords, wrappers (sudo, env, nice,
    timeout, npx ...) with their options and values, and the plugin's `lean.py run SECONDS --`."""
    i = 0
    while i < len(words):
        w, name = words[i], tool_name(words[i])
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', w) or w in KEYWORDS:
            i += 1
        elif name in PREFIX:
            i += 1
            while i < len(words) and words[i].startswith('-'):
                i += 1 if words[i] == '--' else 2 if words[i] in PREFIX_VALUE_OPTS.get(name, ()) else 1
            i += name == 'timeout'  # its duration
        elif re.fullmatch(r'python[\d.]*', name):
            j = i + 1
            while j < len(words) and words[j].startswith('-'):
                j += 1
            if words[j + 1:j + 2] == ['run'] and tool_name(words[j]) == 'lean.py' and '--' in words[j + 2:]:
                i = j + 2 + words[j + 2:].index('--') + 1
            else:
                break
        else:
            break
    return words[i:]


def skip_options(rest, value_opts):
    """Drop leading options; an option in value_opts without '=' also drops its value."""
    while rest and rest[0].startswith('-') and rest[0] != '--':
        rest = rest[2:] if rest[0] in value_opts else rest[1:]  # -Ro/r and --repo=o/r carry their value
    return rest


def drop_redirects(words):
    """Remove redirections (`> file`, `2>&1`, `< in`, `main>/dev/null`) so a target is not read as an argument.
    A word is cut at its first `[0-9]*[<>]` and the prefix is kept."""
    out, i = [], 0
    while i < len(words):
        m = re.search(r'\d*[<>]', words[i])
        if not m:
            out.append(words[i])
            i += 1
            continue
        if m.start():
            out.append(words[i][:m.start()])
        i += 2 if re.fullmatch(r'\d*(>>?|<<?<?|>&|&>>?)', words[i][m.start():]) else 1
    return out


def api_endpoint(args):
    i = 0
    while i < len(args):
        if not args[i].startswith('-'):
            return args[i]
        i += 2 if args[i] in API_VALUE_OPTS else 1
    return ''


def gh_reason(rest, main):
    """main is a function: the default branch is looked up only for an API write."""
    rest = skip_options(rest, GH_VALUE_OPTS)
    if rest[:1] == ['pr'] and skip_options(rest[1:], GH_VALUE_OPTS)[:1] == ['merge']:
        return 'gh pr merge'
    if rest[:1] != ['api']:
        return None
    endpoint = api_endpoint(rest[1:])
    flat = ' '.join(rest)
    if endpoint == 'graphql' and any(w.startswith('query=') and ('mergePullRequest' in w or 'enablePullRequestAutoMerge' in w)
                                     for w in rest):
        return 'a GitHub API merge'
    method = 'GET'
    for i, w in enumerate(rest):
        if w in ('-X', '--method') and i + 1 < len(rest):
            method = rest[i + 1].upper()
        elif w.startswith('--method='):
            method = w.split('=', 1)[1].upper()
        elif w.startswith('-X') and len(w) > 2:
            method = w[2:].upper()
        elif method == 'GET' and w in ('-f', '-F', '--field', '--raw-field', '--input'):
            method = 'POST'
    if method == 'GET':
        return None
    if re.search(r'/merges?/?$', endpoint.split('?')[0]):
        return 'a GitHub API merge'
    m = re.escape(main())
    if re.search(rf'git/refs/heads/{m}(?![\w./-])', flat) or re.search(rf'\bref=refs/heads/{m}(?![\w./-])', flat):
        return f'a GitHub API write to {main()}'
    if re.search(rf'/branches/{m}/rename\b', flat):
        return f'a rename of {main()}'
    if '/contents/' in flat and re.search(rf'\bbranch={m}(?![\w./-])', flat):
        return f'a GitHub API commit to {main()}'
    return None


def git_options(rest):
    """(git's repository-selecting options, the words after the global options)."""
    opts = []
    while rest and rest[0].startswith('-') and rest[0] != '--':
        n = 2 if rest[0] in GIT_VALUE_OPTS else 1
        if rest[0] in ('-C', '--git-dir', '--work-tree') or rest[0].startswith(('-C', '--git-dir=', '--work-tree=')):
            opts += rest[:n]
        rest = rest[n:]
    return opts, rest


def pushes_branch(rest):
    """True when the words after `push` push a branch: not a delete, not tags only."""
    if '--delete' in rest or '-d' in rest:
        return False
    refs = [w for w in rest if not w.startswith('-')][1:]
    if not refs:
        return '--tags' not in rest
    return any(not r.startswith((':', 'refs/tags/')) for r in refs)


def git_reason(rest, state, pushes=None):
    """state(opts) is a function: (default branch, current branch, local branches) of the repository git selects.
    pushes, when given, collects the git options of each push that sends a branch."""
    opts, rest = git_options(rest)
    if rest[:1] != ['push']:
        return None
    main, current, branches = state(tuple(opts))
    rest = rest[1:]
    if '--mirror' in rest:
        return 'a mirror push (it overwrites every branch, the default one included)'
    if ('--all' in rest or '--branches' in rest) and main in branches:
        return f'a push of all branches, {main} included'
    args, explicit_repo, i = [], False, 0
    while i < len(rest):
        w = rest[i]
        if w in PUSH_VALUE_OPTS:
            explicit_repo = explicit_repo or w == '--repo'
            i += 2
            continue
        if w.startswith('--repo='):
            explicit_repo = True
        if not w.startswith('-'):
            args.append(w)
        i += 1
    refs = args if explicit_repo else args[1:]
    if not refs and current == main and '--tags' not in rest:
        return f'a push of {main}'
    for ref in refs:
        dst = ref.lstrip('+').split(':')[-1]
        dst = dst[len('refs/heads/'):] if dst.startswith('refs/heads/') else dst
        if dst in ('HEAD', '@'):
            dst = current
        if dst == main or fnmatch.fnmatchcase(main, dst) or fnmatch.fnmatchcase('refs/heads/' + main, dst):
            return f'a push to {main}'
    if pushes is not None and pushes_branch(rest):
        pushes.append(tuple(opts))
    return None


def merge_reason(command, cwd=None, cache=None, pushes=None):
    """A reason when the command merges into, pushes to or deletes the default branch; else None.
    Git runs at most once per repository, and not at all for a command with no git or gh word."""
    if not re.search(r'\b(git|gh)\b', command):
        return None
    cache = {} if cache is None else cache
    for part in split_commands(command):
        try:
            words = shlex.split(part)
        except ValueError:  # an unbalanced quote, as in the tail of "$(git push origin main)"
            words = [w.strip('"\'()') for w in part.split()]
        words = command_words([w for w in words if w])
        if not words:
            continue
        name = tool_name(words[0])
        if name in ('cd', 'pushd') and len(words) > 1:  # later parts run in that folder
            cwd = str((Path(cwd or os.getcwd()) / os.path.expanduser(words[1])).resolve())
            continue
        if name in SHELLS:
            for i, w in enumerate(words[1:-1], 1):
                if re.fullmatch(r'-[A-Za-z]*c[A-Za-z]*', w):
                    inner = merge_reason(words[i + 1], cwd, cache, pushes)
                    if inner:
                        return inner
                    break
            continue
        if name == 'eval':
            inner = merge_reason(' '.join(words[1:]), cwd, cache, pushes)
            if inner:
                return inner
            continue

        def state(opts=(), cwd=cwd):
            if (cwd, opts) not in cache:
                cache[cwd, opts] = lean.repo_state(cwd, opts)
            return cache[cwd, opts]
        if name == 'gh':
            reason = gh_reason(drop_redirects(words[1:]), lambda: state()[0])
        elif name == 'git':
            found = []
            reason = git_reason(drop_redirects(words[1:]), state, found if pushes is not None else None)
            for opts in found:  # the folder git works in: the last -C wins, each relative to the one before
                where = cwd
                for k, o in enumerate(opts):
                    if o == '-C' and k + 1 < len(opts):
                        where = str(Path(where or os.getcwd()) / os.path.expanduser(opts[k + 1]))
                pushes.append(where)
        else:
            reason = None
        if reason:
            return reason
    return None


MERGE_TOOL = re.compile(r'^mcp__.*merge_pull_request$')


def deny(reason):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': reason}}))


# ---- one Fable critic, and the model matrix (Agent, Task and Workflow calls) -------------------

CRITIC = 'critic-fable'
FABLE_LOCK_SECONDS = 1800  # a lock written when a critic call was allowed counts for this long
INHERIT_TYPES = ('general-purpose', 'claude', 'fork')  # agent types that run on the main session's model
LOOP_CALL = re.compile(r'(?<!\w)(map|forEach|for|while|parallel|pipeline)\s*\(|\bArray\.from\s*\(')
FABLE_ONE = ('Orchestra: only one Fable critic may run at a time. {why} Wait for the running critic-fable to '
             'finish, then call it again.')
FABLE_SCRIPT = ('Orchestra: a workflow may name {name} once, outside any loop, fan-out or function. {why} Name it in one '
                'agent() call (agentType: "orchestra:critic-fable") at the top level of the script, not inside a function, '
                'map(, forEach(, for (, while (, parallel(, pipeline( or Array.from, or run the critic with the Agent tool.')
FABLE_MODEL = ('Orchestra: the Fable model runs only as orchestra:critic-fable, one at a time. Set '
               'subagent_type to orchestra:critic-fable, or drop the model override.')
GATE_PUSH = ('Orchestra: a push during a run needs the test gate to hold, and it does not yet. {lines} Run the gate '
             '(lean.py gate ...), or record `lean.py gate skip KIND REASON` for a repo with no runner, then push again. '
             '(Owner switch: ORCHESTRA_GATE=off.)')
MATRIX_AGENT = ('Orchestra: during a run every subagent names an orchestra:* agent type (builder, investigator, '
                'reviewer, ...), because an agent with no type or a general-purpose type inherits the main '
                "session's model. Set subagent_type, e.g. orchestra:builder. (Owner switch: ORCHESTRA_MATRIX=off.)")
MATRIX_SCRIPT = ('Orchestra: during a run every agent() in a workflow names an orchestra:* agent type '
                 "(agentType: 'orchestra:builder'), because an agent without a type inherits the main session's "
                 'model. Add agentType to each agent() call. (Owner switch: ORCHESTRA_MATRIX=off.)')


def agent_meta_type(f):
    return lean.read_json(f.with_name(f.stem + '.meta.json')).get('agentType')


def fable_running(event, cwd, session):
    """True when a critic-fable subagent of this session is mid-turn and recently written, or (a critic call was
    allowed in the last FABLE_LOCK_SECONDS and no critic transcript has finished since) the lock file says so."""
    lock = lean.state_dir(cwd, session) / 'fable.lock'
    try:
        locked = time.time() - lock.stat().st_mtime < FABLE_LOCK_SECONDS and lock.stat().st_mtime
    except OSError:
        locked = False
    path = event.get('transcript_path')
    if isinstance(path, str) and path.endswith('.jsonl'):
        try:
            for f in (Path(path[:-len('.jsonl')]) / 'subagents').rglob('agent-*.jsonl'):
                kind = agent_meta_type(f)
                if not isinstance(kind, str) or kind.split(':')[-1] != CRITIC:
                    continue
                st = f.stat()
                if lean.turn_open(f):
                    if time.time() - st.st_mtime < lean.LIVE_WORKER_SECONDS:
                        return True
                elif locked and st.st_mtime >= locked:
                    locked = False  # the critic the lock stands for has finished
        except OSError:
            pass
    return bool(locked)


def in_loop(text, at):
    """True when text[at] sits inside the parentheses or the block of a loop or fan-out call."""
    close = {')': '(', '}': '{'}
    depth = {'(': 0, '{': 0}
    for i in range(at - 1, -1, -1):
        c = text[i]
        if c in close:
            depth[close[c]] += 1
        elif c in depth:
            if depth[c]:
                depth[c] -= 1
                continue
            head = text[:i].rstrip()
            if c == '{' and head.endswith(')'):  # a block: look at the call its header closes
                d, j = 0, len(head) - 1
                while j >= 0:
                    d += (head[j] == ')') - (head[j] == '(')
                    if d == 0:
                        break
                    j -= 1
                head = head[:j].rstrip() + '('
                if LOOP_CALL.search(head[-12:]):
                    return True
            elif c == '(' and LOOP_CALL.search(head[-12:] + '('):
                return True
    return False


def workflow_text(tool_input):
    script = tool_input.get('script')
    if isinstance(script, str):
        return script
    path = tool_input.get('scriptPath')
    if isinstance(path, str):
        try:
            return Path(path).read_text(errors='replace')
        except OSError:
            pass
    return ''


def in_run(cwd, session):
    return os.environ.get('ORCHESTRA_MATRIX') != 'off' and bool(lean.open_asks(cwd, session))


def agent_reason(event, tool_input, cwd, session):
    kind, model = tool_input.get('subagent_type'), tool_input.get('model')
    if kind is not None and not isinstance(kind, str):
        return None, False
    kind = kind or ''
    if kind.split(':')[-1] == CRITIC:
        if fable_running(event, cwd, session):
            return FABLE_ONE.format(why='One is already running in this session.'), True
        return None, True
    if isinstance(model, str) and 'fable' in model.lower():
        return FABLE_MODEL, False
    if kind in ('',) + INHERIT_TYPES and not (isinstance(model, str) and model.strip()) and in_run(cwd, session):
        return MATRIX_AGENT, False
    return None, False


STRING_MARK = re.compile(r'\x00(\d+)\x00')
MODEL_LITERAL = re.compile(r'\bmodel\s*:\s*\x00(\d+)\x00')
CRITIC_LITERAL = re.compile(r'(orchestra:)?' + CRITIC)


def strip_js(text):
    """(code, literals): the script without comments, each string literal (', " or `) replaced by a \\x00n\\x00 mark
    that indexes literals. Template text is taken to the next backtick; ${ } is not parsed."""
    code, literals, i = [], [], 0
    while i < len(text):
        c = text[i]
        if text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            i = len(text) if end < 0 else end + 2
            code.append(' ')
        elif c in '\'"`':
            j = i + 1
            while j < len(text) and text[j] != c:
                j += 2 if text[j] == '\\' else 1
            literals.append(text[i + 1:j])
            code.append(f'\x00{len(literals) - 1}\x00')
            i = j + 1
        else:
            code.append(c)
            i += 1
    return ''.join(code), literals


def agent_calls(code):
    """[(start, end, [top-level argument texts])] for each agent( call."""
    calls = []
    for m in re.finditer(r'(?<![\w$.])agent\s*\(', code):
        args, depth, last, i = [], 0, m.end(), m.end()
        while i < len(code):
            c = code[i]
            if c in '([{':
                depth += 1
            elif c in ')]}':
                if depth == 0:
                    break
                depth -= 1
            elif c == ',' and depth == 0:
                args.append(code[last:i])
                last = i + 1
            i += 1
        args.append(code[last:i])
        calls.append((m.start(), i, [x for x in args if x.strip()]))
    return calls


def in_function(code, at):
    """True when code[at] is an arrow function's expression body or sits inside a function or method body."""
    if code[:at].rstrip().endswith('=>'):
        return True
    close = {')': '(', ']': '[', '}': '{'}
    depth = {'(': 0, '[': 0, '{': 0}
    for i in range(at - 1, -1, -1):
        c = code[i]
        if c in close:
            depth[close[c]] += 1
        elif c in depth:
            if depth[c]:
                depth[c] -= 1
                continue
            head = code[:i].rstrip()
            if head.endswith('=>'):
                return True
            if c == '{' and head.endswith(')'):
                d, j = 0, len(head) - 1
                while j >= 0:
                    d += (head[j] == ')') - (head[j] == '(')
                    if d == 0:
                        break
                    j -= 1
                word = re.search(r'(\w+)$', head[:j].rstrip())
                if (word.group(1) if word else '') not in ('if', 'for', 'while', 'switch', 'catch', 'with', 'await'):
                    return True
    return False


def untyped_agent(calls, code):
    """True when an agent( call has no agentType. Options that are not an inline object (a shared variable) are
    judged by whether agentType appears anywhere in the script."""
    for _, _, args in calls:
        options = args[1].strip() if len(args) > 1 else ''
        if not options or (options.startswith('{') and 'agentType' not in options):
            return True
        if not options.startswith('{') and 'agentType' not in code:
            return True
    return False


def workflow_reason(event, tool_input, cwd, session):
    code, literals = strip_js(workflow_text(tool_input))
    calls = agent_calls(code)
    for m in MODEL_LITERAL.finditer(code):
        if 'fable' in literals[int(m.group(1))].lower():
            return FABLE_MODEL, False
    critics = set()
    for m in STRING_MARK.finditer(code):
        if CRITIC_LITERAL.fullmatch(literals[int(m.group(1))].strip()):
            call = next((c for c in calls if c[0] < m.start() < c[1]), None)
            if call is None:
                return FABLE_SCRIPT.format(name=CRITIC, why='The critic type is written outside an agent() call (a shared '
                                           'variable or options object), where one critic call can be reused many times.'), False
            critics.add(call[0])
    if len(critics) > 1:
        return FABLE_SCRIPT.format(name=CRITIC, why=f'This script names it {len(critics)} times.'), False
    if critics:
        at = min(critics)
        if in_loop(code, at):
            return FABLE_SCRIPT.format(name=CRITIC, why='This script names it inside a loop or fan-out.'), False
        if in_function(code, at):
            return FABLE_SCRIPT.format(name=CRITIC, why='This script names it inside a function, which can run many times.'), False
        if fable_running(event, cwd, session):
            return FABLE_ONE.format(why='One is already running in this session.'), True
    if untyped_agent(calls, code) and in_run(cwd, session):
        return MATRIX_SCRIPT, False
    return None, bool(critics)


def fable_reason(event, tool):
    """(deny reason or None, whether a critic call is allowed through) for an Agent, Task or Workflow call."""
    tool_input = event.get('tool_input')
    if not isinstance(tool_input, dict):
        return None, False
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    check = workflow_reason if tool == 'Workflow' else agent_reason
    reason, critic = check(event, tool_input, cwd, session)
    if critic and not reason:
        try:
            if not lean.git('rev-parse', '--git-common-dir', cwd=cwd):  # no repository: keep the folder clean
                return reason, critic
            lean.state_dir(cwd, session, create=True)
            (lean.state_dir(cwd, session) / 'fable.lock').write_text(str(time.time()))
        except OSError:
            pass
    return reason, critic


def run_active(cwd, session):
    """True when the session has an open ask or an active goal."""
    try:
        if lean.open_asks(cwd, session):
            return True
        return lean.read_json(lean.goal_file(cwd, session)).get('state') == 'active'
    except Exception:
        return False


def push_gate_reason(folders, event):
    """The deny text when a run pushes a branch while the test gate lacks lines; None otherwise (and on any error)."""
    if os.environ.get('ORCHESTRA_GATE') == 'off':
        return None
    session = event.get('session_id') if isinstance(event.get('session_id'), str) else None
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
    try:
        if not run_active(cwd, session):
            return None
        import gate  # lazily: gate imports lean, and lean imports this module
        for folder in dict.fromkeys(folders):
            lines = gate.missing(folder)
            if lines:
                return GATE_PUSH.format(lines=' '.join(lines))
    except Exception:
        return None
    return None


def hook_pre_tool_use(event):
    tool = event.get('tool_name')
    if tool in ('Agent', 'Task', 'Workflow'):
        try:
            reason = fable_reason(event, tool)[0]
        except Exception:  # silent on anything it does not understand
            reason = None
        if reason:
            deny(reason)
        return
    if isinstance(tool, str) and MERGE_TOOL.match(tool):
        reason = 'an MCP pull-request merge'
    elif tool in ('Bash', 'PowerShell'):
        tool_input = event.get('tool_input')
        command = tool_input.get('command') if isinstance(tool_input, dict) else ''
        if not isinstance(command, str):
            return
        cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else None
        pushes = []
        try:
            reason = merge_reason(command, cwd, pushes=pushes)
        except Exception:  # never fail open on a command that may merge or push
            reason = 'a merge or push the guard could not read' if re.search(r'\b(merge|push)\b', command) else None
    else:
        return
    if not reason and pushes:
        gate_reason = push_gate_reason(pushes, event)
        if gate_reason:
            deny(gate_reason)
        return
    if reason:
        deny(f'Orchestra: {reason} is the one step only the owner takes. '
             'Push your branch and open a PR instead; the owner merges.')

