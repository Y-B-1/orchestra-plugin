"""Prep cards: `prep_for`, the idle_workers and prep keys of `waves` and `wave`, and the Prep notes brief section."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
import test_waves as tw
from orchestra_core import briefs
from orchestra_core.engine import EngineError


class PrepTests(tw.WaveFixture):
    def prep_card(self, name, target, **kw):
        self.task(name, role='investigator', mode='code', files=[], prep_for=target, **kw)

    def test_prep_for_needs_an_investigator_an_existing_other_card(self):
        self.task('a')
        with self.assertRaisesRegex(EngineError, 'prep_for'):
            self.task('b', prep_for='a')  # builder role
        with self.assertRaisesRegex(EngineError, 'prep_for'):
            self.prep_card('c', 'nope')
        with self.assertRaisesRegex(EngineError, 'prep_for'):
            self.prep_card('d', 'd')
        self.prep_card('p', 'a')
        self.assertEqual(self.engine.status()['tasks']['p']['prep_for'], 'a')

    def test_waves_lists_idle_workers_and_unprepared_blocked_builders(self):
        self.engine_with(dict(max_workers=3))
        self.task('a')
        self.task('b', dependencies=['a'])
        self.task('c', dependencies=['a'])
        self.task('d', files=['a'])  # overlaps a only once a runs
        self.task('r', role='investigator', mode='code', files=[])
        out = self.engine.waves()
        self.assertEqual(out['idle_workers'], 3)
        self.assertEqual(out['prep'], ['b', 'c'])
        self.prep_card('p', 'b')
        self.assertEqual(self.engine.waves()['prep'], ['c'])
        self.engine.dispatch('main', self.lease, 'a', 'wa', serial='fixture')
        out = self.engine.waves()
        self.assertEqual(out['idle_workers'], 2)
        self.assertEqual(out['prep'], ['c', 'd'])  # d now overlaps the running a

    def test_idle_workers_never_below_zero(self):
        self.engine_with(dict(max_workers=1))
        self.task('a')
        self.task('r', role='investigator', mode='code', files=[])
        self.engine.dispatch('main', self.lease, 'a', 'wa', serial='fixture')
        self.assertEqual(self.engine.waves()['idle_workers'], 0)

    def test_wave_output_adds_idle_workers_and_prep_without_refusing(self):
        self.engine_with(dict(max_workers=5))
        self.task('a')
        self.task('b', dependencies=['a'])
        out = self.engine.wave('main', self.lease, ['a'])
        self.assertEqual(out['idle_workers'], 4)
        self.assertEqual(out['prep'], ['b'])

    def test_wave_output_has_no_prep_key_when_nothing_is_blocked(self):
        self.engine_with(dict(max_workers=5))
        self.task('a')
        out = self.engine.wave('main', self.lease, ['a'])
        self.assertEqual(out['idle_workers'], 4)
        self.assertNotIn('prep', out)

    def test_brief_adds_prep_notes_for_accepted_prep_cards_only(self):
        self.task('a')
        self.assertNotIn('Prep notes', briefs.card(self.engine, 'a'))
        self.prep_card('p', 'a')
        self.prep_card('q', 'a')
        self.engine.report('wp', self.engine.dispatch('main', self.lease, 'p', 'wp', serial='fixture'), 'Findings: use the token set.\nARTIFACT: x')
        self.assertNotIn('Prep notes', briefs.card(self.engine, 'a'))  # reported, not accepted
        self.engine.accept('main', self.lease, 'p')
        text = briefs.card(self.engine, 'a')
        self.assertIn('## Prep notes', text)
        self.assertIn('p', text.split('## Prep notes')[1])
        self.assertIn('Findings: use the token set.', text)

    def test_prep_notes_drop_the_self_review_line(self):
        self.task('a')
        self.prep_card('i', 'a')
        self.engine.report('wi', self.engine.dispatch('main', self.lease, 'i', 'wi', serial='fixture'), 'Notes here\nSELF_REVIEW: {"checks": []}')
        self.engine.accept('main', self.lease, 'i')
        text = briefs.card(self.engine, 'a')
        self.assertIn('Notes here', text)
        self.assertNotIn('SELF_REVIEW: {"checks": []}', text)


if __name__ == '__main__':
    unittest.main()
