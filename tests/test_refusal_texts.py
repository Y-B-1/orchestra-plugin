"""Refusals list the valid values and the next command; an inline card starts and reports in one step; `own add`, the
outside-file flag, the stale-report cause, the ruling note and the finalize card."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core.engine import Engine, EngineError

SERIAL = 'fixture: one card at a time'


def report_for(sha, text='Built.'):
    review = {'checks': [{'command': 'python3 -m unittest', 'exit_code': 0}],
              'criteria': [{'criterion': 'check behavior', 'met': True, 'evidence': 'checked'}]}
    return text + '\nARTIFACT: ' + sha + ' clean\nSELF_REVIEW: ' + json.dumps(review)


class RefusalFixture(te.EngineFixture):
    def refusal(self, call, *args, **kw):
        with self.assertRaises(EngineError) as caught:
            call(*args, **kw)
        return str(caught.exception)

    def running(self, name='a', **kw):
        self.task(name, **kw)
        return self.engine.dispatch('main', self.lease, name, 'w-' + name)

    def card(self, name='a'):
        return self.engine.status()['tasks'][name]

    def cli(self, *args, lease=True):
        return te.run_cli(self, *(('--lease', self.lease) if lease else ()), *args)

    def commit(self, **files):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            self.git('add', name)
        self.git('commit', '-qm', 'change ' + ', '.join(files))
        return self.git('rev-parse', 'HEAD')


class ValidValueTests(RefusalFixture):
    def test_invalid_size_lists_the_valid_sizes_at_add_and_in_stored_state(self):
        text = self.refusal(self.task, 'a', size='huge')
        self.assertIn('Invalid task size', text)
        self.assertIn('tiny, medium', text)
        self.task('b')
        path = self.engine.state_dir / 'state.json'
        data = json.loads(path.read_text())
        data['tasks']['b']['size'] = 'huge'
        path.write_text(json.dumps(data))
        self.assertIn('tiny, medium', self.refusal(self.engine.status))

    def test_a_brief_without_keep_lists_every_required_heading(self):
        brief = self.root / 'brief.md'
        brief.write_text('Mode: implementation\nNothing else.\n')
        text = self.refusal(self.task, 'a', brief=str(brief))
        self.assertIn('Builder brief needs the heading ## Keep', text)
        self.assertIn('## Keep, ## Remove', text)


class StateRefusalTests(RefusalFixture):
    def test_cancel_of_a_running_card_names_the_park_command(self):
        self.running()
        text = self.refusal(self.engine.cancel, 'main', self.lease, 'a', 'wrong')
        self.assertIn('`park a --reason TEXT`', text)
        self.assertIn('running', text)

    def test_unpark_names_the_state_and_the_commands_it_allows(self):
        self.task('q')
        text = self.refusal(self.engine.unpark, 'main', self.lease, 'q')
        self.assertIn('Task is not parked', text)
        self.assertIn('queued', text)
        self.assertIn('dispatch', text)
        self.assertIn('unknown task', self.refusal(self.engine.unpark, 'main', self.lease, 'nope'))

    def test_park_names_the_state_of_a_card_that_cannot_be_parked(self):
        token = self.running()
        self.engine.report('w-a', token, te.done())
        self.engine.accept('main', self.lease, 'a')
        text = self.refusal(self.engine.park, 'main', self.lease, 'a', 'why')
        self.assertIn('Only a queued, running or reported card can be parked', text)
        self.assertIn('accepted', text)

    def test_invalid_assignment_says_which_cause(self):
        token = self.running()
        self.assertIn('unknown token', self.refusal(self.engine.report, 'w-a', 'nope', te.done()))
        self.assertIn('token of another worker', self.refusal(self.engine.report, 'w-b', token, te.done()))
        self.engine.report('w-a', token, te.done())
        self.engine.accept('main', self.lease, 'a')
        self.assertIn('card a is in state accepted', self.refusal(self.engine.report, 'w-a', token, te.done()))

    def test_no_reported_result_says_which_cause(self):
        self.task('q')
        self.assertIn('unknown task', self.refusal(self.engine.accept, 'main', self.lease, 'nope'))
        self.assertIn('card q is in state queued', self.refusal(self.engine.accept, 'main', self.lease, 'q'))


class MissingFileTests(RefusalFixture):
    def test_a_missing_file_is_named_and_never_a_raw_errno(self):
        token = self.running()
        missing = str(self.root / 'missing.txt')
        for args in (('report', 'w-a', token, missing), ('review', missing), ('add', missing)):
            with self.subTest(args[0]):
                code, _, err = self.cli(*args)
                self.assertEqual(2, code)
                self.assertIn(missing, err)
                self.assertNotIn('Errno', err)
        task = dict(id='b', role='builder', mode='implementation', inputs=['spec'], acceptance=['x'], files=['b'],
                    resources=[], dependencies=[], brief=str(self.root / 'no-brief.md'))
        text = self.refusal(self.engine.add_task, 'main', self.lease, task)
        self.assertIn(str(self.root / 'no-brief.md'), text)


class InlineReportTests(RefusalFixture):
    def test_inline_report_reserves_and_reports_in_one_step(self):
        self.task('a')
        report = self.root / 'report.txt'
        report.write_text(te.done('Built a.'))
        code, out, err = self.cli('inline', 'a', '--report', str(report), '--serial', SERIAL)
        self.assertEqual(0, code, err)
        self.assertEqual('reported', self.card()['state'])
        self.assertTrue(self.card()['inline'])
        self.assertIn(json.loads(out)['token'], self.card()['assignment'])

    def test_inline_report_accept_closes_the_card(self):
        self.task('a')
        report = self.root / 'report.txt'
        report.write_text(te.done('Built a.'))
        code, _, err = self.cli('inline', 'a', '--report', str(report), '--accept', '--serial', SERIAL)
        self.assertEqual(0, code, err)
        self.assertEqual('accepted', self.card()['state'])

    def test_a_refused_report_reserves_nothing(self):
        self.task('a')
        bad = self.root / 'bad.txt'
        bad.write_text('Built a. No self review.\nARTIFACT: x')
        empty = self.root / 'empty.txt'
        empty.write_text('  \n')
        for label, path in (('no SELF_REVIEW', bad), ('empty', empty), ('missing', self.root / 'gone.txt')):
            with self.subTest(label):
                code, _, err = self.cli('inline', 'a', '--report', str(path), '--serial', SERIAL)
                self.assertEqual(2, code)
                self.assertNotIn('Errno', err)
                self.assertEqual('queued', self.card()['state'])
                self.assertNotIn('assignment', self.card())

    def test_accept_needs_a_report(self):
        self.task('a')
        code, _, err = self.cli('inline', 'a', '--accept', '--serial', SERIAL)
        self.assertEqual(2, code)
        self.assertIn('--report', err)
        self.assertEqual('queued', self.card()['state'])


class OwnAddTests(RefusalFixture):
    def test_own_add_adds_a_path_and_records_it(self):
        self.running()
        code, _, err = self.cli('own', 'add', 'a', 'extra.txt')
        self.assertEqual(0, code, err)
        self.assertEqual(['a', 'extra.txt'], self.card()['files'])
        self.assertIn('own add a extra.txt', (self.engine.state_dir / 'progress.md').read_text())

    def test_own_add_refuses_a_path_another_card_holds(self):
        self.running('a')
        self.running('b', files=['b/sub'])
        text = self.refusal(self.engine.own_add, 'main', self.lease, 'a', 'b')
        self.assertIn('files overlap', text)
        self.assertEqual(['a'], self.card()['files'])

    def test_own_add_refuses_a_bad_path_or_an_idle_card(self):
        self.running('a')
        self.task('q')
        for path in ('*.py', '/abs', '../up', ''):
            with self.subTest(path):
                self.assertIn('ownership', self.refusal(self.engine.own_add, 'main', self.lease, 'a', path))
        self.assertIn('running or reported', self.refusal(self.engine.own_add, 'main', self.lease, 'q', 'z'))
        self.assertIn('Unknown task', self.refusal(self.engine.own_add, 'main', self.lease, 'nope', 'z'))


class OutsideFileTests(RefusalFixture):
    def built(self, files, **commit):
        token = self.running('a', files=files)
        base = self.git('rev-parse', 'HEAD')
        self.engine.record_bases('main', self.lease, ['a'], base)
        sha = self.commit(**commit)
        self.engine.report('w-a', token, report_for(sha))
        return token

    def test_files_outside_the_card_are_flagged_and_accept_refuses(self):
        self.built(['a'], a='new', other='x', sub_dir_file='y')
        text = self.refusal(self.engine.accept, 'main', self.lease, 'a')
        self.assertEqual('reported', self.card()['state'])
        self.assertIn('files outside the card: other, sub_dir_file; add them with own add or revert them', text)

    def test_a_sibling_cards_commit_in_the_range_is_not_outside(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sibling = self.running('b', files=['b_file'])
        self.engine.report('w-b', sibling, report_for(self.commit(b_file='by b')))
        self.engine.accept('main', self.lease, 'b')
        self.engine.report('w-a', token, report_for(self.commit(a='new', stray='x')))
        text = self.refusal(self.engine.accept, 'main', self.lease, 'a')
        self.assertIn('files outside the card: stray;', text)  # the sibling's b_file is not listed

    def test_a_sibling_accepted_after_the_report_clears_its_files_at_accept(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sibling = self.running('b', files=['b_file'])
        b_sha = self.commit(b_file='by b')
        self.engine.report('w-a', token, report_for(self.commit(a='new')))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))
        self.engine.report('w-b', sibling, report_for(b_sha))
        self.engine.accept('main', self.lease, 'b')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_a_card_that_changes_a_file_a_sibling_owns_is_still_flagged(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sibling = self.running('b', files=['b_file', 'b_other'])
        self.engine.report('w-b', sibling, report_for(self.commit(b_other='by b')))
        self.engine.accept('main', self.lease, 'b')
        self.engine.report('w-a', token, report_for(self.commit(a='new', b_file='by a')))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))

    def test_a_file_both_cards_changed_stays_flagged(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sibling = self.running('b', files=['b_file'])
        self.engine.report('w-b', sibling, report_for(self.commit(b_file='by b')))
        self.engine.accept('main', self.lease, 'b')
        self.engine.report('w-a', token, report_for(self.commit(a='new', b_file='by a too')))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))

    def test_a_card_commit_older_than_the_siblings_report_is_still_flagged(self):
        token = self.running('a', files=['a'])
        self.engine.record_bases('main', self.lease, ['a'], self.git('rev-parse', 'HEAD'))
        sibling = self.running('b', files=['b_file', 'b_other'])
        self.engine.record_bases('main', self.lease, ['b'], self.git('rev-parse', 'HEAD'))
        self.engine.report('w-a', token, report_for(self.commit(a='new', b_file='by a')))
        self.engine.report('w-b', sibling, report_for(self.commit(b_other='by b')))
        self.assertIn('files outside the card: b_file;', self.refusal(self.engine.accept, 'main', self.lease, 'a'))

    def test_own_add_clears_the_flag(self):
        self.built(['a'], a='new', other='x')
        self.assertIn('files outside the card: other', self.refusal(self.engine.accept, 'main', self.lease, 'a'))
        self.engine.own_add('main', self.lease, 'a', 'other')
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_a_card_inside_its_files_is_not_flagged(self):
        self.built(['a', 'dir'], a='new', **{'dir/inner': 'x'})
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    GENERATOR = 'plugins/orchestra/scripts/generate.py'

    def generator_repo(self, exit_code):
        script = ('import sys\nsys.exit(%d)\n' % exit_code)
        return {'plugins/orchestra/scripts/generate.py': script, 'plugins/orchestra/agents/x.md': 'generated'}

    def test_generated_outputs_count_as_owned_when_the_generator_check_passes(self):
        self.built(['a', self.GENERATOR], a='new', **self.generator_repo(0))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.card()['state'])

    def test_generated_outputs_are_flagged_when_the_generator_check_fails(self):
        files = self.generator_repo(1)
        self.built(['a', self.GENERATOR], a='new', **files)
        text = self.refusal(self.engine.accept, 'main', self.lease, 'a')
        self.assertIn('files outside the card: plugins/orchestra/agents/x.md;', text)


class StaleReportTests(RefusalFixture):
    def test_a_stale_report_names_the_paths_and_the_commit_that_changed_each(self):
        token = self.running('a', files=['a', 'b'])
        self.engine.report('w-a', token, te.done())
        sha = self.commit(a='later')
        (self.repo / 'b').write_text('uncommitted')
        text = self.refusal(self.engine.accept, 'main', self.lease, 'a')
        self.assertIn('Reported artifact is stale', text)
        self.assertIn('a (%s)' % sha[:7], text)
        self.assertIn('b (uncommitted)', text)


class RulingNoteTests(RefusalFixture):
    def test_a_ruling_on_a_card_with_nothing_unmet_is_a_note_and_accepts(self):
        token = self.running()
        self.engine.report('w-a', token, te.done())
        self.engine.accept('main', self.lease, 'a', ruling='Nothing to rule on, accept.')
        self.assertEqual('accepted', self.card()['state'])
        self.assertIn('Nothing to rule on, accept.', (self.engine.state_dir / 'progress.md').read_text())

    def test_an_inline_card_still_takes_no_ruling(self):
        self.task('a')
        token = self.engine.start_inline('main', self.lease, 'a', serial=SERIAL)
        self.engine.report('main', token, te.done())
        self.assertIn('inline', self.refusal(self.engine.accept, 'main', self.lease, 'a', ruling='Self ruling.'))


class FinalizeCardTests(RefusalFixture):
    def test_a_finalize_card_waits_for_every_other_card(self):
        self.task('a')
        self.task('f', finalize=True, files=['CHANGELOG'])
        text = self.refusal(self.engine.dispatch, 'main', self.lease, 'f', 'w-f')
        self.assertIn('finalize card waits for: a (queued)', text)
        waves = self.engine.waves()
        self.assertEqual(['a'], waves['startable_now'])
        self.assertEqual(['a'], waves['wave_now'])
        token = self.engine.dispatch('main', self.lease, 'a', 'w-a')
        self.engine.report('w-a', token, te.done())
        self.assertIn('a (reported)', self.refusal(self.engine.dispatch, 'main', self.lease, 'f', 'w-f'))
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual(['f'], self.engine.waves()['startable_now'])
        self.engine.dispatch('main', self.lease, 'f', 'w-f')

    def test_parked_and_held_cards_do_not_block_it(self):
        self.task('a')
        self.task('f', finalize=True, files=['CHANGELOG'])
        self.engine.park('main', self.lease, 'a', 'later')
        self.engine.dispatch('main', self.lease, 'f', 'w-f')

    def test_the_field_must_be_a_boolean(self):
        for bad in ('yes', 1, None, []):
            with self.subTest(bad):
                self.assertIn('Invalid task finalize', self.refusal(self.task, 'f', finalize=bad))


if __name__ == '__main__':
    unittest.main()
