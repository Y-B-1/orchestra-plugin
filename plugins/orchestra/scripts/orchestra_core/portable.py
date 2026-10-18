"""The few places where Orchestra touches the operating system rather than Python: file locks, process groups, user ids
and the per-user state location. POSIX uses fcntl and process groups; Windows uses msvcrt locks and taskkill."""
import contextlib
import os
import subprocess
import time

IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import ctypes
    import msvcrt
    from ctypes import wintypes
else:
    import fcntl

_JOBS = {}  # Windows: child pid -> job object handle, for children put under track()


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


def _job_api():
    """kernel32 with the argument types the job calls need, or None where ctypes cannot load it."""
    try:
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateJobObjectW.restype = wintypes.HANDLE
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        return api
    except (OSError, AttributeError):
        return None


class _BasicAccounting(ctypes.Structure if IS_WINDOWS else object):
    if IS_WINDOWS:
        _fields_ = [('times', ctypes.c_longlong * 4), ('TotalPageFaultCount', wintypes.DWORD),
                    ('TotalProcesses', wintypes.DWORD), ('ActiveProcesses', wintypes.DWORD),
                    ('TotalTerminatedProcesses', wintypes.DWORD)]


def track(process):
    """Windows: put the child in a job object, so everything it starts stays reachable after it exits and a
    leftover can be found and killed (a process group cannot do that there). POSIX needs nothing: its group does it.
    The job also dies with this process (kill-on-close), so a crashed engine leaves no gate children running."""
    if not IS_WINDOWS:
        return
    api = _job_api()
    if api is None:
        return
    job = api.CreateJobObjectW(None, None)
    if not job:
        return
    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION: 64 bytes basic (limit flags at offset 16) + 48 bytes io + 4 x size_t.
    info = (ctypes.c_ubyte * (144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 112))()
    ctypes.c_ulong.from_buffer(info, 16).value = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    api.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    if api.AssignProcessToJobObject(job, int(process._handle)):
        _JOBS[process.pid] = (api, job)
    else:
        api.CloseHandle(job)


def release(process):
    """Windows: drop the job handle taken by track(); closing it kills anything still in the job."""
    entry = _JOBS.pop(process.pid, None)
    if entry:
        entry[0].CloseHandle(entry[1])


def kill_group(process):
    """Kill the child and what it started. Raises OSError when there is nothing to kill."""
    if IS_WINDOWS:
        entry = _JOBS.get(process.pid)
        if entry and entry[0].TerminateJobObject(entry[1], 1):
            return
        done = subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
        if done.returncode != 0 and process.poll() is None:
            process.kill()
        return
    os.killpg(process.pid, 9)


def group_alive(process):
    """True when something in the child's process group (on Windows, its job) still runs. A Windows child that was
    not put under track() cannot be inspected, so it reports False."""
    if IS_WINDOWS:
        entry = _JOBS.get(process.pid)
        if not entry:
            return False
        info = _BasicAccounting()
        if not entry[0].QueryInformationJobObject(entry[1], 1, ctypes.byref(info), ctypes.sizeof(info), None):
            return False
        return info.ActiveProcesses > 0
    try:
        os.killpg(process.pid, 0)
    except OSError:
        return False
    return True


def current_uid():
    """The numeric user id, or None where the system has none (Windows)."""
    return os.getuid() if hasattr(os, 'getuid') else None
