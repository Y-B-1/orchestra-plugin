"""Receipt-owned Codex agent installation. Never edit global settings or trust."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import fcntl
from contextlib import contextmanager


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


@contextmanager
def receipt_lock(home):
    directory = Path(home) / 'orchestra'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'profiles.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield directory / 'profiles-receipt.json'


def read_receipt(path):
    if not path.exists():
        return {'schema_version': 1, 'files': {}}
    receipt = json.loads(path.read_text())
    if receipt.get('schema_version') != 1 or not isinstance(receipt.get('files'), dict):
        raise ValueError('Invalid profile receipt')
    for name, sha in receipt['files'].items():
        if not name.startswith('orchestra_') or Path(name).name != name or not name.endswith('.toml'):
            raise ValueError('Unsafe receipt filename')
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError('Invalid receipt hash')
    return receipt


def check_owned(home, receipt):
    for name, sha in receipt['files'].items():
        path = Path(home) / 'agents' / name
        if path.is_symlink():
            raise ValueError(f'Profile is a symlink: {name}')
        if path.exists() and digest(path.read_bytes()) != sha:
            raise ValueError(f'Profile changed outside this installer: {name}; preserve or rename it first')


def install(root, home):
    root, home = Path(root).resolve(), Path(home).expanduser().resolve()
    with receipt_lock(home) as receipt_path:
        receipt = read_receipt(receipt_path)
        check_owned(home, receipt)
        files = {}
        for path in sorted((root / 'profiles/codex').glob('orchestra_*.toml')):
            # Replace inside a JSON-escaped TOML string, including Windows separators.
            escaped = json.dumps(str(root))[1:-1]
            files[path.name] = path.read_text().replace('__ORCHESTRA_ROOT__', escaped).encode()
        if not files:
            raise ValueError('No generated profiles found')
        for name in files:
            target = home / 'agents' / name
            if (target.exists() or target.is_symlink()) and name not in receipt['files']:
                raise ValueError(f'Unowned existing profile: {name}')
        # Preflight every collision before making changes. Old receipt remains recoverable on interruption.
        for name, data in files.items():
            atomic(home / 'agents' / name, data)
        for name in receipt['files'].keys() - files.keys():
            (home / 'agents' / name).unlink(missing_ok=True)
        new = {'schema_version': 1, 'plugin_root': str(root),
               'files': {name: digest(data) for name, data in files.items()}}
        atomic(receipt_path, (json.dumps(new, indent=2) + '\n').encode())
        return {'installed': sorted(files), 'receipt': str(receipt_path)}


def uninstall(home):
    home = Path(home).expanduser().resolve()
    with receipt_lock(home) as receipt_path:
        receipt = read_receipt(receipt_path)
        check_owned(home, receipt)
        for name in receipt['files']:
            (home / 'agents' / name).unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return {'removed': sorted(receipt['files'])}
