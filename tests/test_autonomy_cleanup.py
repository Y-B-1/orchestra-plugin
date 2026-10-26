import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_guard_plane as tg


class CleanupFixture(tg.PlaneFixture):
    """Autonomy armed in a real repository on branch `work`; run worktrees live under `.claude/worktrees/`."""

    def setUp(self):
        super().setUp()
        (self.wt / 'own.txt').write_text('own work')  # a commit the repository has not merged
        tg.subprocess.run(['git', '-C', str(self.wt), 'add', 'own.txt'], check=True)
        tg.subprocess.run(['git', '-C', str(self.wt), 'commit', '-qm', 'own'], check=True)
        self.arm()

    def run_worktree(self, name, commit=False):
        path = self.repo / '.claude' / 'worktrees' / name
        self.git('worktree', 'add', '-q', str(path), '-b', 'run-' + name)
        if commit:
            (path / (name + '.txt')).write_text(name)
            tg.subprocess.run(['git', '-C', str(path), 'add', name + '.txt'], check=True)
            tg.subprocess.run(['git', '-C', str(path), 'commit', '-qm', name], check=True)
        return path

    def merge(self, name):
        self.git('merge', '-q', '--no-edit', 'run-' + name)


class WorktreeRemovalTest(CleanupFixture):
    def test_a_merged_clean_run_worktree_is_removed(self):
        self.run_worktree('a2', commit=True)
        self.run_worktree('a', commit=True)
        self.merge('a')
        self.merge('a2')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/a'))
        self.assertIsNone(self.hook('git worktree remove ./.claude/worktrees/a2'))

    def test_a_worktree_at_the_current_head_is_merged(self):
        self.run_worktree('same')
        self.assertIsNone(self.hook('git worktree remove .claude/worktrees/same'))

    def test_an_unmerged_worktree_stays_denied(self):
        self.run_worktree('b', commit=True)
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/b'), 'deny')

    def test_a_dirty_worktree_stays_denied(self):
        path = self.run_worktree('c', commit=True)
        self.merge('c')
        (path / 'untracked.txt').write_text('x')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/c'), 'deny')

    def test_force_stays_denied(self):
        self.run_worktree('d')
        self.assertEqual(self.hook('git worktree remove --force .claude/worktrees/d'), 'deny')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/d --force'), 'deny')

    def test_a_worktree_outside_the_run_directory_stays_denied(self):
        self.assertEqual(self.hook('git worktree remove ' + str(self.wt)), 'deny')

    def test_the_main_checkout_and_the_session_directory_stay_denied(self):
        self.run_worktree('e')
        self.assertEqual(self.hook('git worktree remove .'), 'deny')
        self.assertEqual(self.hook('git worktree remove ' + str(self.repo)), 'deny')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/e', cwd=self.repo / '.claude' / 'worktrees' / 'e'),
                         'deny')

    def test_a_path_that_climbs_out_stays_denied(self):
        self.run_worktree('f')
        self.assertEqual(self.hook('git worktree remove .claude/worktrees/../../../wt'), 'deny')


class TempRemovalTest(CleanupFixture):
    def test_rm_under_the_system_temp_directory_is_allowed(self):
        for command in ('rm -rf /private/tmp/x/y', 'rm -f /tmp/x', 'rm -rf /tmp/x /private/tmp/y',
                        'rm -rf /tmp/x/*.log'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))

    def test_rm_under_tmpdir_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('TMPDIR')
            os.environ['TMPDIR'] = tmp
            try:
                self.assertIsNone(self.hook('rm -f $TMPDIR/a'))
                self.assertIsNone(self.hook('rm -rf ${TMPDIR}/a'))
            finally:
                if old is None:
                    os.environ.pop('TMPDIR')
                else:
                    os.environ['TMPDIR'] = old

    def test_rm_that_leaves_the_temp_directory_stays_denied(self):
        for command in ('rm -rf /tmp/../etc/x', 'rm -rf ~/x', 'rm -rf build /tmp/x', 'rm -rf /tmp', 'rm -rf /tmpx/y',
                        'rm -rf /tmp/../*', 'rm -rf /tmp/*', 'rm -rf /tmp/x/../../etc', 'rm -rf /tmp/x; rm -rf build',
                        'rm -rf /tmp/$(echo ..)/x', 'rm -rf $TMPDIR/../x'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), 'deny')

    def test_a_tmpdir_that_is_unset_or_not_temporary_allows_nothing(self):
        old = os.environ.pop('TMPDIR', None)
        try:
            self.assertEqual(self.hook('rm -f $TMPDIR/a'), 'deny')
        finally:
            if old is not None:
                os.environ['TMPDIR'] = old


if __name__ == '__main__':
    unittest.main()
