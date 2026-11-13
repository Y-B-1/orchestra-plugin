"""Shared test helpers: git, a cheap repo, the hook runner, transcript and worker builders."""
import atexit, io, json, os, shutil, subprocess, sys, tempfile, time, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
LEAN = ROOT / 'scripts/lean.py'
sys.path.insert(0, str(ROOT / 'scripts'))
import lean  # noqa: E402

_template = None


def git(cwd, *args):
    """Run git in cwd, fail the test on a non-zero exit, and return stdout without the trailing newline."""
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(path, origin=False):
    """A repo at path with one empty commit on main. With origin, a bare clone source sits beside it, pushed and tracked.
    The repo is copied from a template built once per process: one `git init` and commit, not one per test."""
    global _template
    if _template is None:
        _template = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, _template, True)
        git(_template, 'init', '-q', '-b', 'main', '--template=')  # no sample hooks to copy
        git(_template, 'config', 'user.email', 't@example.com')
        git(_template, 'config', 'user.name', 'T')
        git(_template, 'config', 'maintenance.auto', 'false')  # the commit's background `git maintenance` holds
        git(_template, 'config', 'gc.auto', '0')  # objects/maintenance.lock while the template is copied
        git(_template, 'commit', '-q', '--allow-empty', '-m', 'init')
    shutil.copytree(_template, path, symlinks=True)
    if origin:
        bare = Path(path).parent / 'origin.git'
        git(path.parent, 'init', '-q', '--bare', '-b', 'main', str(bare))
        git(path, 'remote', 'add', 'origin', str(bare))
        git(path, 'push', '-q', '-u', 'origin', 'main')
    return Path(path)


class RepoCase(unittest.TestCase):
    """A fresh repo per test (self.repo, a `sub` folder inside it, self.cwd), a private copy of os.environ, and the PreToolUse
    and Stop hooks run in process. Set ORIGIN to give the repo a pushed origin."""
    ORIGIN = False

    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(lean.SESSION_ENV, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_repo(Path(self.tmp.name) / 'repo', self.ORIGIN)
        (self.repo / 'sub').mkdir()
        self.cwd = str(self.repo)

    def hook(self, name, event):
        event.setdefault('cwd', self.cwd)
        out = io.StringIO()
        with redirect_stdout(out):
            {'stop': lean.hook_stop, 'pre-tool-use': lean.hook_pre_tool_use}[name](event)
        text = out.getvalue().strip()
        return json.loads(text) if text else None

    def bash(self, command, **event):
        return self.hook('pre-tool-use', {'tool_name': 'Bash', 'tool_input': {'command': command}, **event})


def transcript(base, worker_age=None, finished=False, journal=None):
    """A session transcript path under base; with worker_age, one workflow subagent transcript last written that many
    seconds ago, whose last assistant turn is finished (end_turn) or still in a tool call."""
    path = Path(base) / 'session.jsonl'
    path.write_text('')
    if worker_age is not None:
        sub = Path(base) / 'session' / 'subagents' / 'workflows' / 'w1'
        sub.mkdir(parents=True, exist_ok=True)
        f = sub / 'agent-a1.jsonl'
        stop = 'end_turn' if finished else 'tool_use'
        f.write_text(json.dumps({'type': 'assistant', 'message': {'role': 'assistant', 'stop_reason': stop}}) + '\n'
                     + json.dumps({'type': 'attachment'}) + '\n')
        when = time.time() - worker_age
        os.utime(f, (when, when))
        if journal is not None:  # what a Workflow writes beside its agents: launched/started/result rows
            (sub / 'journal.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in journal))
    return str(path)


def worker(transcript_path, type_, stop='tool_use', age=0):
    """One subagent of the given type beside a transcript: its last turn's stop reason, last written `age` seconds ago."""
    d = Path(transcript_path).with_suffix('') / 'subagents'
    d.mkdir(parents=True, exist_ok=True)
    f = d / f'agent-{type_.replace(":", "-")}.jsonl'
    f.write_text(json.dumps({'type': 'assistant', 'message': {'stop_reason': stop}}) + '\n')
    (d / (f.stem + '.meta.json')).write_text(json.dumps({'agentType': type_}))
    os.utime(f, (time.time() - age, time.time() - age))
