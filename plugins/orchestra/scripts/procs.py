"""What the gate needs from the operating system: whether a pid lives, and one exclusive lock on both Windows and POSIX."""
import contextlib, os, time

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

LOCK_WAIT = 60.0  # seconds a Windows lock is retried before the run goes on without it, as when a filesystem has no locks


def alive(pid):
    """Whether a process with this pid exists. os.kill(pid, 0) is no probe on Windows: signal 0 is CTRL_C_EVENT there and
    interrupts the process group (the caller), so Windows asks the process table instead. pid <= 0 is never a process."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except PermissionError:  # owned by someone else, still exists
            return True
        except OSError:
            return False
        return True
    import ctypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    k32.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
    k32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() == 5  # access denied: it exists
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
    k32.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


@contextlib.contextmanager
def exclusive(path):
    """Hold an exclusive lock on the file at path (created if missing) until the block ends."""
    with open(path, 'a') as lock:
        held = False
        try:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
                held = True
            elif msvcrt:
                deadline = time.monotonic() + LOCK_WAIT
                while not held:
                    try:
                        lock.seek(0)
                        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)  # retries about 10 s, then raises
                        held = True
                    except OSError:
                        if time.monotonic() > deadline:
                            break
        except OSError:  # no lock support here (a network filesystem): the unique temp file in lean.write_json still keeps the file whole
            pass
        try:
            yield
        finally:
            if held and msvcrt:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
