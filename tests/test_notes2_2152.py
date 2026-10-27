"""2.15.2 notes from the fresh pre-PR review: the track names a busy main session, rulings accept plain prose endings,
`full_check` matches a check with a trailing note, `replace` passes on the final-review warning, and a reported card's
report changes only after `resume`."""
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_capture as tc
import test_engine as te
import test_engine_2152 as t2
from orchestra_core import delta, hooks
from orchestra_core.engine import Engine, EngineError


class BusyTrackTests(t2.Fixture):
    def test_the_track_names_the_running_inline_card(self):
        for name in ('a', 'b', 'c'):
            self.task(name, files=[name])
        self.engine.start_inline('main', self.lease, 'a', serial='fixture: one card at a time')
        view = self.engine.view()
        self.assertEqual(view['track'][0].get('busy'), 'a')
        self.assertEqual('Track: you are running a; side: b, c', delta.track_text(view))


class RulingProseTests(t2.Fixture):
    def test_plain_prose_around_the_target_still_names_it(self):
        for ruling in ('a known flake in tests.test_a.', 'tests.test_a - known flake', '"tests.test_a" flakes'):
            with self.subTest(ruling=ruling):
                self.setUp()
                self.reported('a', checks=[{'command': 'python3 -m unittest tests.test_a', 'exit_code': 1}])
                self.engine.accept('main', self.lease, 'a', ruling=ruling)


class FullCheckNoteTests(t2.Fixture):
    def test_a_check_with_a_trailing_note_counts_and_the_spec_is_trimmed(self):
        self.engine = Engine(self.root / 'fc', self.repo, dict(schema_version=1, full_check=dict(paths=['*'], command=' make full ')))
        self.lease = self.engine.open_session('main')
        self.reported('a', checks=[{'command': 'make full (full gate)', 'exit_code': 0}])
        self.engine.accept('main', self.lease, 'a')
        self.assertEqual('accepted', self.cards()['a']['state'])


class ReplaceWarningTests(t2.Fixture):
    def test_replace_passes_on_the_final_review_warning(self):
        self.reported('B1')
        self.engine.accept('main', self.lease, 'B1')
        self.task('OLD', files=['old'])
        self.task('R1', role='code-reviewer', mode='final', review_of=['B1'], files=[])
        self.engine.dispatch('main', self.lease, 'R1', 'w-R1', serial='fixture: one card at a time')
        out = self.replace('OLD', t2.card('NEW')) or {}
        self.assertIn('R1', out.get('warning', ''))


class ReportedCaptureTests(tc.CaptureCase):
    def test_a_second_final_message_without_resume_leaves_the_report(self):
        self.stop()
        first = (self.reports / (self.token + '.md')).read_text()
        self.assertEqual(self.stop(message='STATUS: PASS\nARTIFACT: def456 clean\nChanged.'), {})
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), first)
        self.assertNotIn('def456', json.dumps(self.engine.status()['tasks']['c']))

    def test_after_resume_the_next_message_replaces_the_report(self):
        self.stop()
        self.engine.resume_card('main', self.lease, 'c')
        newer = 'STATUS: PASS\nARTIFACT: def456 clean\nFixed the two lines.'
        self.assertEqual(self.stop(message=newer), {})
        self.assertEqual((self.reports / (self.token + '.md')).read_text(), newer)
        self.assertEqual(self.task_state(), 'reported')


UID = 'claude-%d' % os.getuid()


class TempNotesTests(unittest.TestCase):
    """FXH notes: a TMPDIR with a `claude-` part anywhere adds no root, the session's own TMPDIR keeps its own files
    deletable, and a plain path into a `cc-` entry of a temp root is denied like its glob."""

    def judge(self, command, tmpdir, session=None):
        with mock.patch.dict(os.environ, {'TMPDIR': tmpdir}):
            return hooks._rm_in_temp(command, session)

    def test_a_tmpdir_with_a_claude_part_outside_tmp_adds_no_root(self):
        self.assertFalse(self.judge('rm -rf /var/folders/ab/cd/T/%s/-*' % UID, '/var/folders/ab/cd/T/' + UID))

    def test_the_sessions_own_tmpdir_keeps_its_files_deletable(self):
        own = '/private/tmp/%s/proj/sess' % UID
        self.assertTrue(self.judge('rm -rf %s/*' % own, own, session='sess'))
        self.assertFalse(self.judge('rm -rf /private/tmp/%s/proj/other/*' % UID, own, session='sess'))

    def test_a_plain_path_into_a_cc_entry_is_denied(self):
        for command in ('rm -rf /tmp/cc-socks/x', 'rm -rf /private/tmp/CC-socks', 'rm -f /tmp/cc-x'):
            with self.subTest(command=command):
                self.assertFalse(self.judge(command, '/var/folders/ab/cd/T'))
        self.assertTrue(self.judge('rm -rf /tmp/ccache/x', '/var/folders/ab/cd/T'))


class ModelLineWordingTests(t2.Fixture):
    """RWT note 0: the line names why a card goes to a worker under the rank rule."""

    def test_the_line_says_stronger_model_or_higher_effort(self):
        self.engine.record_model('claude-haiku-5-5', 'low')
        self.task('b1', files=['b1'])
        text = hooks._model_line(self.engine, self.engine.view())
        self.assertIn('Cards that must go to a worker (a stronger model or a higher effort): b1', text)


@t2.own_tests_only
class ReceiptPrefixTests(te.FindingsLedgerTests):
    """F113: `finding add --review` takes the short receipt id `review` prints, when it names one receipt."""

    def test_a_unique_prefix_names_the_receipt(self):
        receipt = self.final_with_items(['Rename the helper'])
        entry = self.engine.add_finding('main', self.lease, receipt['id'][:8], 'out_of_scope', 0, 'deferred', 'later')
        self.assertEqual('deferred', entry['disposition'])
        self.assertEqual(receipt['id'], entry['source']['review'])

    def test_a_short_or_unknown_prefix_is_refused(self):
        receipt = self.final_with_items(['Rename the helper'])
        for prefix in (receipt['id'][:3], 'f' * 8 if not receipt['id'].startswith('f' * 8) else '0' * 8):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(EngineError, 'Unknown review'):
                self.engine.add_finding('main', self.lease, prefix, 'out_of_scope', 0, 'deferred', 'later')


if __name__ == '__main__':
    unittest.main()
