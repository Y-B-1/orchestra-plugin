"""2.15.3 engine: a resumed card's range skips the commits made while it was reported (F112), a repair reserves only
its own files and the files its finding names (F114), and a newline is never the gap before a trailing note (RY)."""
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
import test_engine_2152 as t2
import test_refusal_texts as tr
from test_refusal_texts import report_for
from orchestra_core.engine import Engine, EngineError


class ResumeGapTests(tr.RefusalFixture):
    def test_a_commit_made_while_the_card_was_reported_is_not_its_own(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first')))
        sibling = self.running('b', files=['b_file', 'shared'])
        self.engine.report('w-b', sibling, tr.report_for(self.commit(b_file='by b', shared='by b')))
        self.engine.accept('main', self.lease, 'b')
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.own_add('main', self.lease, 'a', 'shared')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='second', shared='by a')))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_the_cards_own_commits_on_both_sides_of_the_gap_still_count(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first', stray='x')))
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='second', late='y')))
        self.assertIn('files outside the card: late, stray;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))

    def test_a_commit_after_the_named_artifact_but_before_the_report_still_counts(self):
        """RC note: the gap starts at HEAD when the card reported, not at an earlier commit its ARTIFACT names."""
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        named = self.commit(a='first')
        self.commit(hidden='made after the named commit')
        self.engine.report('w-a', token, tr.report_for(named))
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='second')))
        self.assertIn('files outside the card: hidden;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))



class MergedSiblingTests(tr.RefusalFixture):
    """F121: a sibling's commit merged in from its own branch stays the sibling's work after this card takes over one
    of its files; this card's own commit that touches a sibling's file still counts as its own."""

    def merged_sibling(self):
        main = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('checkout', '-qb', 'side')
        sibling = self.running('b', files=['b_file', 'shared'])
        self.engine.record_bases('main', self.lease, ['b'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-b', sibling, report_for(self.commit(b_file='by b', shared='by b')))
        self.git('checkout', '-q', main)
        self.git('merge', '--no-ff', '-qm', 'merge b', 'side')
        self.engine.accept('main', self.lease, 'b')

    def test_a_merged_sibling_commit_stays_sibling_work(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.merged_sibling()
        self.engine.own_add('main', self.lease, 'a', 'shared')
        self.engine.report('w-a', token, report_for(self.commit(a='mine', shared='by a')))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_a_first_parent_commit_touching_an_owned_file_is_still_this_cards(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.merged_sibling()
        self.engine.own_add('main', self.lease, 'a', 'shared')
        self.engine.report('w-a', token, report_for(self.commit(a='mine', shared='by a', b_file='a sneaks this in')))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))


class OwnAddMovedCheckoutTests(tr.RefusalFixture):
    """F117: `own add` on a reported card after HEAD moved on keeps the report current, so accept needs no resume."""

    def test_own_add_after_a_later_commit_accepts(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, report_for(self.commit(a='mine', extra='mine too')))
        self.commit(z='a later unrelated commit')
        self.engine.own_add('main', self.lease, 'a', 'extra')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_own_add_on_a_branch_card_merged_into_this_checkout_accepts(self):
        main = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('checkout', '-qb', 'side')
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sha = self.commit(a='mine', extra='mine too')
        self.git('checkout', '-q', main)
        self.engine.report('w-a', token, report_for(sha))  # captured from this checkout, as SubagentStop does
        self.commit(z='work on main meanwhile')
        self.git('merge', '--no-ff', '-qm', 'merge a', 'side')
        self.engine.own_add('main', self.lease, 'a', 'extra')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_a_later_edit_of_the_added_file_still_stales_the_report(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, report_for(self.commit(a='mine', extra='mine too')))
        self.commit(extra='changed after the report')
        self.engine.own_add('main', self.lease, 'a', 'extra')
        self.assertIn('Reported artifact is stale', self.refusal(self.engine.accept, 'main', self.lease, 'a'))


class SideBranchSneakTests(tr.RefusalFixture):
    """RS repair of F121: this card's own side-branch commit, merged into a shared checkout, is not sibling work just
    because a sibling's later range holds it."""

    def test_a_merged_side_commit_touching_a_sibling_file_is_outside(self):
        ta = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        tb = self.running('b', files=['b_file'])
        self.engine.record_bases('main', self.lease, ['b'], self.git('rev-parse', 'HEAD'))
        main = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('checkout', '-qb', 'side')
        self.commit(a='mine', b_file='a sneaks this in')
        self.git('checkout', '-q', main)
        self.git('merge', '--no-ff', '-qm', 'merge side', 'side')
        sha_a = self.git('rev-parse', 'HEAD')
        self.engine.report('w-b', tb, report_for(self.commit(b_file2='x')))
        self.engine.report('w-a', ta, report_for(sha_a))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))

@t2.own_tests_only
class RepairReservationTests(te.FinalBlockerTests):
    """F114: two repairs meet only on their own files, whatever their chains hold; any other card still meets the chain."""

    def setUp(self):
        super().setUp()
        self.release_setup()
        self.task('B1', files=['a', 'shared'])
        self.task('B2', files=['b'])
        self.task('B3', files=['c'])
        for card in ('B1', 'B2', 'B3'):
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, te.done('Result ' + card))
        self.record('blocked', ['B1', 'B2', 'B3'], findings=['Wrong output'])
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b', 'shared'])
        self.engine.policy['max_workers'] = 3  # release_setup runs one worker; these tests need two side by side

    def test_a_repair_starts_beside_a_running_repair_whose_chain_shares_a_file(self):
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.assertEqual(['RB'], self.engine.ready('main', self.lease))
        self.engine.dispatch('main', self.lease, 'RB', 'repair-b')

    def test_a_non_repair_card_still_waits_for_the_whole_chain(self):
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.task('N', files=['shared'])
        self.assertNotIn('N', self.engine.ready('main', self.lease))

    def test_a_chain_file_another_repair_owns_is_outside(self):
        base = self.git('rev-parse', 'HEAD')
        token = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.engine.record_bases('main', self.lease, ['RA'], base)
        (self.repo / 'shared').write_text('by RA')
        self.git('add', 'shared')
        self.git('commit', '-qm', 'RA edits shared')
        self.engine.report('repair-a', token, tr.report_for(self.git('rev-parse', 'HEAD')))
        self.assertEqual(['shared'], self.engine.status()['tasks']['RA'].get('outside_files'))

    def test_two_repairs_that_own_one_file_still_wait(self):
        self.task('RC', mode='repair', repair_of='B3', files=['a'])
        self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.assertNotIn('RC', self.engine.ready('main', self.lease))



@t2.own_tests_only
class SharedChainFileTests(te.FinalBlockerTests):
    """RC repair of F114: a file both chains hold and neither repair owns is outside for each repair that edits it."""

    def setUp(self):
        super().setUp()
        self.release_setup()
        for card, files in (('B1', ['a', 'shared']), ('B2', ['b', 'shared'])):  # B1 is accepted before B2 starts
            self.task(card, files=files)
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, te.done('Result ' + card))
            if card == 'B1':
                self.engine.accept('main', self.lease, 'B1')
        self.record('blocked', ['B1', 'B2'], findings=['Wrong output'])
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b'])
        self.engine.policy['max_workers'] = 3

    def edit_shared(self, card, worker, token, base):
        self.engine.record_bases('main', self.lease, [card], base)
        (self.repo / 'shared').write_text('by ' + card)
        self.git('add', 'shared')
        self.git('commit', '-qm', card + ' edits shared')
        self.engine.report(worker, token, tr.report_for(self.git('rev-parse', 'HEAD')))
        return self.engine.status()['tasks'][card].get('outside_files')

    def test_each_repair_that_edits_the_shared_file_is_flagged(self):
        base = self.git('rev-parse', 'HEAD')
        ra = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        rb = self.engine.dispatch('main', self.lease, 'RB', 'repair-b')
        self.assertEqual(['shared'], self.edit_shared('RA', 'repair-a', ra, base))
        self.assertEqual(['shared'], self.edit_shared('RB', 'repair-b', rb, base))

    def test_a_repair_that_owns_the_shared_file_may_edit_it_and_the_other_waits(self):
        base = self.git('rev-parse', 'HEAD')
        ra = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.engine.own_add('main', self.lease, 'RA', 'shared')
        self.assertNotIn('RB', self.engine.ready('main', self.lease))
        self.assertIsNone(self.edit_shared('RA', 'repair-a', ra, base))


@t2.own_tests_only
class SharedChainDirectoryTests(te.FinalBlockerTests):
    """FX3 note on F114: chains that overlap only through a directory entry are caught too."""

    def setUp(self):
        super().setUp()
        self.release_setup()
        for card, files in (('B1', ['a', 'src']), ('B2', ['b', 'src/x.py'])):
            self.task(card, files=files)
            token = self.engine.dispatch('main', self.lease, card, 'builder-' + card, serial='test')
            self.engine.report('builder-' + card, token, te.done('Result ' + card))
            if card == 'B1':
                self.engine.accept('main', self.lease, 'B1')
        self.record('blocked', ['B1', 'B2'], findings=['Wrong output'])
        self.task('RA', mode='repair', repair_of='B1', files=['a'])
        self.task('RB', mode='repair', repair_of='B2', files=['b'])
        self.engine.policy['max_workers'] = 3

    def test_a_file_under_my_chain_directory_that_another_chain_holds_is_flagged(self):
        base = self.git('rev-parse', 'HEAD')
        ra = self.engine.dispatch('main', self.lease, 'RA', 'repair-a')
        self.engine.dispatch('main', self.lease, 'RB', 'repair-b')
        self.engine.record_bases('main', self.lease, ['RA'], base)
        (self.repo / 'src').mkdir(exist_ok=True)
        (self.repo / 'src' / 'x.py').write_text('by RA')
        (self.repo / 'src' / 'y.py').write_text('by RA')
        self.git('add', 'src')
        self.git('commit', '-qm', 'RA edits src')
        self.engine.report('repair-a', ra, tr.report_for(self.git('rev-parse', 'HEAD')))
        self.assertEqual(['src/x.py'], self.engine.status()['tasks']['RA'].get('outside_files'))

class BareNewlineTests(unittest.TestCase):
    def test_a_newline_before_a_note_keeps_the_text(self):
        self.assertEqual('make a\n(make b)', Engine._bare('make a\n(make b)'))
        self.assertEqual('make full', Engine._bare('make full \t (full gate)'))


if __name__ == '__main__':
    unittest.main()


@t2.own_tests_only
class PrReviewedScopeTests(te.PullRequestTests):
    """N4: a PR counts as reviewed only from a clean review at its head that is final or covers every card it carries."""

    def test_a_narrow_clean_review_does_not_mark_the_pr_reviewed(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.built('d', files=['d.txt'])
        self.reviewed('narrow', ['c'])
        self.assertFalse(self.engine.record_pr('main', self.lease, self.URL, tasks=['c', 'd'])[0]['reviewed'])

    def test_a_pr_recorded_without_tasks_needs_a_final_review(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.reviewed('narrow', ['c'])
        self.assertFalse(self.engine.record_pr('main', self.lease, self.URL)[0]['reviewed'])

    def test_a_clean_review_of_every_carried_card_marks_it_reviewed(self):
        self.view()
        self.built('c', files=['c.txt'])
        self.built('d', files=['d.txt'])
        self.reviewed('both', ['c', 'd'])
        self.assertTrue(self.engine.record_pr('main', self.lease, self.URL, tasks=['c', 'd'])[0]['reviewed'])


class ReadOnlyReportTests(te.EngineFixture):
    """F116: an investigator card that owns no files is accepted on its report after the checkout moves on; its evidence
    names the commit it read. A builder report still goes stale."""

    def test_an_investigator_report_survives_later_edits(self):
        self.task('I', role='investigator', mode='code', files=[])
        token = self.engine.dispatch('main', self.lease, 'I', 'w-I')
        self.engine.report('w-I', token, 'Read the code.\nARTIFACT: fixture')
        (self.repo / 'a').write_text('edited after the report')
        self.engine.accept('main', self.lease, 'I')
        self.assertEqual('accepted', self.engine.status()['tasks']['I']['state'])

    def test_an_investigator_report_under_another_policy_goes_stale(self):
        self.task('I', role='investigator', mode='code', files=[])
        token = self.engine.dispatch('main', self.lease, 'I', 'w-I')
        self.engine.report('w-I', token, 'Read the code.\nARTIFACT: fixture')
        with self.engine._state() as state:  # the report was made under another policy
            state['tasks']['I']['report_artifact']['policy'] = 'another policy'
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'I')

    def test_a_builder_report_still_goes_stale(self):
        self.task('B', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B', 'w-B')
        self.engine.report('w-B', token, te.done('Built.'))
        (self.repo / 'a').write_text('edited after the report')
        with self.assertRaisesRegex(EngineError, 'Reported artifact is stale'):
            self.engine.accept('main', self.lease, 'B')


class StopDuringGateTests(te.EngineFixture):
    """F115: the Stop hook does not ask to accept a card while a gate log has no receipt yet; the gate's end wakes the
    coordinator, and accepting before it would skip the evidence it is waiting for."""

    def setUp(self):
        super().setUp()
        self.task('B', files=['a'])
        token = self.engine.dispatch('main', self.lease, 'B', 'w-B')
        self.engine.report('w-B', token, te.done('Built.'))

    def test_a_running_gate_keeps_the_stop_quiet(self):
        from orchestra_core import hooks
        (self.engine.state_dir / 'gate-0123456789abcdef.log').write_text('PASS     generate\n')
        self.assertEqual({}, hooks._board_stop(self.engine, {}))

    def test_without_a_running_gate_the_stop_still_names_accept(self):
        from orchestra_core import hooks
        out = hooks._board_stop(self.engine, {})
        self.assertEqual('block', out.get('decision'))
        self.assertIn('accept B', out['reason'])


class StaleHintTests(tr.RefusalFixture):
    """F117: a stale report's refusal names resume, since a reported card is re-reported only after `resume` (F102)."""

    def test_the_stale_refusal_names_resume(self):
        token = self.running('a', files=['a'])
        self.engine.report('w-a', token, tr.report_for(self.commit(a='new')))
        (self.repo / 'a').write_text('edited after the report')
        text = self.refusal(self.engine.accept, 'main', self.lease, 'a')
        self.assertIn('resume a and re-report, or send a repair card', text)


class SizeChoicesTests(unittest.TestCase):
    """X1 item 2: the CLI size choices are the engine's SIZES, not a second literal."""

    def test_cli_size_choices_come_from_the_engine(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/orchestra.py').read_text()
        self.assertFalse("choices=['tiny', 'medium', 'large']" in source, 'the size choices repeat SIZES')


class OneGhRunnerTests(unittest.TestCase):
    """N8: the engine runs gh through approval.run_gh, not its own subprocess copies."""

    def test_engine_has_no_own_gh_subprocess(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts/orchestra_core/engine.py').read_text()
        self.assertFalse("shutil.which('gh')" in source, 'engine.py still finds gh itself')


class TestStateIsolationTests(unittest.TestCase):
    """2.15.3: MergedDeleteHookTest writes policy.json into the state location, so it must not be the user's own."""

    def test_merged_delete_tests_use_a_temp_state_home(self):
        import test_hooks
        from orchestra_core.paths import state_location
        case = test_hooks.MergedDeleteHookTest('test_the_merged_proof_runs_no_merge_driver')
        with mock.patch.dict(os.environ, {'ORCHESTRA_STATE_DIR': '/nonexistent/user-state'}):  # RS note: it outranks XDG
            case.setUp()
            try:
                temp = pathlib.Path(case.temp.name).resolve()
                self.assertIn(temp, state_location(case.repo).parents)
            finally:
                case.doCleanups()

    def test_merged_delete_setup_without_a_state_override(self):
        import test_hooks
        from orchestra_core.paths import state_location
        case = test_hooks.MergedDeleteHookTest('test_the_merged_proof_runs_no_merge_driver')
        case.setUp()
        try:
            temp = pathlib.Path(case.temp.name).resolve()
            self.assertIn(temp, state_location(case.repo).parents)
        finally:
            case.doCleanups()


class BindsEdgeTests(te.EngineFixture):
    """X1 item 1 (old 2.5 note): a state with the 2.3 policy hash binds only while its session carries no 2.4 field."""

    def test_the_legacy_hash_binds_without_a_sized_session(self):
        legacy, now = self.engine._policy_hash_2_3, self.engine.policy_hash
        self.assertTrue(self.engine.binds({'policy': now, 'session': {'size': 'medium'}}))
        self.assertTrue(self.engine.binds({'policy': legacy, 'session': None}))
        self.assertTrue(self.engine.binds({'policy': legacy, 'session': {'active': True}}))
        self.assertFalse(self.engine.binds({'policy': legacy, 'session': {'size': 'medium'}}))
        self.assertFalse(self.engine.binds({'policy': legacy, 'session': {'items': 2}}))
        self.assertFalse(self.engine.binds({'policy': 'other', 'session': None}))


class BoardOverlapsTests(t2.Fixture):
    """F39: the board view carries the same file overlaps as `waves`."""

    def test_view_overlaps_match_waves(self):
        self.task('a', files=['a'])
        self.task('c', files=['a'])
        self.task('b', files=['b'])
        self.assertEqual(self.engine.view()['overlaps'], self.engine.waves()['overlaps'])
        self.assertEqual(self.engine.view()['overlaps'], [['a', 'c']])


class FrictionE4Tests(tr.RefusalFixture):
    """F122, F124, F126 (2.15.3 run)."""

    def test_a_bad_self_review_key_is_named(self):
        token = self.running('a')
        sha = self.commit(a='x')
        line = json.dumps({'checks': [{'command': 'make test', 'exit': 0}],
                           'criteria': [{'criterion': 'check behavior', 'met': True, 'evidence': 'ok'}]})
        text = self.refusal(self.engine.report, 'w-a', token, 'Built.\nARTIFACT: %s clean\nSELF_REVIEW: %s' % (sha, line))
        self.assertIn('exit_code', text)

    def test_a_missing_self_review_line_still_says_so(self):
        token = self.running('a')
        self.assertIn('needs one SELF_REVIEW line', self.refusal(self.engine.report, 'w-a', token, 'Built.'))

    def test_a_review_brief_lens_must_match_the_variant(self):
        brief = self.repo / 'rt.md'
        brief.write_text('# RT\n\nMode: final\nLens: standards\n')
        self.task('a')
        card = dict(id='RT', role='code-reviewer', mode='final', inputs=[str(brief)], acceptance=['review'], files=[],
                    resources=[], dependencies=[], review_of=['a'])
        self.assertIn("variant 'standards'", self.refusal(self.engine.add_task, 'main', self.lease, dict(card)))
        self.engine.add_task('main', self.lease, dict(card, variant='standards'))
        self.assertEqual('standards', self.card('RT').get('variant'))

    def test_accept_names_uncommitted_card_files(self):
        token = self.running('a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first')))
        (self.repo / 'a').write_text('edited, not committed')
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, tr.report_for(self.git('rev-parse', 'HEAD')))
        self.assertEqual(['a'], (self.engine.accept('main', self.lease, 'a') or {}).get('uncommitted'))

    def test_accept_of_committed_work_names_nothing(self):
        token = self.running('a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first')))
        self.assertFalse((self.engine.accept('main', self.lease, 'a') or {}).get('uncommitted'))


class AcceptWarningCliTests(tr.RefusalFixture):
    """F126: the CLI result of accept carries the warning."""

    def test_the_cli_warns_on_uncommitted_card_files(self):
        token = self.running('a')
        self.engine.report('w-a', token, tr.report_for(self.commit(a='first')))
        (self.repo / 'a').write_text('edited')
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, tr.report_for(self.git('rev-parse', 'HEAD')))
        out = self.cli('accept', 'a')
        self.assertIn('uncommitted changes in the card files: a', json.dumps(out))


class OneRepositoryTests(te.PullRequestFixture):
    """RZ out-of-scope note: the approval reply lists one repository's pull requests, so a run records pull requests
    of one repository only."""

    def test_a_pull_request_of_a_second_repository_is_refused(self):
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        other = 'https://github.example/o/other/pull/8'
        with self.assertRaisesRegex(EngineError, r'records pull requests of one repository: o/r, not o/other'):
            self.engine.record_pr('main', self.lease, other)
        self.assertEqual(len(self.prs()), 1)

    def test_a_rerun_and_another_pull_request_of_the_same_repository_still_record(self):
        self.view()
        self.engine.record_pr('main', self.lease, self.URL)
        self.engine.record_pr('main', self.lease, self.URL)
        self.engine.record_pr('main', self.lease, 'https://github.example/O/R/pull/9')
        self.assertEqual(len(self.prs()), 2)


class CleanupRZTests(tr.RefusalFixture):
    """RZ notes: a staged rename, the lens hint for lenses no variant gives, and the variant map pin."""

    def test_a_staged_rename_names_both_paths_whole(self):
        self.commit(old_name_file='x')
        self.git('mv', 'old_name_file', 'new_name_file')
        self.assertEqual(['new_name_file', 'old_name_file'],
                         self.engine._uncommitted(dict(files=['old_name_file', 'new_name_file'])))

    def test_a_lens_no_variant_gives_points_at_the_brief_field(self):
        brief = self.repo / 'sec.md'
        brief.write_text('# S\n\nMode: final\nLens: security\n')
        self.task('a')
        card = dict(id='S', role='code-reviewer', mode='final', inputs=[str(brief)], acceptance=['review'], files=[],
                    resources=[], dependencies=[], review_of=['a'])
        self.assertIn("pass it as the card's brief", self.refusal(self.engine.add_task, 'main', self.lease, card))

    def test_the_engine_and_brief_variant_maps_agree(self):
        from orchestra_core import briefs
        from orchestra_core.engine import Engine
        self.assertEqual(Engine.VARIANT_LENS, briefs.LENSES)
