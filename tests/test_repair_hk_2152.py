"""2.15.2 repair RH (RWS on HK): a temp glob is judged against the Claude temp tree whatever $TMPDIR is, a $TMPDIR
operand is never relieved, and a glob that could take Claude Code's `cc-` sockets is denied."""
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'plugins/orchestra/scripts'))

from orchestra_core import hooks


UID = 'claude-%d' % os.getuid()


class TempTreeTests(unittest.TestCase):
    def judge(self, command, tmpdir):
        with mock.patch.dict(os.environ, {'TMPDIR': tmpdir}):
            return hooks._rm_in_temp(command)

    def test_a_tmpdir_inside_the_claude_temp_tree_adds_no_root(self):
        tmpdir = '/private/tmp/' + UID
        for command in ('rm -rf /private/tmp/%s/-*' % UID, 'rm -rf $TMPDIR/-*', 'rm -rf ${TMPDIR}/-*'):
            with self.subTest(command=command):
                self.assertFalse(self.judge(command, tmpdir))

    def test_a_tmpdir_operand_is_never_relieved(self):
        # the shell that runs the command may use another $TMPDIR than the hook (a sandboxed shell exports its own)
        self.assertFalse(self.judge('rm -rf $TMPDIR/x', '/var/folders/ab/cd/T'))

    def test_a_glob_that_could_take_claude_code_sockets_is_denied(self):
        for command in ('rm -rf /tmp/cc*', 'rm -rf /tmp/c*', 'rm -rf /private/tmp/CC-*'):
            with self.subTest(command=command):
                self.assertFalse(self.judge(command, '/var/folders/ab/cd/T'))

    def test_plain_temp_files_and_the_system_tmpdir_stay_allowed(self):
        for command in ('rm -f /tmp/foo*.log', 'rm -rf /tmp/x/y', 'rm -rf /var/folders/ab/cd/T/orchestra-check.X1'):
            with self.subTest(command=command):
                self.assertTrue(self.judge(command, '/var/folders/ab/cd/T'))


if __name__ == '__main__':
    unittest.main()
