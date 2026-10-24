"""F47: a repaired ancestor accepts once its repair is accepted after a CLEAN fix re-review, although its own report
names file content that the repair (and later commits on shared files) changed."""
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import EngineError


class RepairedAncestorTests(te.EngineFixture):
    LENSES = te.FixReviewTests.LENSES
    reviewed = te.FixReviewTests.reviewed
    final = te.FixReviewTests.final

    def setUp(self):
        super().setUp()
        self.allow_review()

    def committed(self, name, content):
        """A builder card for file `name`, committed in the run checkout and reported with that commit."""
        self.task(name, files=[name])
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        (self.repo / name).write_text(content)
        self.git('add', name)
        self.git('commit', '-qm', 'built ' + name)
        sha = self.git('rev-parse', 'HEAD').strip()
        self.engine.report('w-' + name, token, te.done('Built ' + name).replace('ARTIFACT: fixture', 'ARTIFACT: %s clean' % sha))

    def repaired_chain(self, recheck=True):
        self.committed('B1', 'first')
        self.committed('B2', 'other')
        self.engine.accept('main', self.lease, 'B1')  # accepted before the pre-PR review, as a wave card is
        self.engine.accept('main', self.lease, 'B2')
        (self.repo / 'B1').write_text('first, extended by a later card')  # a later card commits to the shared file
        self.git('add', 'B1')
        self.git('commit', '-qm', 'later card on B1')
        self.final('final', findings=['f'], task_findings={'B1': ['f'], 'B2': []})
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        token = self.engine.dispatch('main', self.lease, 'R1', 'r1')
        # The repair is built in a linked worktree and reported before it is merged, as a Workflow repair is.
        side = self.root / 'side'
        self.git('worktree', 'add', '-q', '-b', 'side', str(side))
        (side / 'B1').write_text('repaired')
        side_git = lambda *a: subprocess.check_output(['git', '-C', str(side), *a], text=True).strip()
        side_git('commit', '-qam', 'repair B1')
        sha = side_git('rev-parse', 'HEAD')
        self.engine.report('r1', token, te.done('Repaired').replace('ARTIFACT: fixture', 'ARTIFACT: %s clean' % sha))
        self.git('merge', '-q', '--ff-only', 'side')
        if recheck:
            self.reviewed('check', ['R1', 'B1'], repair_check=True)
            self.engine.accept('main', self.lease, 'R1')

    def test_the_repaired_ancestor_accepts_after_its_repair(self):
        self.repaired_chain()
        self.engine.accept('main', self.lease, 'B1')
        self.assertEqual('accepted', self.engine.status()['tasks']['B1']['state'])

    def test_without_a_clean_fix_re_review_the_ancestor_stays_refused(self):
        self.repaired_chain(recheck=False)
        with self.assertRaisesRegex(EngineError, 'repair must be accepted first'):
            self.engine.accept('main', self.lease, 'B1')

    def test_a_card_without_a_repair_still_refuses_a_changed_file(self):
        self.committed('B1', 'first')
        (self.repo / 'B1').write_text('changed later')
        self.git('add', 'B1')
        self.git('commit', '-qm', 'later change')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'B1')


if __name__ == '__main__':
    unittest.main()
