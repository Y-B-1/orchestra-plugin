// TypeScript port of the bounded shell guard in scripts/orchestra_core/guards.py (SPEC 10.3, A5, A8).
//
// The rules table (config/guard-rules.json) and the corpus (config/guard-corpus.json) are shared with
// Python; the corpus is the parity contract. This file holds ALL classifier logic: the guard digest
// covers guard-rules.json, guards.py, hooks.py and this file, so a change here invalidates the marker.
//
// Pure code only: the engine's validator never follows `$` across an import. Not an interpreter, alias
// or hostile-worker sandbox. Known limit: edit protection compares lexical paths (symlinks are not
// resolved here; Python resolves them).

export class ValueError extends Error {}

export type Decision = {
  action: string;
  reason: string;
  category: string;
  remote: string | null;
  target: string | null;
  argv: string[];
  source: string | null;
  boundary: string | null;
};

type Rules = {
  shells: string[];
  shell_value_flags: string[];
  wrappers: Record<string, string[]>;
  tools: { shell: string[]; edit: string[] };
  runners: {
    attached_value_flags: Record<string, string[]>;
    watch_exec_flags: string[];
    flock_command_flags: string[];
    find_exec_actions: string[];
  };
  git: Record<string, string[]>;
  release: {
    gh: string[][];
    az_requires: string[];
    az_pr_update: { prefix: string[]; word: string };
    package_tools: string[];
    package_verb: string;
    deploy_tools: string[];
    deploy_words: string[];
  };
  boundary: { delete_commands: string[]; find_delete_flag: string; gh: string[][] };
  protected: { harness_dirs: string[]; files: string[]; agents_prefixes: string[]; component: string; state_root_exceptions: string[] };
};

const MULTI = 'releasemulti';

let SHELLS = new Set<string>();
let SHELL_VALUE_FLAGS = new Set<string>();
let WRAPPER_VALUES = new Map<string, Set<string>>();
let GIT: Record<string, Set<string>> = {};
let RELEASE: Rules['release'];
let BOUNDARY: Rules['boundary'];
let ATTACHED = new Map<string, Set<string>>();
let EXEC_FLAGS = new Set<string>();
let COMMAND_FLAGS = new Set<string>();
let FIND_EXEC = new Set<string>();
let PROTECTED: Rules['protected'];
let SHELL_TOOLS: string[] = [];
let EDIT_TOOLS: string[] = [];

function strings(value: unknown, what: string): string[] {
  if (!Array.isArray(value) || value.some((x) => (x as unknown) !== String(x) || (typeof x) !== 'string')) throw new ValueError('Invalid guard rules: ' + what);
  return value as string[];
}

/** Install the rules table from the JSON text of config/guard-rules.json. Throws when it is malformed. */
export function loadRules(json: string): void {
  const raw = JSON.parse(json) as Partial<Rules>;
  const need = <T>(value: T | undefined, what: string): T => {
    if (value === undefined || value === null) throw new ValueError('Invalid guard rules: ' + what);
    return value;
  };
  const wrappers = need(raw.wrappers, 'wrappers');
  const runners = need(raw.runners, 'runners');
  const git = need(raw.git, 'git');
  const release = need(raw.release, 'release');
  const boundary = need(raw.boundary, 'boundary');
  const prot = need(raw.protected, 'protected');
  const tools = need(raw.tools, 'tools');
  const shells = new Set(strings(raw.shells, 'shells'));
  const shellFlags = new Set(strings(raw.shell_value_flags, 'shell_value_flags'));
  const wrapperMap = new Map<string, Set<string>>();
  for (const key of Object.keys(wrappers)) wrapperMap.set(key, new Set(strings(wrappers[key], 'wrappers.' + key)));
  const attached = new Map<string, Set<string>>();
  for (const key of Object.keys(need(runners.attached_value_flags, 'runners.attached'))) attached.set(key, new Set(strings(runners.attached_value_flags[key], 'attached')));
  const gitSets: Record<string, Set<string>> = {};
  for (const key of Object.keys(git)) gitSets[key] = new Set(strings(git[key], 'git.' + key));
  for (const key of ['global_value_options', 'clean_value_options', 'push_value_options', 'commit_value_options', 'stash_allowed', 'push_multi_flags', 'switch_force_flags', 'worktree_delete', 'boundary_merge_verbs']) need(gitSets[key], 'git.' + key);
  strings(release.az_requires, 'release.az_requires');
  strings(release.package_tools, 'release.package_tools');
  strings(release.deploy_tools, 'release.deploy_tools');
  strings(release.deploy_words, 'release.deploy_words');
  strings(release.az_pr_update.prefix, 'release.az_pr_update');
  strings(boundary.delete_commands, 'boundary.delete_commands');
  strings(prot.harness_dirs, 'protected.harness_dirs');
  strings(prot.files, 'protected.files');
  strings(prot.agents_prefixes, 'protected.agents_prefixes');
  strings(prot.state_root_exceptions, 'protected.state_root_exceptions');
  const shellTools = strings(tools.shell, 'tools.shell');
  const editTools = strings(tools.edit, 'tools.edit');
  const execFlags = new Set(strings(runners.watch_exec_flags, 'runners.watch_exec_flags'));
  const commandFlags = new Set(strings(runners.flock_command_flags, 'runners.flock_command_flags'));
  const findExec = new Set(strings(runners.find_exec_actions, 'runners.find_exec_actions'));
  SHELLS = shells;
  SHELL_VALUE_FLAGS = shellFlags;
  WRAPPER_VALUES = wrapperMap;
  ATTACHED = attached;
  GIT = gitSets;
  RELEASE = release;
  BOUNDARY = boundary;
  PROTECTED = prot;
  SHELL_TOOLS = shellTools;
  EDIT_TOOLS = editTools;
  EXEC_FLAGS = execFlags;
  COMMAND_FLAGS = commandFlags;
  FIND_EXEC = findExec;
}

export function shellTools(): string[] {
  return SHELL_TOOLS;
}

export function editTools(): string[] {
  return EDIT_TOOLS;
}

// ---------------------------------------------------------------------------------------------
// Python string semantics the classifier depends on.

const PY_WS = '\\t-\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const STRIP_RE = new RegExp('^[' + PY_WS + ']+|[' + PY_WS + ']+$', 'g');
const WS_START_RE = new RegExp('^[' + PY_WS + ']');
const WS_OR_END_RE = new RegExp('^(?:[' + PY_WS + ']|$)');
const DIGITS_RE = /^[\p{Nd}²³¹⁰⁴-⁹₀-₉①-⑨⑴-⑼⒈-⒐⓪⓵-⓽⓿❶-❾➀-➈➊-➒]+$/u;

function strip(text: string): string {
  return text.replace(STRIP_RE, '');
}

function isDigit(text: string): boolean {
  return DIGITS_RE.test(text);
}

function posixName(path: string): string {
  const parts = path.split('/').filter((p) => p !== '' && p !== '.');
  return parts.length ? parts[parts.length - 1]! : '';
}

function quote(text: string): string {
  if (text === '') return "''";
  if (/^[A-Za-z0-9_@%+=:,./-]+$/.test(text)) return text;
  return "'" + text.split("'").join('\'"\'"\'') + "'";
}

/** Python's shlex.split: posix mode, whitespace_split, `#` comments only when asked. */
export function shlexSplit(s: string, comments: boolean): string[] {
  const out: string[] = [];
  const n = s.length;
  let i = 0;
  const WS = ' \t\r\n';
  for (;;) {
    let state: string = ' ';
    let token = '';
    let quoted = false;
    let escapedState = '';
    for (;;) {
      const ch = i < n ? s[i++]! : '';
      if (state === ' ') {
        if (ch === '') break;
        if (WS.includes(ch)) {
          if (token !== '' || quoted) break;
          continue;
        }
        if (comments && ch === '#') {
          const end = s.indexOf('\n', i);
          i = end < 0 ? n : end + 1;
          continue;
        }
        if (ch === '\\') {
          escapedState = 'a';
          state = ch;
        } else if (ch === '"' || ch === "'") {
          state = ch;
        } else {
          token = ch;
          state = 'a';
        }
      } else if (state === '"' || state === "'") {
        quoted = true;
        if (ch === '') throw new ValueError('No closing quotation');
        if (ch === state) state = 'a';
        else if (ch === '\\' && state === '"') {
          escapedState = state;
          state = ch;
        } else token += ch;
      } else if (state === '\\') {
        if (ch === '') throw new ValueError('No escaped character');
        if ((escapedState === '"' || escapedState === "'") && ch !== state && ch !== escapedState) token += state;
        token += ch;
        state = escapedState;
      } else {
        if (ch === '') break;
        if (WS.includes(ch)) {
          state = ' ';
          if (token !== '' || quoted) break;
          continue;
        }
        if (comments && ch === '#') {
          const end = s.indexOf('\n', i);
          i = end < 0 ? n : end + 1;
          state = ' ';
          if (token !== '' || quoted) break;
          continue;
        }
        if (ch === '"' || ch === "'") state = ch;
        else if (ch === '\\') {
          escapedState = 'a';
          state = ch;
        } else token += ch;
      }
    }
    if (!quoted && token === '') return out;
    out.push(token);
  }
}

// ---------------------------------------------------------------------------------------------

function dec(action = 'allow', reason = '', category = '', extra: Partial<Decision> = {}): Decision {
  return { action, reason, category, remote: null, target: null, argv: [], source: null, boundary: null, ...extra };
}

function denyOf(reason: string, category = 'destructiveGit'): Decision {
  return dec('deny', reason, category);
}

/** The SPEC 5.1 class: allow, deny, release, release-multi or boundary. */
export function klassOf(d: Decision): string {
  if (d.boundary) return 'boundary';
  if (d.category === MULTI) return 'release-multi';
  return d.action;
}

type Piece = [string, string];

function split(command: string): Piece[] {
  // Split operators only outside quotes; quoted messages remain ordinary arguments.
  const out: Piece[] = [];
  let start = 0;
  let q: string | null = null;
  let escaped = false;
  for (let i = 0; i < command.length; i++) {
    const char = command[i]!;
    if (escaped) {
      escaped = false;
    } else if (char === '\\' && q !== "'") {
      escaped = true;
    } else if (q) {
      if (char === q) q = null;
    } else if (char === '"' || char === "'") {
      q = char;
    } else if (char === '&' && ((i > 0 && '<>'.includes(command[i - 1]!)) || command.slice(i + 1, i + 2) === '>')) {
      continue;
    } else if (char === '|' && i > 0 && command[i - 1] === '>') {
      continue;
    } else if (';|&()\n'.includes(char)) {
      out.push([command.slice(start, i), char]);
      start = i + 1;
    }
  }
  out.push([command.slice(start), '']);
  return out;
}

function segments(command: string): string[] {
  return split(command).map((p) => p[0]);
}

function pipelines(command: string): string[][] {
  const parts = split(command);
  const out: string[][] = [];
  let current: string[] = [];
  let k = 0;
  while (k < parts.length) {
    const [segment, op] = parts[k]!;
    if (strip(segment)) current.push(segment);
    let join = false;
    if (op === '|' && k + 1 < parts.length) {
      const [following, followingOp] = parts[k + 1]!;
      if (strip(following)) join = true;
      else if (followingOp === '&' || followingOp === '\n') {
        join = true;
        k += 1;
      }
    }
    if (!join && current.length) {
      out.push(current);
      current = [];
    }
    k += 1;
  }
  if (current.length) out.push(current);
  return out;
}

const MARK = '';
const MARK_RE = /<<[0-9]+/g;
const REDIRECT_RE = /^(?:[0-9]*(?:>&|<&|>>|>\||<>|>|<)|&>>?)([^\n]*)$/;
const HEREDOC_RE = /<<(-?)[ \t]*("[^"\n]*"|'[^'\n]*'|\\?[A-Za-z_0-9][A-Za-z_0-9.\-]*)/y;

/** HEREDOC_RE matched at text[i], or null. */
function heredocAt(text: string, i: number): RegExpExecArray | null {
  HEREDOC_RE.lastIndex = i;
  return HEREDOC_RE.exec(text);
}
const ASSIGNMENT_RE = /^[A-Za-z_][A-Za-z0-9_]*=[^\n]*$/;

type Doc = [string, boolean];

function stripHeredocs(command: string): [string, Doc[]] {
  const out: string[] = [];
  const docs: Doc[] = [];
  let pending: [string, boolean, boolean][] = [];
  let q: string | null = null;
  let escaped = false;
  let i = 0;
  const n = command.length;
  while (i < n) {
    const char = command[i]!;
    if (escaped) {
      escaped = false;
    } else if (char === '\\' && q !== "'") {
      escaped = true;
    } else if (q) {
      if (char === q) q = null;
    } else if (char === '"' || char === "'") {
      q = char;
    } else if (char === '<' && command.startsWith('<<', i) && !command.startsWith('<<<', i) && (i === 0 || command[i - 1] !== '<')) {
      HEREDOC_RE.lastIndex = i;
      const match = HEREDOC_RE.exec(command);
      // An all-digit word is shell arithmetic (1 << 2), not a heredoc.
      if (match && !isDigit(match[2]!)) {
        let word = match[2]!;
        const quoted = '\'"\\'.includes(word[0]!);
        word = '\'"'.includes(word[0]!) ? word.slice(1, -1) : word.startsWith('\\') ? word.slice(1) : word;
        pending.push([word, match[1] === '-', quoted]);
        out.push('<<' + MARK + String(docs.length + pending.length - 1) + MARK);
        i = match.index + match[0].length;
        continue;
      }
    } else if (char === '\n') {
      out.push(char);
      i += 1;
      for (const [word, stripTabs, quoted] of pending) {
        const body: string[] = [];
        let found = false;
        while (i < n) {
          const end = command.indexOf('\n', i);
          const line = command.slice(i, end >= 0 ? end : n);
          i = end >= 0 ? end + 1 : n;
          if ((stripTabs ? line.replace(/^\t+/, '') : line) === word) {
            found = true;
            break;
          }
          body.push(line);
        }
        if (!found) throw new ValueError('Heredoc has no terminator');
        docs.push([body.join('\n'), quoted]);
      }
      pending = [];
      continue;
    }
    out.push(char);
    i += 1;
  }
  if (pending.length) throw new ValueError('Heredoc has no terminator');
  return [out.join(''), docs];
}

type Found = { exec: boolean; command: string | null };

function eatOptions(wrapper: string, wordsIn: string[]): [string[], Found] {
  let words = wordsIn;
  const found: Found = { exec: false, command: null };
  const values = WRAPPER_VALUES.get(wrapper)!;
  const attached = ATTACHED.get(wrapper) ?? new Set<string>();
  while (words.length && (words[0]!.startsWith('-') || ASSIGNMENT_RE.test(words[0]!))) {
    const option = words.shift()!;
    if (option === '--') break;
    let value: string | null = null;
    let valueOption = option;
    if (option.startsWith('--') && option.includes('=')) {
      const at = option.indexOf('=');
      valueOption = option.slice(0, at);
      value = option.slice(at + 1);
    } else if (option.startsWith('-') && !option.startsWith('--')) {
      // A value-taking short flag ends the cluster; its suffix is its value.
      for (let i = 1; i < option.length; i++) {
        const char = option[i]!;
        if (attached.has('-' + char)) break;
        if (values.has('-' + char)) {
          valueOption = '-' + char;
          value = option.slice(i + 1) || null;
          break;
        }
        if (wrapper === 'watch' && EXEC_FLAGS.has('-' + char)) found.exec = true;
      }
    }
    if (wrapper === 'watch' && EXEC_FLAGS.has(option)) found.exec = true;
    if (values.has(valueOption)) {
      if (value === null) {
        if (!words.length) throw new ValueError('Missing wrapper option value');
        value = words.shift()!;
      }
      if (wrapper === 'env' && (valueOption === '-S' || valueOption === '--split-string')) {
        words = shlexSplit(value, false).concat(words);
        break;
      }
      if (wrapper === 'flock' && COMMAND_FLAGS.has(valueOption)) found.command = value;
    }
  }
  return [words, found];
}

const RESERVED = new Set(['{', '}', '!', 'if', 'then', 'elif', 'else', 'fi', 'while', 'until', 'do', 'done', 'esac']);

function unwrap(wordsIn: string[]): string[] {
  let words = wordsIn;
  while (words.length) {
    const name = posixName(words[0]!);
    const redirect = REDIRECT_RE.exec(words[0]!);
    if (words[0] === 'case') return [];
    if (words[0] === 'function' && words.length > 1) {
      // `function NAME [()] {`: the name is not a command (SPEC A5, O20).
      words = words.slice(2);
      if (words.length && words[0] === '()') words = words.slice(1);
    } else if (words[0] === 'coproc') {
      // `coproc [NAME] {` or `coproc COMMAND` (SPEC A5, O20).
      words = words.slice(1);
      if (words.length > 1 && words[1] === '{') words = words.slice(1);
    } else if (RESERVED.has(words[0]!)) {
      words = words.slice(1);
    } else if (redirect) {
      words = redirect[1] ? words.slice(1) : words.slice(2);
    } else if (ASSIGNMENT_RE.test(words[0]!)) {
      words = words.slice(1);
    } else if (WRAPPER_VALUES.has(name)) {
      const wrapper = name;
      let found: Found;
      [words, found] = eatOptions(wrapper, words.slice(1));
      if (wrapper === 'timeout' && words.length) {
        words.shift();
      } else if (wrapper === 'watch' && !found.exec && words.length) {
        words = ['sh', '-c', words.join(' ')];
      } else if (wrapper === 'flock') {
        if (found.command === null && words.length) [words, found] = eatOptions(wrapper, words.slice(1));
        if (found.command !== null) words = ['sh', '-c', found.command];
      }
    } else {
      return words;
    }
  }
  return words;
}

function shellPayloadRest(words: string[]): [string, string[]] | null {
  let i = 1;
  while (i < words.length) {
    const token = words[i]!;
    if (token === '--' || !(token.startsWith('-') || token.startsWith('+'))) return null;
    if (SHELL_VALUE_FLAGS.has(token)) {
      i += 2;
      continue;
    }
    if (/^-[A-Za-z]+$/.test(token) && token.slice(1).includes('c')) {
      return i + 1 < words.length ? [words[i + 1]!, words.slice(i + 2)] : ['', []];
    }
    i += 1;
  }
  return null;
}

function shellPayload(words: string[]): string | null {
  const found = shellPayloadRest(words);
  return found ? found[0] : null;
}

function boundaryOf(kind: string, reason: string): Decision {
  return dec('allow', reason, 'boundary', { boundary: kind });
}

function git(words: string[]): Decision {
  let args = words.slice(1);
  let changedRepo = false;
  while (args.length && args[0]!.startsWith('-')) {
    const opt = args.shift()!;
    if (GIT.global_value_options!.has(opt)) {
      if (!args.length) return denyOf('Malformed Git global option', 'malformed');
      args.shift();
    }
    if (opt.startsWith('-C') || opt.startsWith('--git-dir') || opt.startsWith('--work-tree')) changedRepo = true;
  }
  if (!args.length) return dec();
  const verb = args[0]!;
  args = args.slice(1);
  let options = args.includes('--') ? args.slice(0, args.indexOf('--')) : args;
  if (verb === 'clean' || verb === 'push') {
    const valueOptions = verb === 'clean' ? GIT.clean_value_options! : GIT.push_value_options!;
    const filtered: string[] = [];
    let i = 0;
    while (i < options.length) {
      if (valueOptions.has(options[i]!)) i += 2;
      else {
        filtered.push(options[i]!);
        i += 1;
      }
    }
    options = filtered;
  }
  const flags = options.filter((x) => x.startsWith('-'));
  const short = flags.filter((x) => !x.startsWith('--')).map((x) => x.slice(1)).join('');
  const hasFlag = (name: string) => flags.includes(name);
  if (verb === 'stash') {
    if (args.length && GIT.stash_allowed!.has(args[0]!)) return dec();
    return denyOf('Git stash shares state across worktrees', 'stash');
  }
  if (verb === 'reset' && flags.some((x) => x === '--hard' || x.startsWith('--hard='))) return denyOf('Hard reset discards work');
  if (verb === 'clean' && (short.includes('f') || hasFlag('--force')) && !(short.includes('n') || hasFlag('--dry-run'))) return denyOf('Forced clean discards files');
  if (verb === 'branch' && (short.includes('D') || ((short.includes('d') || hasFlag('--delete')) && (short.includes('f') || hasFlag('--force'))))) return denyOf('Forced branch deletion discards refs');
  const wholesale = args.includes('.') || args.includes(':/');
  if (verb === 'checkout' && (wholesale || hasFlag('--force') || short.includes('f'))) return denyOf('Wholesale restore discards work');
  if (verb === 'switch' && (short.includes('f') || [...GIT.switch_force_flags!].some((x) => hasFlag(x)))) return denyOf('Wholesale restore discards work');
  if (verb === 'restore') {
    const stagedOnly = (hasFlag('--staged') || short.includes('S')) && !(hasFlag('--worktree') || short.includes('W'));
    if (hasFlag('--force') || (wholesale && !stagedOnly)) return denyOf('Wholesale restore discards work');
  }
  if (verb === 'add' && (hasFlag('--all') || hasFlag('--update') || short.includes('A') || short.includes('u') || args.includes('.') || args.includes(':/'))) {
    return denyOf('Stage explicit paths only', 'wholesaleStage');
  }
  if (verb === 'commit') {
    // A message beginning with a dash is still a message.
    const opts: string[] = [];
    let i = 0;
    while (i < options.length) {
      const token = options[i]!;
      if (GIT.commit_value_options!.has(token)) {
        i += 2;
        continue;
      }
      if (token.startsWith('--message=') || token.startsWith('--file=') || token.startsWith('-m')) {
        i += 1;
        continue;
      }
      opts.push(token);
      i += 1;
    }
    if (opts.includes('--all') || opts.some((x) => x.startsWith('-') && !x.startsWith('--') && x.slice(1).includes('a'))) {
      return denyOf('Commit explicit staged paths only', 'wholesaleStage');
    }
  }
  if (verb === 'push') {
    if (flags.some((x) => x.startsWith('--force') || x === '--mirror') || short.includes('f') || args.some((x) => x.startsWith('+'))) return denyOf('Force push rewrites remote history');
    const dryRun = hasFlag('--dry-run') || short.includes('n');
    const positional = options.filter((x) => !x.startsWith('-'));
    if (positional.length > 2 || [...GIT.push_multi_flags!].some((x) => hasFlag(x)) || short.includes('d')) return denyOf('Push needs one explicit remote and refspec', 'release');
    let remote: string | null = positional[0] ?? null;
    let target: string | null = positional[1] ?? null;
    let source: string | null = target ? target.split(':', 2)[0]! : null;
    if (target) {
      if (target.startsWith(':') || target.includes('*') || target.split(':').length - 1 > 1) return denyOf('Push needs one non-deleting refspec', 'release');
      const last = target.split(':').pop()!;
      target = last.startsWith('refs/heads/') ? last.slice('refs/heads/'.length) : last;
    }
    if (changedRepo) {
      remote = null;
      target = null;
      source = null;
    }
    if (dryRun) return dec('allow', 'Dry-run push does not release', 'gitpush', { remote, target, argv: words.slice(), source });
    return dec('release', 'Push needs an exact current release permit', 'gitpush', { remote, target, argv: words.slice(), source });
  }
  if (
    verb === 'rm' ||
    (verb === 'branch' && (short.includes('d') || hasFlag('--delete'))) ||
    (verb === 'tag' && (short.includes('d') || hasFlag('--delete'))) ||
    (verb === 'worktree' && args.length > 0 && GIT.worktree_delete!.has(args[0]!))
  ) {
    return boundaryOf('delete', 'Deletion is a boundary action');
  }
  if (GIT.boundary_merge_verbs!.has(verb)) return boundaryOf('merge', 'Local merge is a boundary action');
  return dec();
}

function sameWords(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

function isRelease(name: string, words: string[]): boolean {
  const pair = words.slice(1, 3);
  return (
    (name === 'gh' && RELEASE.gh.some((p) => sameWords(p, pair))) ||
    (name === 'az' &&
      (RELEASE.az_requires.every((x) => words.includes(x)) ||
        (sameWords(words.slice(1, 4), RELEASE.az_pr_update.prefix) && words.includes(RELEASE.az_pr_update.word)))) ||
    (RELEASE.package_tools.includes(name) && words.slice(1).includes(RELEASE.package_verb)) ||
    (RELEASE.deploy_tools.includes(name) && RELEASE.deploy_words.some((x) => words.slice(1).includes(x)))
  );
}

function findExec(words: string[], depth: number): Decision[] {
  const decisions: Decision[] = [];
  let i = 1;
  while (i < words.length) {
    if (FIND_EXEC.has(words[i]!)) {
      let j = i + 1;
      let command: string[] = [];
      while (j < words.length && !(words[j] === ';' || (words[j] === '+' && words[j - 1] === '{}'))) {
        command.push(words[j]!);
        j += 1;
      }
      command = unwrap(command);
      if (command.length) decisions.push(classifySegment(command, depth));
      i = j;
    }
    i += 1;
  }
  return decisions;
}

function firstBySeverity(decisions: Decision[], base: Decision): Decision {
  const tests: ((d: Decision) => boolean)[] = [(d) => d.action === 'deny' && d.category !== MULTI, (d) => d.action === 'release', (d) => !!d.boundary];
  for (const test of tests) for (const d of decisions) if (test(d)) return d;
  return base;
}

function classifySegment(words: string[], depth: number): Decision {
  const name = posixName(words[0]!);
  if (SHELLS.has(name)) {
    const found = shellPayloadRest(words);
    if (found === null) return dec();
    const [payload, rest] = found;
    const decision = classifyCommand(payload, depth + 1);
    if (hardDeny(decision)) return decision;
    // Rule (6b): substitutions in the payload and the arguments after it.
    return scanSubstitutions(payload, depth) ?? scanPieces(rest, depth) ?? decision;
  }
  if (name === 'eval') {
    const text = words.slice(1).join(' ');
    const decision = classifyCommand(text, depth + 1);
    if (hardDeny(decision)) return decision;
    return scanSubstitutions(text, depth) ?? decision;
  }
  if (name === 'git') return git(words);
  if (isRelease(name, words)) return dec('release', 'Provider release needs structured authorization', 'providerrelease', { argv: words.slice() });
  let base = dec();
  const pair = words.slice(1, 3);
  if (BOUNDARY.delete_commands.includes(name) || (name === 'find' && words.slice(1).includes(BOUNDARY.find_delete_flag)) || (name === 'gh' && BOUNDARY.gh.some((p) => sameWords(p, pair)))) {
    base = boundaryOf('delete', 'Deletion is a boundary action');
  }
  if (name === 'find') return firstBySeverity(findExec(words, depth), base);
  return base;
}

function hardDeny(d: Decision): boolean {
  return d.action === 'deny' && d.category !== 'malformed' && d.category !== MULTI;
}

function scanLines(body: string, depth: number, keepRelease = false): Decision {
  let release = dec();
  for (const line of body.split('\\\n').join('').split('\n')) {
    if (!strip(line)) continue;
    const decision = classifyCommand(line, depth + 1);
    if (hardDeny(decision)) return decision;
    if (keepRelease && decision.action === 'release' && release.action === 'allow') release = decision;
  }
  return release;
}

function substitutions(body: string): string[] {
  const found: string[] = [];
  let i = 0;
  const n = body.length;
  while (i < n) {
    const char = body[i]!;
    if (char === '\\') {
      i += 2;
    } else if (body.startsWith('$((', i)) {
      i += 3;
    } else if (body.startsWith('$(', i)) {
      let depth = 1;
      let j = i + 2;
      while (j < n && depth) {
        if (body[j] === '\\') j += 1;
        else if (body[j] === '(') depth += 1;
        else if (body[j] === ')') depth -= 1;
        j += 1;
      }
      const content = body.slice(i + 2, depth === 0 ? j - 1 : j);
      found.push(content);
      found.push(...substitutions(content));
      i = j;
    } else if (char === '`') {
      let j = i + 1;
      while (j < n && body[j] !== '`') j += body[j] === '\\' ? 2 : 1;
      const content = body.slice(i + 1, j);
      found.push(content);
      found.push(...substitutions(content));
      i = j + 1;
    } else {
      i += 1;
    }
  }
  return found;
}

function commandWords(segment: string): string[] {
  const words = unwrap(shlexSplit(segment, true));
  const kept: string[] = [];
  let skip = false;
  for (const word of words) {
    if (skip) {
      skip = false;
      continue;
    }
    const redirect = REDIRECT_RE.exec(word);
    if (redirect) skip = !redirect[1];
    else kept.push(word);
  }
  return kept;
}

function consumerMode(segment: string, allowEval = true): string | null {
  const kept = commandWords(segment);
  if (!kept.length) return null;
  if (SHELLS.has(posixName(kept[0]!))) return shellPayload(kept) !== null ? 'c' : 'script';
  if (kept[0] === '.' || kept[0] === 'source' || (allowEval && kept[0] === 'eval')) return 'script';
  return null;
}

function bodyDecision(body: string, modes: Set<string | null>, depth: number): Decision {
  if (!strip(body)) return dec();
  let decision = classifyCommand(body, depth + 1);
  if (!modes.has('script') && decision.category === 'malformed') decision = scanLines(body, depth, true);
  return decision;
}

const ANSI: Record<string, string> = { a: '\x07', b: '\b', e: '\x1b', E: '\x1b', f: '\f', n: '\n', r: '\r', t: '\t', v: '\v', '\\': '\\', "'": "'", '"': '"', '?': '?' };
const ANSI_NUMERIC: [string, RegExp, number][] = [
  ['x', /[0-9A-Fa-f]{1,2}/y, 16],
  ['u', /[0-9A-Fa-f]{1,4}/y, 16],
  ['U', /[0-9A-Fa-f]{1,8}/y, 16],
];
const ANSI_OCTAL = /[0-7]{1,3}/y;

function matchAt(re: RegExp, text: string, pos: number): string | null {
  re.lastIndex = pos;
  const m = re.exec(text);
  return m ? m[0] : null;
}

function ansiEscape(text: string, i: number): [string, number] {
  const char = text[i + 1]!;
  if (Object.prototype.hasOwnProperty.call(ANSI, char)) return [ANSI[char]!, i + 2];
  try {
    for (const [letter, pattern, base] of ANSI_NUMERIC) {
      const m = char === letter ? matchAt(pattern, text, i + 2) : null;
      if (m) return [String.fromCodePoint(parseInt(m, base)), i + 2 + m.length];
    }
    const m = matchAt(ANSI_OCTAL, text, i + 1);
    if (m) return [String.fromCodePoint(parseInt(m, 8)), i + 1 + m.length];
  } catch {
    // Out of range for a code point: the escape stays literal.
  }
  return ['\\' + char, i + 2];
}

function dollarDecode(text: string): string {
  if (!text.includes("$'")) return text;
  const out: string[] = [];
  let q: string | null = null;
  let escaped = false;
  let i = 0;
  const n = text.length;
  while (i < n) {
    const char = text[i]!;
    if (escaped) {
      escaped = false;
    } else if (char === '\\' && q !== "'") {
      escaped = true;
    } else if (q) {
      if (char === q) q = null;
    } else if (char === '"' || char === "'") {
      q = char;
    } else if (char === '$' && text.startsWith("$'", i)) {
      let j = i + 2;
      const buf: string[] = [];
      while (j < n && text[j] !== "'") {
        if (text[j] === '\\' && j + 1 < n) {
          const [decoded, next] = ansiEscape(text, j);
          buf.push(decoded);
          j = next;
        } else {
          buf.push(text[j]!);
          j += 1;
        }
      }
      if (j >= n) {
        out.push(text.slice(i));
        break;
      }
      out.push(quote(buf.join('')));
      i = j + 1;
      continue;
    }
    out.push(char);
    i += 1;
  }
  return out.join('');
}

function readBalanced(text: string, i: number): number {
  const end = balancedEnd(text, i);
  return end < 0 ? text.length : end;
}

const CASE_PREV = new Set(['if', 'then', 'elif', 'else', 'while', 'until', 'do', '!', '{', 'time']);
const WORD_STOP = ' \t\n;&|()<>"\'\\$`';

/**
 * Index just past the bodies of the heredocs in pending, which start at text[i]. A body that never ends is
 * not skipped (the operator may not have been a heredoc, as in `$((1 << 2))`).
 */
function skipHeredocBodies(text: string, i: number, pending: [boolean, string][]): number {
  let j = i;
  const n = text.length;
  for (const [dash, delimiter] of pending) {
    for (;;) {
      if (j >= n) return i;
      const end = text.indexOf('\n', j);
      const line = text.slice(j, end < 0 ? n : end);
      j = end < 0 ? n : end + 1;
      if ((dash ? line.replace(/^\t+/, '') : line) === delimiter) break;
    }
  }
  return j;
}

function balancedEnd(text: string, start0: number): number {
  let i = start0;
  let depth = 1;
  let q: string | null = null;
  const n = text.length;
  const cases: { state: string; depth: number }[] = [];
  let pending: [boolean, string][] = []; // Heredoc (dash, delimiter) pairs whose bodies start after the next newline (SPEC A5, O20).
  let start = true;
  while (i < n) {
    const char = text[i]!;
    if (char === '\\' && q !== "'") {
      i += 2;
      start = false;
      continue;
    }
    if (q) {
      if (char === q) q = null;
      i += 1;
      continue;
    }
    const last = cases[cases.length - 1];
    const top = last && last.depth === depth ? last : null;
    if (char === '"' || char === "'") {
      q = char;
      start = false;
    } else if (text.startsWith("$'", i)) {
      i += 2;
      while (i < n && text[i] !== "'") i += text[i] === '\\' ? 2 : 1;
      start = false;
    } else if (char === '#' && (i === 0 || ' \t\n;&|()'.includes(text[i - 1]!))) {
      const end = text.indexOf('\n', i);
      i = end < 0 ? n : end;
      continue;
    } else if (char === ' ' || char === '\t') {
      // Blanks neither start nor end a command position.
    } else if (char === '(') {
      if (!(top && top.state === 'pattern')) depth += 1;
      start = true;
    } else if (char === ')') {
      if (top && top.state === 'pattern') {
        top.state = 'body';
      } else {
        depth -= 1;
        if (depth === 0) return i + 1;
      }
      start = true;
    } else if (char === '<' && text.startsWith('<<', i) && !text.startsWith('<<<', i) && (i === 0 || text[i - 1] !== '<') && heredocAt(text, i) !== null) {
      const found = heredocAt(text, i)!;
      pending.push([found[1] !== '', found[2]!.replace(/^["'\\]+|["'\\]+$/g, '')]);
      i = found.index + found[0].length;
      start = false;
      continue;
    } else if (';&|\n'.includes(char)) {
      const two = text.slice(i, i + 2);
      if (top && top.state === 'body' && (two === ';;' || two === ';&')) {
        top.state = 'pattern';
        i += 1;
      } else if (char === '\n' && pending.length) {
        i = skipHeredocBodies(text, i + 1, pending);
        pending = [];
        start = true;
        continue;
      }
      start = true;
    } else if (!'$`<>'.includes(char)) {
      let end = i;
      while (end < n && !WORD_STOP.includes(text[end]!)) end += 1;
      const after = text.slice(end, end + 1);
      const word = after !== '"' && after !== "'" && after !== '\\' && after !== '$' && after !== '`' ? text.slice(i, end) : '';
      if (word === 'in' && top && top.state === 'head') top.state = 'pattern';
      else if (word === 'case' && start) cases.push({ state: 'head', depth });
      else if (word === 'esac' && start && top && top.state !== 'head') cases.pop();
      start = CASE_PREV.has(word);
      i = end;
      continue;
    } else {
      start = false;
    }
    i += 1;
  }
  return -1;
}

function skipDouble(text: string, start: number): number {
  let i = start;
  const n = text.length;
  while (i < n) {
    if (text[i] === '\\') i += 2;
    else if (text[i] === '"') return i + 1;
    else if (text.startsWith('$(', i)) i = readBalanced(text, i + 2);
    else if (text[i] === '`') {
      const close = text.indexOf('`', i + 1);
      i = close < 0 ? n : close + 1;
    } else i += 1;
  }
  return n;
}

function readWord(text: string, start: number): number {
  let i = start;
  const n = text.length;
  while (i < n) {
    const char = text[i]!;
    if (' \t\n;|&<>()'.includes(char)) break;
    if (char === '\\') i += 2;
    else if (char === "'") {
      const close = text.indexOf("'", i + 1);
      i = close < 0 ? n : close + 1;
    } else if (char === '"') i = skipDouble(text, i + 1);
    else if (text.startsWith('$(', i)) i = readBalanced(text, i + 2);
    else if (char === '`') {
      const close = text.indexOf('`', i + 1);
      i = close < 0 ? n : close + 1;
    } else i += 1;
  }
  return Math.min(i, n);
}

type Ops = [[string, string][], [string, string][]];

function scanOps(text: string): Ops {
  const herestrings: [string, string][] = [];
  const procsubs: [string, string][] = [];
  let pending: [string, string, number][] = [];
  let start = 0;
  let q: string | null = null;
  let escaped = false;
  const n = text.length;
  for (let i = 0; i < n; i++) {
    const char = text[i]!;
    if (escaped) {
      escaped = false;
    } else if (char === '\\' && q !== "'") {
      escaped = true;
    } else if (q) {
      if (char === q) q = null;
    } else if (char === '"' || char === "'") {
      q = char;
    } else if (char === '<' && text.startsWith('<<<', i) && (i === 0 || text[i - 1] !== '<')) {
      let j = i + 3;
      while (j < n && ' \t'.includes(text[j]!)) j += 1;
      const end = readWord(text, j);
      pending.push([text.slice(start, i), text.slice(j, end), end]);
    } else if (char === '<' && text.startsWith('<(', i) && (i === 0 || !'<>'.includes(text[i - 1]!))) {
      const close = readBalanced(text, i + 2);
      const inner = text.slice(close - 1, close) === ')' ? text.slice(i + 2, close - 1) : text.slice(i + 2, close);
      procsubs.push([text.slice(start, i), inner]);
    } else if (char === '&' && ((i > 0 && '<>'.includes(text[i - 1]!)) || text.slice(i + 1, i + 2) === '>')) {
      continue;
    } else if (char === '|' && i > 0 && text[i - 1] === '>') {
      continue;
    } else if (';|&()\n'.includes(char)) {
      for (const [before, word, end] of pending) herestrings.push([before + ' ' + (i >= end ? text.slice(end, i) : ''), word]);
      pending = [];
      start = i + 1;
    }
  }
  for (const [before, word, end] of pending) herestrings.push([before + ' ' + text.slice(end), word]);
  return [herestrings, procsubs];
}

function isArithmetic(text: string, i: number): boolean {
  if (!text.startsWith('$((', i)) return false;
  const inner = balancedEnd(text, i + 3);
  return inner < 0 || text.slice(inner, inner + 1) === ')';
}

function rawSubstitutions(text: string, ticks: [boolean, number][] | null = null): [string[], boolean] {
  const found: string[] = [];
  let closed = true;
  let i = 0;
  const n = text.length;
  let inQuote = false;

  const command = (at: number): number => {
    if (ticks !== null) ticks.push([text[at] === '`', at]);
    if (text[at] === '`') {
      let j = at + 1;
      while (j < n && text[j] !== '`') j += text[j] === '\\' ? 2 : 1;
      closed = closed && j < n;
      found.push(text.slice(at + 1, Math.min(j, n)));
      return j + 1;
    }
    const end = balancedEnd(text, at + 2);
    closed = closed && end >= 0;
    found.push(text.slice(at + 2, end < 0 ? n : end - 1));
    return end < 0 ? n : end;
  };

  while (i < n) {
    const char = text[i]!;
    if (char === '\\') {
      i += 2;
    } else if (inQuote) {
      if (char === '"') {
        inQuote = false;
        i += 1;
      } else if (char === '`' || (text.startsWith('$(', i) && !isArithmetic(text, i))) {
        i = command(i);
      } else {
        i += 1;
      }
    } else if (char === "'") {
      const close = text.indexOf("'", i + 1);
      i = close < 0 ? n : close + 1;
    } else if (char === '"') {
      inQuote = true;
      i += 1;
    } else if (isArithmetic(text, i)) {
      i += 3;
    } else if (char === '`' || text.startsWith('$(', i)) {
      i = command(i);
    } else {
      i += 1;
    }
  }
  return [found, closed];
}

function rawCommands(text: string): string[][] {
  const commands: string[][] = [];
  let words: string[] = [];
  let i = 0;
  const n = text.length;
  while (i < n) {
    const char = text[i]!;
    if (char === ' ' || char === '\t') {
      i += 1;
    } else if (char === '#') {
      const end = text.indexOf('\n', i);
      i = end < 0 ? n : end;
    } else if (';|&()\n'.includes(char)) {
      const glued = (char === '&' && ((i > 0 && '<>'.includes(text[i - 1]!)) || text.slice(i + 1, i + 2) === '>')) || (char === '|' && i > 0 && text[i - 1] === '>');
      if (!glued) {
        commands.push(words);
        words = [];
      }
      i += 1;
    } else if (char === '<' || char === '>') {
      let end = i;
      while (end < n && (text[end] === '<' || text[end] === '>')) end += 1;
      words.push(text.slice(i, end));
      i = end;
    } else {
      let end = Math.max(readWord(text, i), i + 1);
      const next = text.slice(end, end + 1);
      if (isDigit(text.slice(i, end)) && (next === '<' || next === '>')) {
        while (end < n && (text[end] === '<' || text[end] === '>')) end += 1;
      }
      words.push(text.slice(i, end));
      i = end;
    }
  }
  commands.push(words);
  return commands.filter((c) => c.length);
}

function rawScan(text: string, depth: number): Decision | null {
  if (depth > 8) return null;
  for (const raws of rawCommands(text)) {
    const values: string[] = [];
    for (const raw of raws) {
      let parts: string[];
      try {
        parts = shlexSplit(raw, false);
      } catch (e) {
        if (!(e instanceof ValueError)) throw e;
        parts = [];
      }
      values.push(parts.length === 1 ? parts[0]! : raw);
    }
    let words: string[];
    try {
      words = unwrap(values);
    } catch (e) {
      if (!(e instanceof ValueError)) throw e;
      continue;
    }
    if (!words.length) continue;
    const name = posixName(words[0]!);
    if (!(name === 'eval' || (SHELLS.has(name) && shellPayloadRest(words) !== null))) continue;
    for (const raw of raws) {
      const [contents, closed] = rawSubstitutions(raw);
      if (!closed) return denyOf('Unbalanced command substitution', 'malformed');
      for (const content of contents) {
        const hit = scanText(content, depth + 1, true);
        if (hit) return hit;
      }
    }
  }
  return null;
}

/**
 * True when the text before a substitution leaves it at command position: after a separator or group
 * opener, with only reserved words and `NAME=value` assignments since (SPEC A5, O20, O23).
 */
function atCommandPosition(before: string): boolean {
  let tail = before;
  for (let k = before.length - 1; k >= 0; k--) {
    if (';&|({\n'.includes(before[k]!)) {
      tail = before.slice(k + 1);
      break;
    }
  }
  let i = 0;
  while (i < tail.length) {
    if (tail[i] === ' ' || tail[i] === '\t') {
      i++;
      continue;
    }
    const end = Math.max(readWord(tail, i), i + 1);
    const word = tail.slice(i, end);
    if (!RESERVED.has(word) && !/^[A-Za-z_][A-Za-z0-9_]*\+?=/.test(word)) return false;
    i = end;
  }
  return true;
}

/**
 * SPEC A5 (O20, O23): a backtick substitution anywhere in the text is a command, as `$(...)` is. The
 * `$(...)` ones are classified by the segment split, except at command position, where (like a
 * backtick there) the substitution's output runs, so its text is producer text.
 */
function backtickScan(text: string, depth: number): Decision | null {
  if (depth > 8) return null;
  const ticks: [boolean, number][] = []; // One [is a backtick, start index] per substitution.
  const [found] = rawSubstitutions(text, ticks);
  for (let k = 0; k < found.length && k < ticks.length; k++) {
    const content = found[k]!;
    const [tick, at] = ticks[k]!;
    let hit: Decision | null;
    if (atCommandPosition(text.slice(0, at))) hit = scanText(content, depth + 1, true); // At command position its output runs.
    else if (!tick) hit = backtickScan(content, depth + 1);
    else hit = classifyCommand(content, depth + 1);
    if (hit && hardDeny(hit)) return hit;
  }
  return null;
}

/** True when the segment is blank or only redirections (`2>/dev/null`, `>&1`, `</dev/stdin`). */
function onlyRedirects(segment: string): boolean {
  let words: string[];
  try {
    words = shlexSplit(segment, false);
  } catch {
    return false;
  }
  let i = 0;
  while (i < words.length) {
    const redirect = REDIRECT_RE.exec(words[i]!);
    if (!redirect) return false;
    i += redirect[1] ? 1 : 2;
  }
  return i <= words.length;
}

function pipeJoins(parts: Piece[], k: number): boolean {
  const following = k + 1 < parts.length ? parts[k + 1]! : null;
  return following !== null && !!(strip(following[0]) || following[1] === '&' || following[1] === '\n' || following[1] === '(');
}

function chains(text: string): string[][] {
  const parts = split(text);
  const out: string[][] = [];
  let cur: string[] = [];
  const frames: { members: string[]; seen: number; feeder: string[] | null }[] = [];
  let carry = false;
  let pipeBefore = false;
  let flushes = 0;

  const flush = () => {
    if (cur.length) {
      for (let f = frames.length - 1; f >= 0; f--) {
        const frame = frames[f]!;
        if (frame.feeder && frame.feeder.length && flushes !== frame.seen) {
          cur = frame.feeder.concat(cur);
          break;
        }
      }
      out.push(cur);
      flushes += 1;
    }
    cur = [];
  };

  // A part holding only redirects and a continuing `|` comes right after parts[k] (O20).
  const pipeFollows = (k: number): boolean => k + 1 < parts.length && onlyRedirects(parts[k + 1]![0]) && parts[k + 1]![1] === '|' && pipeJoins(parts, k + 1);

  for (let k = 0; k < parts.length; k++) {
    const [seg, op] = parts[k]!;
    let s = strip(seg);
    if (carry && !s && (op === '&' || op === '\n')) {
      carry = false;
      continue;
    }
    carry = false;
    if (k && parts[k - 1]![1] === ')' && s && pipeFollows(k - 1)) s = ''; // The redirects of a group that a pipe follows are not a command.
    if (/^\{/.test(s) && WS_OR_END_RE.test(s.slice(1))) {
      s = strip(s.slice(1));
      frames.push({ members: [], seen: flushes, feeder: pipeBefore ? cur.slice() : null });
    }
    const closes = s === '}';
    if (closes) s = '';
    if (s) {
      cur.push(s);
      for (const frame of frames) frame.members.push(s);
    }
    if (closes && frames.length) {
      const frame = frames.pop()!;
      if (flushes !== frame.seen) cur = (frame.feeder ?? []).concat(frame.members);
    }
    if (op === '(') {
      if (!pipeBefore) flush();
      frames.push({ members: [], seen: flushes, feeder: pipeBefore ? cur.slice() : null });
    } else if (op === ')') {
      if (frames.length) {
        const frame = frames.pop()!;
        if (flushes !== frame.seen && pipeFollows(k)) cur = (frame.feeder ?? []).concat(frame.members);
        else if (frame.feeder && frame.feeder.length && flushes !== frame.seen && cur.length) cur = frame.feeder.concat(cur);
      }
      if (!pipeFollows(k)) flush();
    } else if (op === '|' && pipeJoins(parts, k)) {
      carry = !strip(parts[k + 1]![0]) && (parts[k + 1]![1] === '&' || parts[k + 1]![1] === '\n');
      pipeBefore = true;
      continue;
    } else {
      flush();
    }
    pipeBefore = op !== '(' ? false : pipeBefore;
  }
  flush();
  return out;
}

function scanSubstitutions(text: string, depth: number): Decision | null {
  if (depth > 8) return null;
  for (const content of substitutions(text)) {
    const hit = scanText(content, depth + 1, true);
    if (hit) return hit;
  }
  return null;
}

function scanPieces(args: string[], depth: number): Decision | null {
  if (depth > 8 || !args.length) return null;
  for (const word of args) {
    const hit = scanSubstitutions(word, depth);
    if (hit) return hit;
  }
  for (const text of [...args, args.join(' ')]) {
    for (const piece of text.split(/\n|\\n|;/)) {
      if (strip(piece)) {
        const decision = classifyCommand(strip(piece), depth + 1);
        if (hardDeny(decision)) return decision;
      }
    }
  }
  return null;
}

function scanText(textIn: string, depth: number, asCommand = false): Decision | null {
  if (depth > 8) return null;
  const text = dollarDecode(textIn);
  if (asCommand) {
    const decision = classifyCommand(text, depth + 1);
    if (hardDeny(decision)) return decision;
  }
  for (const content of rawSubstitutions(text)[0]) {
    const hit = scanText(content, depth + 1, true);
    if (hit) return hit;
  }
  for (const segment of segments(text)) {
    let words: string[];
    try {
      words = commandWords(segment);
    } catch (e) {
      if (!(e instanceof ValueError)) throw e;
      continue;
    }
    const hit = scanPieces(words.slice(1), depth);
    if (hit) return hit;
  }
  return null;
}

type Item = [Decision, string[], boolean];

function streamItems(text: string, ops: Ops, depth: number): Item[] {
  const items: Item[] = [];
  const [herestrings, procsubs] = ops;

  const consumer = (commandText: string, allowEval: boolean): [string | null, string[]] => {
    try {
      return [consumerMode(commandText, allowEval), commandWords(commandText)];
    } catch (e) {
      if (!(e instanceof ValueError)) throw e;
      return [null, []];
    }
  };

  for (const [commandText, word] of herestrings) {
    const [mode, argv] = consumer(commandText, false);
    if (mode === null) continue;
    let value: string;
    try {
      value = shlexSplit(word, false).join(' ');
    } catch (e) {
      if (!(e instanceof ValueError)) throw e;
      continue;
    }
    items.push([bodyDecision(value, new Set([mode]), depth), argv, false]);
    const hit = scanSubstitutions(value, depth);
    if (hit) items.push([hit, argv, false]);
  }
  for (const [before, inner] of procsubs) {
    const [mode, argv] = consumer(before, false);
    if (mode !== null) {
      const hit = scanText(inner, depth, true);
      if (hit) items.push([hit, argv, false]);
    }
  }
  for (const chain of chains(text)) {
    for (let index = 0; index < chain.length; index++) {
      const [mode, argv] = consumer(chain[index]!, true);
      if (mode === null) continue;
      for (const producer of chain.slice(0, index)) {
        const hit = scanText(producer, depth);
        if (hit) items.push([hit, argv, false]);
      }
      break;
    }
  }
  return items;
}

function heredocItems(docs: Doc[], pipes: string[][], depth: number): Item[] {
  const items: Item[] = [];
  docs.forEach(([body, quoted], index) => {
    const marker = '<<' + MARK + String(index) + MARK;
    let modes = new Set<string | null>();
    let argv: string[] = [];
    for (const pipeline of pipes) {
      const where = pipeline.findIndex((segment) => segment.includes(marker));
      if (where >= 0) {
        argv = shlexSplit(pipeline[where]!, true).map((word) => word.replace(MARK_RE, '<<HEREDOC'));
        modes = new Set(pipeline.slice(where).map((segment) => consumerMode(segment)));
        break;
      }
    }
    if (modes.has('script') || modes.has('c')) items.push([bodyDecision(body, modes, depth), argv, false]);
    if (!quoted) {
      for (const content of substitutions(body)) {
        const decision = classifyCommand(content, depth + 1);
        if (hardDeny(decision)) items.push([decision, argv, false]);
      }
    }
    const decision = scanLines(body, depth);
    if (decision.action === 'deny') items.push([decision, argv, false]);
  });
  return items;
}

function codePointLength(text: string): number {
  if (text.length <= 131072) return text.length;
  let n = 0;
  for (const _ of text) n += 1;
  return n;
}

/** Classify a shell command (SPEC A5). Mirrors guards.classify_command. */
export function classifyCommand(command: string, depth = 0): Decision {
  if (!(typeof command === 'string') || !strip(command) || codePointLength(command) > 131072 || depth > 8) return denyOf('Invalid or excessively nested command', 'malformed');
  const items: Item[] = [];
  try {
    const [stripped, docs] = stripHeredocs(command);
    const text = dollarDecode(stripped);
    const parsed = segments(text)
      .map((segment) => shlexSplit(segment, true).map((word) => word.replace(MARK_RE, '<<HEREDOC')))
      .filter((words) => words.length);
    for (const original of parsed) {
      const words = unwrap(original.slice());
      if (words.length) items.push([classifySegment(words, depth), original, true]);
    }
    items.push(...heredocItems(docs, pipelines(text), depth));
    items.push(...streamItems(text, scanOps(text), depth));
    const rawHit = rawScan(text, depth) ?? backtickScan(text, depth);
    if (rawHit) items.push([rawHit, [], false]);
  } catch (e) {
    if (!(e instanceof ValueError)) throw e;
    return denyOf(e.message.startsWith('Heredoc') ? 'Malformed heredoc' : 'Malformed shell quoting', 'malformed');
  }
  for (const [decision] of items) if (decision.action === 'deny' && decision.category !== MULTI) return decision;
  const total = items.filter((item) => item[2]).length;
  const releases = items.filter((item) => item[0].action === 'release');
  if (items.some((item) => item[0].category === MULTI) || releases.length > 1 || (releases.length && total > 1)) return denyOf('Execute release actions separately', MULTI);
  if (releases.length) return { ...releases[0]![0], argv: releases[0]![1].slice() };
  for (const kind of ['delete', 'merge']) for (const [decision] of items) if (decision.boundary === kind) return decision;
  let result = dec();
  for (const [decision, original] of items) if (decision.category) result = { ...decision, argv: original.slice() };
  return result;
}

// ---------------------------------------------------------------------------------------------
// Edit protection (hooks.py _protected, A8 and A12). Lexical paths: symlinks are not resolved.

export type EditEnv = { stateDir: string | null | undefined; xdg: string | undefined; home: string | undefined };

function expandUser(path: string, home: string | undefined): string {
  if (home && (path === '~' || path.startsWith('~/'))) return home + path.slice(1);
  return path;
}

function resolveParts(base: string, path: string): string[] {
  const joined = path.startsWith('/') ? path : base + '/' + path;
  const parts: string[] = [];
  for (const part of joined.split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') parts.pop();
    else parts.push(part);
  }
  return parts;
}

function startsWithParts(parts: string[], prefix: string[]): boolean {
  return prefix.length <= parts.length && prefix.every((x, i) => parts[i] === x);
}

/** True when an Edit, Write or MultiEdit of `path` (relative to `cwd`) must be denied. */
export function editDenied(path: string | undefined, cwd: string, env: EditEnv): boolean {
  if (!(typeof path === 'string') || path === '') return true;
  const resolved = resolveParts(cwd, path);
  const stateRoot = (root: string[]): boolean | null => {
    if (!startsWithParts(resolved, root)) return null;
    // Coordinator-authored notes at the state root stay writable (A8).
    return !(resolved.length === root.length + 1 && PROTECTED.state_root_exceptions.includes(resolved[resolved.length - 1]!));
  };
  if (env.stateDir) {
    const verdict = stateRoot(resolveParts('/', expandUser(env.stateDir, env.home)));
    if (verdict !== null) return verdict;
  }
  const bases: string[] = [];
  if (env.xdg) bases.push(expandUser(env.xdg, env.home));
  else if (env.home) bases.push(env.home + '/.local/state');
  for (const base of bases) {
    const orchestra = resolveParts('/', base).concat('orchestra');
    if (startsWithParts(resolved, orchestra.concat('mods'))) return true;
    // Without ORCHESTRA_STATE_DIR the run state directory is <base>/orchestra/<24 hex>: protect any such directory.
    if (startsWithParts(resolved, orchestra) && resolved.length > orchestra.length && /^[0-9a-f]{24}$/.test(resolved[orchestra.length]!)) {
      const verdict = stateRoot(orchestra.concat(resolved[orchestra.length]!));
      if (verdict !== null && verdict) return true;
    }
  }
  if (resolved.includes(PROTECTED.component)) return true;
  // Every harness directory in the path counts, not only the first (B-F4).
  for (let i = 0; i < resolved.length; i++) {
    if (!PROTECTED.harness_dirs.includes(resolved[i]!)) continue;
    const tail = resolved.slice(i + 1);
    if (tail.length && (PROTECTED.files.includes(tail[0]!) || (tail[0] === 'agents' && tail.slice(1).some((x) => PROTECTED.agents_prefixes.some((p) => x.startsWith(p)))))) return true;
  }
  return false;
}
