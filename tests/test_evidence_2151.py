"""2.15.1 engine evidence: final-review currency after a squash (F96), untracked worktree directories (F90), the
captured report read by token alone (F85) and a reported card re-reported at the review's artifact (F87)."""
import json
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
import test_guard_plane as tgp
import test_review_token as trt
from orchestra_core.engine import EngineError


class SquashFixture(te.HoldFixture):
    def reviewed_branch(self, move_main=False):
        """A final review of a PR branch tip, then the branch squash-merged into main (and deleted)."""
        self.git('switch', '-qc', 'pr')
        (self.repo / 'feature').write_text('feature')
        self.git('add', 'feature')
        self.git('commit', '-qm', 'feature')
        self.reviewed('final-pr', [], final=True, categories=self.ALL)
        self.git('switch', '-q', '-')
        if move_main:
            (self.repo / 'other').write_text('landed on main meanwhile')
            self.git('add', 'other')
            self.git('commit', '-qm', 'other')
        self.git('merge', '-q', '--squash', 'pr')
        self.git('commit', '-qm', 'squash of pr')
        self.git('branch', '-q', '-D', 'pr')


class FinalReceiptAfterSquashTests(SquashFixture):
    def test_a_final_receipt_stays_current_after_its_head_is_squash_merged_with_the_same_tree(self):
        self.reviewed_branch()
        self.engine.check_completion('main', self.lease)

    def test_a_squash_that_changes_the_tree_voids_the_final_receipt(self):
        self.reviewed_branch(move_main=True)
        with self.assertRaisesRegex(EngineError, 'Current final review coverage is incomplete'):
            self.engine.check_completion('main', self.lease)

    def test_a_receipt_head_the_repository_no_longer_holds_is_not_landed(self):
        self.reviewed_branch()
        self.git('reflog', 'expire', '--expire=now', '--all')
        self.git('gc', '-q', '--prune=now')
        with self.assertRaisesRegex(EngineError, 'Current final review coverage is incomplete'):
            self.engine.check_completion('main', self.lease)


class LeftoverWorktreeTests(trt.TokenFixture):
    def lens_receipt(self):
        token = self.lens('l1')
        return token, self.file('f.json', 'orchestra-l1', ['B1', 'l1'])

    def test_an_untracked_linked_worktree_does_not_dirty_a_clean_head_receipt(self):
        self.git('worktree', 'add', '-q', '-b', 'leftover', str(self.repo / '.claude/worktrees/leftover'))
        token, path = self.lens_receipt()
        result = self.engine.review_with_token('main', self.lease, token, path)
        self.assertTrue(result['accepted'], result['refusal'])

    def test_a_real_untracked_file_still_dirties_the_clean_head_receipt(self):
        (self.repo / 'stray.txt').write_text('not committed')
        token, path = self.lens_receipt()
        with self.assertRaises(EngineError):
            self.engine.review_with_token('main', self.lease, token, path)


class ReportedReviewCardTests(trt.TokenFixture):
    def critic_card(self):
        self.task('C1', role='critic', mode='judge', files=[])
        token = self.engine.dispatch('main', self.lease, 'C1', 'orchestra-C1')
        path = self.root / 'c.json'
        self.review(path, reviewer='orchestra-C1', tasks=['B1'])
        body = json.loads(path.read_text())
        body['artifact'] = self.head + ' clean'
        path.write_text(json.dumps(body))
        return token, path

    def test_a_card_reported_beside_a_dirty_sibling_is_accepted_when_its_receipt_is_recorded_clean(self):
        token, path = self.critic_card()
        (self.repo / 'sibling.txt').write_text('a sibling is mid-edit')
        self.engine.report('orchestra-C1', token, path.read_text())  # what the Stop hook did
        (self.repo / 'sibling.txt').unlink()
        result = self.engine.review_with_token('main', self.lease, token, path)
        self.assertEqual((True, None), (result['accepted'], result['refusal']))
        self.assertEqual('accepted', self.engine.status()['tasks']['C1']['state'])

    def test_a_reported_card_whose_report_differs_from_the_receipt_keeps_its_old_artifact(self):
        token, path = self.critic_card()
        (self.repo / 'sibling.txt').write_text('a sibling is mid-edit')
        self.engine.report('orchestra-C1', token, 'Judged beside a dirty sibling.')
        (self.repo / 'sibling.txt').unlink()
        result = self.engine.review_with_token('main', self.lease, token, path)
        self.assertFalse(result['accepted'])
        self.assertIn('stale', result['refusal'])


class TokenOnlyReviewTests(trt.TokenFixture):
    def test_review_by_token_alone_reads_the_captured_report(self):
        token = self.lens('l1')
        path = self.file('f.json', 'orchestra-l1', ['B1', 'l1'])
        reports = self.engine.state_dir / 'reports'
        reports.mkdir(parents=True, exist_ok=True)
        (reports / (token + '.md')).write_text(path.read_text())
        code, out, err = te.run_cli(self, '--lease', self.lease, 'review', '--token', token)
        self.assertEqual((0, ''), (code, err), out)
        self.assertEqual('accepted', self.engine.status()['tasks']['l1']['state'])

    def test_without_a_captured_report_the_refusal_names_the_missing_file(self):
        token = self.lens('l1')
        code, out, err = te.run_cli(self, '--lease', self.lease, 'review', '--token', token)
        self.assertNotEqual(0, code)
        self.assertIn('Review report not found', err + out)

    def test_a_path_that_climbs_out_of_the_reports_directory_is_not_a_token(self):
        code, out, err = te.run_cli(self, '--lease', self.lease, 'review', '--token', '../state')
        self.assertNotEqual(0, code)
        self.assertIn('Invalid review token', err + out)

    def test_review_without_a_path_or_a_token_is_refused(self):
        code, out, err = te.run_cli(self, '--lease', self.lease, 'review')
        self.assertNotEqual(0, code)
        self.assertIn('review needs a report path or --token', err + out)


class TokenOnlyGuardTests(tgp.PlaneFixture):
    def test_the_token_only_review_is_allowed_and_reading_the_captured_report_is_still_denied_while_locked(self):
        self.arm()
        cli = 'python3 /opt/orchestra/scripts/orchestra.py --repo %s --lease L review --token T1'
        self.assertIsNone(self.hook(cli % self.repo))
        self.assertEqual('deny', self.hook('cat %s/reports/T1.md' % self.state))


if __name__ == '__main__':
    unittest.main()
