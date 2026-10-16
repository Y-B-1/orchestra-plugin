"""Stable user-level run locations; no application checkout configuration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def repository(cwd):
    return Path(subprocess.check_output(['git','-C',str(cwd),'rev-parse','--show-toplevel'],stderr=subprocess.PIPE).decode().strip()).resolve()


class StateRootError(Exception):
    """The fallback state root is unusable. Not an OSError, so run discovery cannot mistake it for 'no run'."""


def _private_temp_root():
    """A per-user 0700 directory owned by this uid under the system temp folder; refuses a root another user made."""
    root = Path(tempfile.gettempdir()) / ('orchestra-state-%d' % os.getuid())
    try:
        root.mkdir(mode=0o700, exist_ok=True)
        info = root.lstat()
    except OSError as exc:
        raise StateRootError('Fallback state directory %s cannot be created: %s' % (root, exc)) from None
    if root.is_symlink() or info.st_uid != os.getuid():
        raise StateRootError('Fallback state directory %s is not owned by this user' % root)
    if info.st_mode & 0o077:
        try:
            root.chmod(0o700)
            tightened = root.lstat().st_mode & 0o077
        except OSError as exc:
            raise StateRootError('Fallback state directory %s cannot be made private: %s' % (root, exc)) from None
        if tightened:
            raise StateRootError('Fallback state directory %s is not private' % root)
    return root


def state_home():
    """XDG_STATE_HOME when it is absolute (the XDG rule, as the mod reads it), else ~/.local/state."""
    value = os.environ.get('XDG_STATE_HOME', '')
    if os.path.isabs(value):
        return Path(value)
    try:
        return Path.home() / '.local/state'
    except RuntimeError:  # No HOME and no passwd entry (a container run as an arbitrary uid): a private temp location
        return _private_temp_root()


def push_url_digest(url):
    """What arm records of a push URL: a digest, since a remote URL can carry a token that `status` would print."""
    return 'sha256:' + hashlib.sha256(url.encode()).hexdigest()


def state_location(repo):
    override = os.environ.get('ORCHESTRA_STATE_DIR')
    if override:
        return Path(override).expanduser().resolve()
    base = state_home()
    identity = hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:24]
    return base / 'orchestra' / identity


def load_policy(state_dir):
    path = Path(state_dir)/'policy.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if not isinstance(data,dict) or data.get('schema_version') != 1:
        raise ValueError('Invalid project policy')
    return data


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.orchestra-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
