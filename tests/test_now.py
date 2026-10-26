"""NOW.md: the short present-state file rendered from the board view."""
import os
import pathlib
import sys
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import test_engine as te
from orchestra_core import now


def card(name, state='queued', seq=1, **kw):
    base = dict(id=name, role='builder', mode='implementation', state=state, worker=None, inline=False,
                deps_open=[], review_of=[], files=[name], started_at=None, seq=seq)
    base.update(kw)
    return base


def view(cards, active=True, **kw):
    out = dict(session=dict(active=active, size='small'), autonomy=dict(active=False), cards=cards)
    out.update(kw)
    return out


class RenderTests(unittest.TestCase):
    def test_header_and_run_line(self):
        lines = now.render(view([card('a')])).splitlines()
        self.assertEqual(lines[0], '# Orchestra now')
        self.assertIn('rewritten by the engine', lines[1].lower())
        self.assertIn('do not edit', lines[1].lower())
        run = [l for l in lines if l.startswith('Run:')][0]
        self.assertIn('active', run)
        self.assertIn('size small', run)
        self.assertIn('autonomy off', run)
        armed = now.render(view([card('a')], autonomy=dict(active=True)))
        self.assertIn('autonomy armed', armed)

    def test_open_card_lines_in_seq_order(self):
        cards = [card('b', 'running', seq=2, worker='w1', inline=True, files=['x', 'y']),
                 card('a', 'queued', seq=1, deps_open=['c', 'd']),
                 card('c', 'accepted', seq=3)]
        text = now.render(view(cards))
        lines = text.splitlines()
        self.assertIn('- a builder/implementation queued files: a; waits on: c, d', lines)
        self.assertIn('- b builder/implementation running (w1, inline) files: x, y', lines)
        self.assertLess(text.index('- a '), text.index('- b '))
        self.assertNotIn('- c ', text)
        self.assertEqual(lines[-1], 'Accepted: 1 cards')

    def test_file_limit(self):
        text = now.render(view([card('a', files=['1', '2', '3', '4', '5'])]))
        self.assertIn('files: 1, 2, 3 +2', text)

    def test_next_line(self):
        text = now.render(view([card('a', 'reported')], columns={'reported': ['a']}))
        self.assertIn('Next: orchestra.py accept a', text)
        text = now.render(view([card('a')], startable_now=['a', 'b']))
        self.assertIn('Next: orchestra.py wave a b', text)
        self.assertIn('Next: none', now.render(view([card('a', 'running')])))

    def test_no_run(self):
        for empty in (dict(session=dict(active=False)), view([], active=True), None):
            lines = now.render(empty).splitlines()
            self.assertEqual(lines[0], '# Orchestra now')
            self.assertIn('No active run.', lines)
            self.assertLessEqual(len(lines), 5)

    def test_fifty_card_limit(self):
        cards = [card('c%02d' % i, seq=i, deps_open=['z']) for i in range(60)]
        lines = now.render(view(cards, startable_now=['c00'])).splitlines()
        self.assertLessEqual(len(lines), 60)
        self.assertIn('+10 more', lines)
        self.assertIn('- c49 builder/implementation queued files: c49; waits on: z', lines)
        self.assertFalse([l for l in lines if l.startswith('- c50 ')])

    def test_fifty_open_cards_fit_sixty_lines(self):
        cards = [card('c%02d' % i, seq=i, deps_open=['z']) for i in range(50)]
        lines = now.render(view(cards)).splitlines()
        self.assertLessEqual(len(lines), 60)
        self.assertEqual(lines[-1], 'Accepted: 0 cards')


class RefreshTests(te.EngineFixture):
    def test_writes_rendered_text(self):
        self.task('a')
        self.assertTrue(now.refresh(self.engine))
        path = self.engine.state_dir / 'NOW.md'
        self.assertEqual(path.read_text(), now.render(self.engine.view()))
        self.assertIn('- a builder/implementation queued', path.read_text())
        self.assertEqual([p.name for p in self.engine.state_dir.glob('.now-*')], [])

    def test_uses_atomic_replace(self):
        with mock.patch('os.replace', wraps=os.replace) as replace:
            self.assertTrue(now.refresh(self.engine))
        self.assertEqual(pathlib.Path(replace.call_args[0][1]), self.engine.state_dir / 'NOW.md')
        self.assertEqual(pathlib.Path(replace.call_args[0][0]).parent, self.engine.state_dir)

    def test_view_failure_returns_false(self):
        with mock.patch.object(self.engine, 'view', side_effect=RuntimeError('boom')):
            self.assertFalse(now.refresh(self.engine))
        self.assertFalse((self.engine.state_dir / 'NOW.md').exists())


if __name__ == '__main__':
    unittest.main()
