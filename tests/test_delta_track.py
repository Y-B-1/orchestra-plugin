"""2.15.1 T2: the board line names the next track step for the main session and keeps the accept-first rule."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_engine as te
from orchestra_core import delta, hooks as hooks_module


def board(track, states=None, **extra):
    cards = [dict(id=i, state=s) for i, s in (states or {'a': 'queued'}).items()]
    return dict(session=dict(active=True), cards=cards, counts={'queued': len(cards)}, startable_now=['a'],
                track=track, **extra)


class TrackLineTests(unittest.TestCase):
    def test_the_line_names_the_main_step_and_its_side_cards(self):
        text = delta.line(board([dict(step=1, card='E2', side=['H', 'M'])]), {})
        self.assertIn('Track: you run E2; side: H, M', text)

    def test_a_step_with_no_side_cards_names_only_the_main_card(self):
        text = delta.line(board([dict(step=1, card='E2', side=[])]), {})
        self.assertTrue(text.endswith('Track: you run E2'), text)

    def test_only_the_first_step_is_named(self):
        text = delta.line(board([dict(step=1, card='E2', side=[]), dict(step=2, card='F1', side=[])]), {})
        self.assertNotIn('F1', text)

    def test_an_acceptable_card_still_comes_first(self):
        view = board([dict(step=1, card='E2', side=[])], {'r': 'reported', 'a': 'queued'}, acceptable_now=['r'])
        text = delta.line(view, {})
        self.assertLess(text.index('accept r'), text.index('Track: you run E2'))

    def test_a_board_with_no_track_adds_no_track_text(self):
        self.assertNotIn('Track', delta.line(board([]), {}))
        view = board([])
        del view['track']
        self.assertNotIn('Track', delta.line(view, {}))

    def test_no_card_fitting_the_session_model_says_so_plainly(self):
        text = delta.line(board([dict(step=1, card=None, side=['a', 'b'], coordinator='prepare briefs and review reports')]), {})
        self.assertIn('Track: no card fits the session model; you coordinate, accept and review; side: a, b', text)


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DocsTests(unittest.TestCase):
    def test_the_skill_says_to_take_the_next_track_step_within_its_byte_budget(self):
        skill = (ROOT / 'plugins/orchestra/skills/orchestra/SKILL.md').read_bytes()
        self.assertIn(b'Take the next track step', skill)
        self.assertIn(b'wait only when no track step is startable', skill)
        self.assertLessEqual(len(skill), 4096)

    def test_hooks_doc_describes_the_lane_and_the_mirror_order(self):
        text = (ROOT / 'docs/hooks.md').read_text()
        self.assertIn('Track lane', text)
        self.assertIn('`accept-ID`', text)
        self.assertIn('Track: you run', text)


class EngineTrackTests(te.EngineFixture):
    def test_the_prompt_line_carries_the_engine_track(self):
        self.engine.record_model('claude-sonnet-5-5', 'medium')
        self.task('a')
        text = hooks_module.prompt_board({'prompt': 'go', 'session_id': 's1'}, self.engine)['hookSpecificOutput']['additionalContext']
        self.assertIn('Track: you run a', text)


if __name__ == '__main__':
    unittest.main()
