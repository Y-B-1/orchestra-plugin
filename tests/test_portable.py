import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))

from orchestra_core import paths, portable  # noqa: E402

POSIX = os.name != 'nt'


class FakeMsvcrt:
    """Stands in for msvcrt so the Windows branch runs anywhere: the first `busy` lock attempts raise OSError."""
    LK_NBLCK, LK_UNLCK = 2, 0

    def __init__(self, busy=0):
        self.busy, self.calls = busy, []

    def locking(self, fd, mode, nbytes):
        self.calls.append((mode, nbytes))
        if mode == self.LK_NBLCK and self.busy > 0:
            self.busy -= 1
            raise OSError('locked')


class LockTest(unittest.TestCase):
    @unittest.skipUnless(POSIX, 'flock')
    def test_a_second_nonblocking_lock_on_posix_raises_until_the_first_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'l')
            with path.open('a+') as one, path.open('a+') as two:
                portable.lock(one)
                with self.assertRaises(OSError):
                    portable.lock(two, blocking=False)
                portable.unlock(one)
                portable.lock(two, blocking=False)

    @unittest.skipUnless(POSIX, 'flock')
    def test_shared_locks_coexist_on_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'l')
            with path.open('a+') as one, path.open('a+') as two:
                portable.lock(one, exclusive=False)
                portable.lock(two, exclusive=False, blocking=False)

    def test_the_windows_branch_retries_a_busy_lock_and_raises_when_not_blocking(self):
        fake = FakeMsvcrt(busy=3)
        with tempfile.TemporaryFile('a+') as stream, mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.object(portable, 'msvcrt', fake, create=True), mock.patch.object(portable.time, 'sleep'):
            portable.lock(stream)  # blocks through three busy answers, then holds
            self.assertEqual(len(fake.calls), 4)
            fake.busy = 1
            with self.assertRaises(OSError):
                portable.lock(stream, blocking=False)
            portable.unlock(stream)
            self.assertEqual(fake.calls[-1], (FakeMsvcrt.LK_UNLCK, 1))

    def test_a_shared_request_is_exclusive_on_windows(self):
        fake = FakeMsvcrt()
        with tempfile.TemporaryFile('a+') as stream, mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.object(portable, 'msvcrt', fake, create=True):
            portable.lock(stream, exclusive=False)
        self.assertEqual(fake.calls, [(FakeMsvcrt.LK_NBLCK, 1)])


class ProcessGroupTest(unittest.TestCase):
    def test_group_kwargs_name_the_platform_flag(self):
        self.assertEqual(portable.group_kwargs(), {'start_new_session': True} if POSIX
                         else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP})
        with mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, create=True):
            self.assertEqual(portable.group_kwargs(), {'creationflags': 512})

    @unittest.skipUnless(POSIX, 'process groups')
    def test_kill_group_stops_a_child_and_what_it_started(self):
        process = subprocess.Popen([sys.executable, '-c', 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); time.sleep(60)'],
                                   **portable.group_kwargs())
        self.assertTrue(portable.group_alive(process))
        portable.kill_group(process)
        process.wait(timeout=10)
        for _ in range(100):
            if not portable.group_alive(process):
                break
            subprocess.run([sys.executable, '-c', 'import time; time.sleep(0.05)'])
        self.assertFalse(portable.group_alive(process))

    def test_windows_kills_the_tree_with_taskkill_and_cannot_see_a_group(self):
        process = mock.Mock(pid=4242)
        with mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.object(portable.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            portable.kill_group(process)
            self.assertEqual(run.call_args[0][0], ['taskkill', '/F', '/T', '/PID', '4242'])
            self.assertFalse(portable.group_alive(process))
        with mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.object(portable.subprocess, 'run', return_value=mock.Mock(returncode=128)):
            process.poll.return_value = None
            portable.kill_group(process)
            process.kill.assert_called_once()  # taskkill failed: fall back to the child alone


class StateLocationTest(unittest.TestCase):
    def test_windows_uses_localappdata_when_xdg_is_unset(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.dict(os.environ, {'XDG_STATE_HOME': '', 'LOCALAPPDATA': tmp}):
            self.assertEqual(paths.state_home(), Path(tmp))

    def test_an_absolute_xdg_state_home_wins_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(portable, 'IS_WINDOWS', True), \
                mock.patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'LOCALAPPDATA': '/elsewhere'}):
            self.assertEqual(paths.state_home(), Path(tmp))

    def test_without_a_numeric_uid_the_fallback_root_is_named_for_the_user(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(paths.tempfile, 'gettempdir', return_value=tmp), \
                mock.patch.object(portable, 'current_uid', return_value=None), \
                mock.patch.dict(os.environ, {'USERNAME': 'Ada Lovelace'}):
            root = paths._private_temp_root()
        self.assertEqual(root.name, 'orchestra-state-Ada_Lovelace')


class WindowsJobTest(unittest.TestCase):
    @unittest.skipIf(POSIX, 'job objects exist only on Windows')
    def test_a_job_sees_and_kills_a_process_the_child_left_running(self):
        code = ('import subprocess, sys\n'
                'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], close_fds=True)\n')
        process = subprocess.Popen([sys.executable, '-c', code], **portable.group_kwargs())
        portable.track(process)
        self.addCleanup(portable.release, process)
        process.wait(timeout=30)
        self.assertTrue(portable.group_alive(process))  # the grandchild outlived its parent
        portable.kill_group(process)
        for _ in range(100):
            if not portable.group_alive(process):
                break
            time.sleep(0.05)
        self.assertFalse(portable.group_alive(process))

    def test_track_and_release_are_harmless_without_a_job(self):
        process = mock.Mock(pid=1)
        with mock.patch.object(portable, 'IS_WINDOWS', False):
            portable.track(process)
        portable.release(process)  # nothing was tracked: no error


class LauncherTest(unittest.TestCase):
    @unittest.skipUnless(POSIX, 'sh')
    def test_run_hook_sh_starts_the_hook_in_utf8_mode_and_survives_a_missing_python(self):
        launcher = Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/run-hook.sh'
        done = subprocess.run(['sh', str(launcher), 'Stop', '--harness', 'claude'], input='{"cwd": "/nonexistent"}',
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        text = launcher.read_text()
        self.assertIn('-X utf8', text)
        self.assertIn("tr '\\\\' '/'", text)  # a backslash $0 (Git Bash on Windows) is split on forward slashes
        self.assertIn('case "$orchestra_self" in', text)  # and only then: no extra command on the common path
        self.assertIn('py "-$orchestra_version"', text)  # the Windows launcher is a candidate


if __name__ == '__main__':
    unittest.main()
