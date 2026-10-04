"""Stable user-level run locations; no application checkout configuration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def repository(cwd):
    return Path(subprocess.check_output(['git','-C',str(cwd),'rev-parse','--show-toplevel'],stderr=subprocess.PIPE).decode().strip()).resolve()


def state_location(repo):
    override = os.environ.get('ORCHESTRA_STATE_DIR')
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))
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
