"""The few places where Orchestra touches the operating system rather than Python: file locks, process groups, user ids
and the per-user state location. POSIX uses fcntl and process groups; Windows uses msvcrt locks and taskkill."""
import contextlib
import os
import subprocess
import time

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import msvcrt
else:
    import fcntl


def lock(stream, exclusive=True, blocking=True):
    """Lock an open file. Raises OSError when `blocking` is False and another process holds it. Windows has no shared
    locks here, so a shared request is exclusive there: readers of the run state then take turns."""
    if not IS_WINDOWS:
        flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(stream, flags if blocking else flags | fcntl.LOCK_NB)
        return
    while True:
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if not blocking:
                raise
            time.sleep(0.05)


def unlock(stream):
    """Release a lock taken with `lock`; closing the file also does."""
    if not IS_WINDOWS:
        fcntl.flock(stream, fcntl.LOCK_UN)
        return
    stream.seek(0)
    with contextlib.suppress(OSError):
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def group_kwargs():
    """Popen arguments that put the child in its own process group, so one signal reaches what it starts."""
    if IS_WINDOWS:
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'start_new_session': True}


def kill_group(process):
    """Kill the child and what it started. Raises OSError when there is nothing to kill."""
    if IS_WINDOWS:
        done = subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
        if done.returncode != 0 and process.poll() is None:
            process.kill()
        return
    os.killpg(process.pid, 9)


def group_alive(process):
    """True when something in the child's process group still runs. Windows cannot say, so it reports False."""
    if IS_WINDOWS:
        return False
    try:
        os.killpg(process.pid, 0)
    except OSError:
        return False
    return True


def current_uid():
    """The numeric user id, or None where the system has none (Windows)."""
    return os.getuid() if hasattr(os, 'getuid') else None
