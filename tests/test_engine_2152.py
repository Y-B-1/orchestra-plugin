"""2.15.2 engine friction: F98 replace, F99 ruling on a failing check, F102 resume, F104 deferred out-of-scope and
needs_triage, F101 full_check. (F70 subshell matching is in test_e1f_2151.py.)"""
import json
import pathlib
import shlex
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError


def own_tests_only(cls):
    """Reuse a fixture class without rerunning the tests it inherits."""
    for name in dir(cls):
        if name.startswith('test_') and name not in vars(cls):
            setattr(cls, name, None)
    return cls


def card(name, **kw):
    task = dict(id=name, role='builder', mode='implementation', inputs=['spec'], acceptance=['check behavior'],
                files=[name], resources=[], dependencies=[])
    task.update(kw)
    return task


class Fixture(te.EngineFixture):
    def cards(self):
        return json.loads(self.engine.state_path.read_text())['tasks']

    def raw(self):
        return json.loads(self.engine.state_path.read_text())

    def reported(self, name, checks=None, criteria=None, text='Built.'):
        self.task(name)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, te.done(text, checks=checks, criteria=criteria))
        return token

    def replace(self, old, task):
        return self.engine.replace_task('main', self.lease, old, task)


class ReplaceTests(Fixture):
    def test_replace_swaps_a_queued_card_and_moves_dependents_and_reviewers(self):
        self.task('OLD')
        self.task('DEP', dependencies=['OLD'])
        self.task('REV', role='code-reviewer', mode='final', review_of=['OLD'], files=[])
        self.replace('OLD', card('NEW'))
        cards = self.cards()
        self.assertNotIn('OLD', cards)
        self.assertEqual('queued', cards['NEW']['state'])
        self.assertEqual(['NEW'], cards['DEP']['dependencies'])
        self.assertEqual(['NEW'], cards['REV']['review_of'])
        gone = self.raw()['cancelled']
        self.assertEqual(['OLD'], [c['id'] for c in gone])
        self.assertEqual('replaced by NEW', gone[0]['reason'])

    def test_replace_takes_the_place_of_a_reported_or_parked_card(self):
        self.reported('R1')
        self.task('P1')
        self.engine.park('main', self.lease, 'P1', 'waiting for the owner')
        self.replace('R1', card('R2'))
        self.replace('P1', card('P2'))
        self.assertEqual(['P2', 'R2'], sorted(self.cards()))
        self.assertEqual(['queued', 'queued'], [self.cards()[i]['state'] for i in ('P2', 'R2')])

    def test_replace_refuses_a_running_or_an_accepted_card_and_keeps_it(self):
        self.task('RUN')
        self.engine.dispatch('main', self.lease, 'RUN', 'w-RUN')
        self.reported('ACC')
        self.engine.accept('main', self.lease, 'ACC')
        for old in ('RUN', 'ACC'):
            with self.subTest(old), self.assertRaisesRegex(EngineError, 'cannot be replaced'):
                self.replace(old, card('NEW-' + old))
        self.assertEqual(['ACC', 'RUN'], sorted(self.cards()))

    def test_a_refused_new_card_leaves_old_and_its_dependents_untouched(self):
        self.task('OLD')
        self.task('DEP', dependencies=['OLD'])
        before = self.raw()['tasks']
        bad = {'no inputs': {k: v for k, v in card('NEW').items() if k != 'inputs'},
               'duplicate id': card('DEP'),
               'same id': card('OLD'),
               'depends on the old card': card('NEW', dependencies=['OLD']),
               'unknown id': None}
        for label, task in bad.items():
            with self.subTest(label), self.assertRaises(EngineError):
                self.replace('OLD', task)
        with self.assertRaisesRegex(EngineError, 'Unknown task'):
            self.replace('GHOST', card('NEW'))
        self.assertEqual(before, self.raw()['tasks'])
        self.assertNotIn('cancelled', self.raw())

    def test_replace_refuses_a_cycle_through_a_moved_dependent(self):
        self.task('OLD')
        self.task('DEP', dependencies=['OLD'])
        with self.assertRaisesRegex(EngineError, 'cycle'):
            self.replace('OLD', card('NEW', dependencies=['DEP']))
        self.assertEqual(['OLD'], self.cards()['DEP']['dependencies'])

    def test_replace_refuses_a_card_a_review_covers_or_a_repair_chain_holds(self):
        self.reported('B1')
        self.allow_review('rev')
        path = self.root / 'r.json'
        self.review(path, reviewer='rev', tasks=['B1'])
        self.engine.record_review('main', self.lease, 'rev', path, ['correctness'], ['B1'])
        with self.assertRaisesRegex(EngineError, 'review covers'):
            self.replace('B1', card('B2'))

    def test_replace_needs_the_lease(self):
        self.task('OLD')
        with self.assertRaises(EngineError):
            self.engine.replace_task('main', 'wrong-lease', 'OLD', card('NEW'))
        self.assertIn('OLD', self.cards())

    def test_the_cli_and_a_do_step_replace_a_card(self):
        self.task('OLD')
        self.task('OLD2')
        for name in ('NEW', 'NEW2'):
            (self.root / (name + '.json')).write_text(json.dumps(card(name)))
        code, out, err = te.run_cli(self, '--lease', self.lease, 'replace', 'OLD', str(self.root / 'NEW.json'))
        self.assertEqual(0, code, err)
        self.assertEqual({'replaced': 'OLD', 'by': 'NEW'}, {k: json.loads(out)[k] for k in ('replaced', 'by')})
        code, out, err = te.run_cli(self, '--lease', self.lease, 'do', 'replace OLD2 ' + shlex.quote(str(self.root / 'NEW2.json')))
        self.assertEqual(0, code, out)
        self.assertEqual(['NEW', 'NEW2'], sorted(self.cards()))


class ResumeTests(Fixture):
    def test_resume_returns_a_reported_card_to_running_with_the_same_token_and_keeps_the_report(self):
        token = self.reported('a', text='First try.')
        self.engine.resume_card('main', self.lease, 'a')
        card_ = self.cards()['a']
        self.assertEqual('running', card_['state'])
        self.assertEqual(token, card_['assignment'])
        self.assertEqual('w-a', card_['worker'])
        self.assertNotIn('report', card_)
        self.assertNotIn('self_review', card_)
        self.assertIn('First try.', card_['report_history'][0]['report'])
        self.assertNotIn('a', self.engine.view('main').get('acceptable_now', []))
        with self.assertRaisesRegex(EngineError, 'allows'):
            self.engine.accept('main', self.lease, 'a')

    def test_a_later_report_replaces_the_kept_one(self):
        token = self.reported('a', text='First try.')
        self.engine.resume_card('main', self.lease, 'a')
        self.engine.report('w-a', token, te.done('Second try.'))
        card_ = self.cards()['a']
        self.assertEqual('reported', card_['state'])
        self.assertIn('Second try.', card_['report'])
        self.assertEqual(1, len(card_['report_history']))
        self.engine.accept('main', self.lease, 'a')

    def test_resume_refuses_a_card_that_is_not_reported(self):
        self.reported('acc')
        self.engine.accept('main', self.lease, 'acc')
        self.task('q')
        self.task('r')
        self.engine.dispatch('main', self.lease, 'r', 'w-r', serial='test')
        for name in ('q', 'r', 'acc', 'GHOST'):
            with self.subTest(name), self.assertRaises(EngineError):
                self.engine.resume_card('main', self.lease, name)

    def test_resume_refuses_a_report_a_review_covers_and_a_wrong_lease(self):
        self.reported('B1')
        with self.assertRaises(EngineError):
            self.engine.resume_card('main', 'wrong-lease', 'B1')
        self.allow_review('rev')
        path = self.root / 'r.json'
        self.review(path, reviewer='rev', tasks=['B1'])
        self.engine.record_review('main', self.lease, 'rev', path, ['correctness'], ['B1'])
        with self.assertRaisesRegex(EngineError, 'review covers'):
            self.engine.resume_card('main', self.lease, 'B1')
        self.assertEqual('reported', self.cards()['B1']['state'])

    def test_the_cli_and_a_do_step_resume_a_card(self):
        self.reported('a')
        self.reported('b')
        code, out, err = te.run_cli(self, '--lease', self.lease, 'resume', 'a')
        self.assertEqual(0, code, err)
        self.assertEqual('a', json.loads(out)['resumed'])
        code, out, err = te.run_cli(self, '--lease', self.lease, 'do', 'resume b')
        self.assertEqual(0, code, err)
        self.assertEqual(['running', 'running'], [self.cards()[i]['state'] for i in 'ab'])


class RulingOnCheckTests(Fixture):
    FAILING = [{'command': 'python3 -m unittest tests/test_flaky.py', 'exit_code': 1},
               {'command': 'make test', 'exit_code': 0}]

    def test_a_ruling_that_names_the_failing_command_accepts_and_is_recorded(self):
        self.reported('a', checks=self.FAILING)
        with self.assertRaisesRegex(EngineError, 'failing check'):
            self.engine.accept('main', self.lease, 'a')
        text = 'python3 -m unittest tests/test_flaky.py fails on the clock only; owner agrees'
        self.engine.accept('main', self.lease, 'a', ruling=text)
        card_ = self.cards()['a']
        self.assertEqual('accepted', card_['state'])
        self.assertEqual(text, card_['ruling']['text'])

    def test_a_ruling_that_names_the_test_file_of_the_command_accepts(self):
        self.reported('a', checks=self.FAILING)
        self.engine.accept('main', self.lease, 'a', ruling='tests/test_flaky.py is a known flake')
        self.assertEqual('accepted', self.cards()['a']['state'])

    def test_a_ruling_that_names_no_failing_check_is_refused(self):
        self.reported('a', checks=self.FAILING)
        for ruling in ('Ignore the failing check.', 'make test is fine', 'tests/test_other.py is a known flake'):
            with self.subTest(ruling), self.assertRaisesRegex(EngineError, 'failing check'):
                self.engine.accept('main', self.lease, 'a', ruling=ruling)
        self.assertEqual('reported', self.cards()['a']['state'])

    def test_every_failing_check_must_be_named(self):
        checks = self.FAILING + [{'command': 'ruff check src', 'exit_code': 2}]
        self.reported('a', checks=checks)
        with self.assertRaisesRegex(EngineError, 'ruff check src'):
            self.engine.accept('main', self.lease, 'a', ruling='tests/test_flaky.py is a known flake')
        self.engine.accept('main', self.lease, 'a', ruling='tests/test_flaky.py is flaky and ruff check src is a lint-only miss')
        self.assertEqual('accepted', self.cards()['a']['state'])

    def test_a_named_check_and_an_unmet_criterion_are_ruled_together(self):
        self.reported('a', checks=self.FAILING, criteria=[{'criterion': 'check behavior', 'met': False, 'evidence': 'no'}])
        self.engine.accept('main', self.lease, 'a', ruling='tests/test_flaky.py is flaky; the criterion is out of reach')
        self.assertEqual('accepted', self.cards()['a']['state'])

    def test_a_red_first_check_with_no_later_pass_is_still_never_rulable(self):
        self.reported('a', checks=[{'command': 'make test', 'exit_code': 1, 'expect': 'fail'}])
        with self.assertRaisesRegex(EngineError, 'no later passing run'):
            self.engine.accept('main', self.lease, 'a', ruling='make test was meant to fail')

    def test_the_cli_takes_the_ruling_on_a_failing_check(self):
        self.reported('a', checks=self.FAILING)
        code, out, err = te.run_cli(self, '--lease', self.lease, 'accept', 'a', '--ruling', 'tests/test_flaky.py is a known flake')
        self.assertEqual(0, code, err)
        self.assertEqual('accepted', self.cards()['a']['state'])


@own_tests_only
class DeferredOutOfScopeTests(te.FindingsLedgerTests):
    def test_an_out_of_scope_item_can_be_deferred_with_a_reason(self):
        receipt = self.final_with_items(['Rename the helper'])
        entry = self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 0, 'deferred', 'next release')
        self.assertEqual('deferred', entry['disposition'])
        self.assertEqual('next release', entry['reason'])
        self.engine.status()  # the stored state still validates

    def test_a_deferred_item_needs_a_reason_and_other_kinds_keep_their_dispositions(self):
        receipt = self.final_with_items(['Rename the helper'])
        with self.assertRaisesRegex(EngineError, 'reason'):
            self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 0, 'deferred', '  ')
        with self.assertRaisesRegex(EngineError, 'Disposition'):
            self.engine.add_finding('main', self.lease, receipt['id'], 'out_of_scope', 0, 'rejected', 'no')

    def test_a_final_receipt_lists_its_untriaged_items_without_refusing(self):
        receipt = self.final_with_items(['Rename the helper', 'Drop the old flag'])
        self.assertEqual(['Rename the helper', 'Drop the old flag'], receipt['needs_triage'])

    def test_a_final_receipt_without_out_of_scope_items_has_no_needs_triage(self):
        self.reported()
        receipt = self.record('final', ['a'], final=True)
        self.assertNotIn('needs_triage', receipt)

    def test_a_triaged_item_is_left_out_of_needs_triage_on_the_next_receipt(self):
        first = self.final_with_items(['Rename the helper'], name='one')
        self.engine.add_finding('main', self.lease, first['id'], 'out_of_scope', 0, 'deferred', 'next release')
        second = self.record('two', ['a'], final=True, out_of_scope=['Rename the helper', 'Drop the old flag'])
        self.assertEqual(['Drop the old flag'], second['needs_triage'])

    def test_the_cli_prints_needs_triage_for_a_final_receipt(self):
        self.reported()
        path = self.root / 'final.json'
        from orchestra_core.engine import CATEGORIES
        self.review(path, reviewer='final', tasks=sorted(self.engine.status()['tasks']), categories=CATEGORIES, final=True)
        body = json.loads(path.read_text())
        body['out_of_scope'] = ['Rename the helper']
        path.write_text(json.dumps(body))
        code, out, err = te.run_cli(self, '--lease', self.lease, 'review', str(path))
        self.assertEqual(0, code, err)
        self.assertEqual(['Rename the helper'], json.loads(out)['needs_triage'])
        code, out, err = te.run_cli(self, '--lease', self.lease, 'finding', 'add', '--review', json.loads(out)['id'],
                                    '--kind', 'out_of_scope', '--index', '0', '--disposition', 'deferred', '--reason', 'next release')
        self.assertEqual(0, code, err)
        self.assertEqual('deferred', json.loads(out)['disposition'])


class FullCheckTests(te.EngineFixture):
    FULL = {'paths': ['src/**'], 'command': 'python3 -B -m unittest discover -s tests'}

    def fresh(self, policy):
        self.engine = Engine(self.root / 'state-fc', self.repo, policy)
        self.lease = self.engine.open_session('main')

    def built(self, name, files, checks, commit=None):
        """A builder card owning FILES, reported with CHECKS; COMMIT names the touched files to commit with a base."""
        self.task(name, files=files)
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        sha = None
        if commit:
            base = self.git('rev-parse', 'HEAD')
            self.engine.record_bases('main', self.lease, [name], base)
            for path in commit:
                (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
                (self.repo / path).write_text(name)
                self.git('add', path)
            self.git('commit', '-qm', name)
            sha = self.git('rev-parse', 'HEAD')
        text = te.done('Built ' + name, checks=checks)
        if sha:
            text = text.replace('ARTIFACT: fixture', 'ARTIFACT: ' + sha + ' clean')
        self.engine.report('w-' + name, token, text)

    def ok(self, command='make test'):
        return {'command': command, 'exit_code': 0}

    def test_a_card_touching_a_matching_path_needs_the_full_check_in_its_self_review(self):
        self.fresh({'full_check': self.FULL})
        self.built('fx', ['src/x.py'], [self.ok()])
        with self.assertRaisesRegex(EngineError, 'python3 -B -m unittest discover -s tests'):
            self.engine.accept('main', self.lease, 'fx')

    def test_the_full_check_passing_lets_the_card_be_accepted(self):
        self.fresh({'full_check': self.FULL})
        self.built('fx', ['src/x.py'], [self.ok(), self.ok(self.FULL['command'])])
        self.engine.accept('main', self.lease, 'fx')
        self.assertEqual('accepted', self.engine.status()['tasks']['fx']['state'])

    def test_a_red_first_run_alone_does_not_count_as_the_full_check(self):
        self.fresh({'full_check': self.FULL})
        red = {'command': self.FULL['command'], 'exit_code': 1, 'expect': 'fail'}
        self.built('fx', ['src/x.py'], [red, self.ok(self.FULL['command'] + ' --verbose')])
        with self.assertRaises(EngineError):
            self.engine.accept('main', self.lease, 'fx')

    def test_a_card_touching_no_matching_path_is_unchanged(self):
        self.fresh({'full_check': self.FULL})
        self.built('docs', ['docs/a.md'], [self.ok()])
        self.engine.accept('main', self.lease, 'docs')

    def test_without_the_key_nothing_changes(self):
        self.fresh(None)
        self.built('fx', ['src/x.py'], [self.ok()])
        self.engine.accept('main', self.lease, 'fx')

    def test_the_diff_of_the_reported_commit_decides_when_it_is_known(self):
        self.fresh({'full_check': self.FULL})
        self.built('wide', ['src', 'docs'], [self.ok()], commit=['docs/only.md'])
        self.engine.accept('main', self.lease, 'wide')  # it owns src, but its commit touched docs only
        self.built('wide2', ['src', 'docs'], [self.ok()], commit=['src/y.py'])
        with self.assertRaisesRegex(EngineError, 'python3 -B -m unittest discover -s tests'):
            self.engine.accept('main', self.lease, 'wide2')

    def test_a_malformed_full_check_is_refused_at_start(self):
        for bad in ('x', {'paths': ['src/**']}, {'command': 'make'}, {'paths': 'src', 'command': 'make'},
                    {'paths': [''], 'command': 'make'}, {'paths': ['src'], 'command': ' '}, {'paths': [], 'command': 'make'},
                    {'paths': ['src'], 'command': 'make', 'extra': 1}):
            with self.subTest(bad):
                engine = Engine(self.root / 'state-bad', self.repo, {'full_check': bad})
                with self.assertRaisesRegex(EngineError, 'full_check'):
                    engine._check_policy_keys()


if __name__ == '__main__':
    unittest.main()
