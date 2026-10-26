"""The board as a stone on the path: the prompt hook, the post-agent hook and the Stop hook say what moved and what waits."""
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_engine as te
from orchestra_core import hooks as hooks_module
from orchestra_core.hooks import handle_event

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra'
GOOD = 'STATUS: PASS\nARTIFACT: abc123 clean\nJudged the card.'


def context(reply):
    return reply.get('hookSpecificOutput', {}).get('additionalContext')


class BoardCase(te.EngineFixture):
    def prompt(self, text='next step', engine='default'):
        engine = self.engine if engine == 'default' else engine
        return hooks_module.prompt_board({'prompt': text, 'session_id': 's1'}, engine)

    def stop(self, **payload):
        return handle_event('Stop', payload, engine=self.engine).output

    def seen(self, name):
        path = self.engine.state_dir / name
        return json.loads(path.read_text()) if path.exists() else None

    def report_critic(self, name='c'):
        self.task(name, role='critic', mode='judge', files=[])
        token = self.engine.dispatch('main', self.lease, name, 'w-' + name)
        self.engine.report('w-' + name, token, 'Judged.')
        return token


class PromptTests(BoardCase):
    def test_a_changed_board_adds_one_line_naming_the_cards_then_stores_it(self):
        self.task('a')
        text = context(self.prompt())
        self.assertTrue(text.startswith('Orchestra board: '), text)
        self.assertIn('a', text)
        self.assertEqual(self.seen('board-seen.json')['signature'], hooks_module.delta.signature(self.engine.view()))

    def test_a_second_prompt_with_no_change_adds_nothing(self):
        self.task('a')
        self.prompt()
        self.assertEqual(self.prompt(), {})

    def test_a_moved_card_is_named_with_its_move(self):
        self.task('a')
        self.prompt()
        self.engine.dispatch('main', self.lease, 'a', 'w1')
        text = context(self.prompt())
        self.assertIn('a queued>running', text)

    def test_no_run_adds_nothing(self):
        self.assertEqual(self.prompt(engine=None), {})

    def test_an_inactive_run_adds_nothing(self):
        self.task('a')
        self.engine.interrupt_active()
        self.assertEqual(self.prompt(), {})

    def test_a_board_with_no_cards_adds_nothing(self):
        self.assertEqual(self.prompt(), {})

    def test_a_prompt_from_another_session_adds_nothing(self):
        self.task('a')
        with mock.patch.object(hooks_module, '_other_session', return_value=True):
            self.assertEqual(self.prompt(), {})

    def test_the_prompt_hook_prints_the_line_and_the_approval_flow_is_unchanged(self):
        self.task('a')
        payload = {'cwd': str(self.repo), 'prompt': 'carry on', 'session_id': 's1'}
        with mock.patch.object(hooks_module, '_run_location', return_value=(self.repo, self.engine.state_dir)), \
                mock.patch('sys.stdout', new=io.StringIO()) as out:
            hooks_module._prompt_submit(payload)
        self.assertTrue(context(json.loads(out.getvalue())).startswith('Orchestra board: '))
        with mock.patch.object(hooks_module, '_run_location', return_value=(self.repo, self.engine.state_dir)), \
                mock.patch('orchestra_core.prompt_approval.handle_prompt', return_value={'approval': 1}), \
                mock.patch('sys.stdout', new=io.StringIO()) as out:
            hooks_module._prompt_submit(dict(payload, prompt='approved'))
        self.assertEqual(json.loads(out.getvalue()), {'approval': 1})


class PendingTests(BoardCase):
    def setUp(self):
        super().setUp()
        self.task('c', role='critic', mode='judge', files=[])
        self.token = self.engine.dispatch('main', self.lease, 'c', 'w1')
        self.transcript = self.root / 'agent.jsonl'
        self.transcript.write_text(json.dumps({'type': 'user', 'message': {'role': 'user', 'content': 'Assignment: w1 %s\nGo.' % self.token}}) + '\n')

    def subagent_stop(self, message=GOOD):
        payload = {'agent_id': 'a1', 'agent_type': 'orchestra:critic', 'agent_transcript_path': str(self.transcript),
                   'last_assistant_message': message, 'stop_hook_active': False}
        return handle_event('SubagentStop', payload, engine=self.engine, state_dir=str(self.engine.state_dir)).output

    def post(self, **extra):
        return handle_event('PostToolUse', dict({'tool_name': 'Agent', 'tool_input': {}}, **extra), engine=self.engine).output

    def test_a_recorded_report_writes_pending_delta_and_prints_nothing_new(self):
        self.assertEqual(self.subagent_stop(), {})
        pending = (self.engine.state_dir / 'pending-delta').read_text()
        self.assertIn('c running>reported', pending)

    def test_no_report_recorded_writes_nothing(self):
        self.assertEqual(self.subagent_stop(message='no report lines'), {})
        self.assertFalse((self.engine.state_dir / 'pending-delta').exists())

    def test_post_agent_prints_the_pending_delta_once_and_clears_it(self):
        self.subagent_stop()
        text = context(self.post())
        self.assertTrue(text.startswith('Orchestra board: '), text)
        self.assertIn('c running>reported', text)
        self.assertFalse((self.engine.state_dir / 'pending-delta').exists())
        self.assertEqual(self.post(), {})

    def test_post_agent_without_a_pending_delta_prints_nothing(self):
        self.assertEqual(self.post(), {})

    def test_post_agent_stores_the_board_so_the_next_prompt_adds_nothing(self):
        self.subagent_stop()
        self.post()
        self.assertEqual(self.prompt(), {})

    def test_a_call_made_inside_a_subagent_is_not_delivered(self):
        self.subagent_stop()
        self.assertEqual(self.post(agent_id='a9'), {})
        self.assertTrue((self.engine.state_dir / 'pending-delta').exists())

    def test_two_stops_before_one_delivery_are_both_named(self):
        self.subagent_stop()
        self.task('d', role='critic', mode='judge', files=[])
        token = self.engine.dispatch('main', self.lease, 'd', 'w2')
        self.engine.report('w2', token, GOOD)
        pending = (self.engine.state_dir / 'pending-delta')
        pending.write_text(pending.read_text() + '\n' + 'd running>reported')
        text = context(self.post())
        self.assertIn('c running>reported', text)
        self.assertIn('d running>reported', text)

    def test_the_plugin_registers_post_tool_use_on_agent_and_task(self):
        hooks = json.loads((PLUGIN / 'hooks/claude.json').read_text())['hooks']
        entry = hooks['PostToolUse'][0]
        self.assertEqual(entry['matcher'], 'Agent|Task')
        self.assertIn('PostToolUse --harness claude', entry['hooks'][0]['command'])


class StopTests(BoardCase):
    def test_a_startable_card_blocks_once_with_the_next_command(self):
        self.task('a')
        out = self.stop()
        self.assertEqual(out['decision'], 'block')
        self.assertIn('orchestra.py', out['reason'])
        self.assertIn('a', out['reason'])
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.seen('stop-seen')['signature'], hooks_module.delta.signature(self.engine.view()))

    def test_a_reported_card_names_accept(self):
        self.report_critic()
        out = self.stop()
        self.assertEqual(out['decision'], 'block')
        self.assertIn('accept c', out['reason'])

    def test_a_new_board_signature_blocks_again(self):
        self.task('a')
        self.stop()
        self.task('b')
        self.assertEqual(self.stop()['decision'], 'block')
        self.assertEqual(self.stop(), {})

    def test_only_workers_running_never_blocks(self):
        self.task('a')
        self.engine.dispatch('main', self.lease, 'a', 'w1')
        self.assertEqual(self.stop(), {})

    def test_no_cards_never_blocks(self):
        self.assertEqual(self.stop(), {})

    def test_a_repeated_stop_never_blocks(self):
        self.task('a')
        self.assertEqual(self.stop(stop_hook_active=True), {})

    def test_an_inactive_run_never_blocks(self):
        self.task('a')
        self.engine.interrupt_active()
        self.assertEqual(self.stop(), {})

    def test_a_mock_engine_never_blocks(self):
        engine = mock.Mock()
        engine.hook_stop.return_value = None
        self.assertEqual(handle_event('Stop', {}, engine=engine).output, {})

    def test_the_autonomy_path_is_unchanged(self):
        engine = mock.Mock()
        engine.autonomy_active.return_value = True
        engine.hook_stop.return_value = 'Continue one authorized bounded pass'
        out = handle_event('Stop', {}, engine=engine).output
        self.assertEqual(out, {'decision': 'block', 'reason': 'Continue one authorized bounded pass'})
        engine.view.assert_not_called()

class AcceptableTests(BoardCase):
    """F60: the board names only the reported cards that `accept` would not refuse for the repair chain or a pending review."""

    def built(self, name):
        self.task(name)
        self.engine.report('w-' + name, self.engine.dispatch('main', self.lease, name, 'w-' + name), te.done('Built ' + name))

    def under_repair_with_recheck_running(self):
        self.allow_review()
        self.built('B1')
        path = self.root / 'blocked.json'
        self.review(path, tasks=['B1'], findings=['f'])
        self.engine.record_review('main', self.lease, 'reviewer', path, ['correctness'], ['B1'], findings=['f'])
        self.task('R1', mode='repair', repair_of='B1', files=['B1'])
        self.engine.report('r1', self.engine.dispatch('main', self.lease, 'R1', 'r1'), te.done('Repaired'))
        self.task('L1', role='code-reviewer', mode='final', files=[], review_of=['R1', 'B1'])
        self.engine.dispatch('main', self.lease, 'L1', 'orchestra-L1')

    def test_a_plain_reported_builder_card_is_acceptable_and_the_stop_names_accept(self):
        self.built('B1')
        self.assertEqual(['B1'], self.engine.view()['acceptable_now'])
        out = self.stop()
        self.assertEqual('block', out['decision'])
        self.assertIn('orchestra.py accept B1', out['reason'])
        self.assertEqual({}, self.stop())

    def test_a_card_under_repair_with_its_fix_re_review_running_is_not_acceptable(self):
        self.under_repair_with_recheck_running()
        view = self.engine.view()
        self.assertEqual(['B1', 'R1'], [c['id'] for c in view['cards'] if c['state'] == 'reported'])
        self.assertEqual([], view['acceptable_now'])
        self.assertIsNone(hooks_module.delta.next_command(view))
        self.assertEqual({}, self.stop())

    def test_a_reported_card_a_queued_review_names_is_not_acceptable(self):
        self.built('B1')
        self.task('L1', role='code-reviewer', mode='final', files=[], review_of=['B1'])
        self.assertEqual([], self.engine.view()['acceptable_now'])

    def test_a_builder_card_reported_with_an_unmet_criterion_is_not_acceptable(self):
        self.task('B1')
        unmet = [{'criterion': 'check behavior', 'met': False, 'evidence': 'not yet'}]
        self.engine.report('w-B1', self.engine.dispatch('main', self.lease, 'B1', 'w-B1'), te.done('Built', criteria=unmet))
        view = self.engine.view()
        self.assertEqual(['B1'], hooks_module.delta.ids(view, 'reported'))
        self.assertEqual([], view['acceptable_now'])
        self.assertIsNone(hooks_module.delta.next_command(view))
        self.assertEqual({}, self.stop())

    def test_the_next_command_falls_back_to_the_reported_list_for_an_older_view(self):
        view = {'cards': [{'id': 'c', 'state': 'reported'}]}
        self.assertEqual('orchestra.py accept c', hooks_module.delta.next_command(view))

    def test_a_startable_card_still_blocks_beside_an_unacceptable_reported_one(self):
        self.under_repair_with_recheck_running()
        self.task('S1')
        out = self.stop()
        self.assertEqual('block', out['decision'])
        self.assertIn('wave S1', out['reason'])


if __name__ == '__main__':
    unittest.main()
