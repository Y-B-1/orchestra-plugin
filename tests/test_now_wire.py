"""WIRE: briefs point workers at NOW.md and refresh it when a wave is emitted."""
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'
sys.path.insert(0, str(SCRIPTS))

from orchestra_core import briefs

SENTENCE = '(read it only when you need to know what other cards are doing).'
TASK = dict(id='c1', role='builder', mode='implementation', objective='Do it.', inputs=[], files=['a.py'],
            resources=[], acceptance=['It works.'])


class Stub:
    def __init__(self, state):
        self.state_dir = pathlib.Path(state)


class NowWire(unittest.TestCase):
    def emit(self, state, plan):
        prepared = dict(plan=plan, size=1, base='abc')
        result = dict(workers={'c1': 'w1'}, assignments={'c1': 'tok'})
        engine = Stub(state)
        with mock.patch.object(briefs.now, 'refresh') as refresh:
            entries = briefs.emit(engine, prepared, result)
        return entries, refresh, engine

    def test_prompt_names_now_file_after_assignment(self):
        with tempfile.TemporaryDirectory() as state:
            entries, _, engine = self.emit(state, [(TASK, ('Mode: implementation\n', None), ('orchestra:builder', None))])
            lines = entries[0]['prompt'].splitlines()
            self.assertEqual(lines[1], 'Assignment: w1 tok')
            self.assertEqual(lines[2], "Run state now: the run's NOW.md in the state directory that `orchestra.py where` "
                                       "prints " + SENTENCE)  # F77: a worker is never given a path under the state directory
            self.assertNotIn(str(engine.state_dir), entries[0]['prompt'])

    def test_refresh_once_and_inline_gets_no_prompt(self):
        with tempfile.TemporaryDirectory() as state:
            entries, refresh, engine = self.emit(state, [(TASK, ('Mode: implementation\n', None), None)])
            self.assertNotIn('prompt', entries[0])
            refresh.assert_called_once_with(engine)

    def test_rendered_brief_has_run_state_section(self):
        text = briefs.render(TASK, '/repo', 'abc')
        self.assertIn("## Run state\nRun state now: the run's NOW.md in the state directory that `orchestra.py where` prints "
                      + SENTENCE, text)


if __name__ == '__main__':
    unittest.main()
