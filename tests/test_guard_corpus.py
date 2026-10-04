import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestra_core.guards import classify_command, RULES
from orchestra_core.hooks import handle_event
import test_hooks

CONFIG = Path(__file__).resolve().parents[1] / 'plugins/orchestra/config'
CLASSES = {'allow', 'deny', 'release', 'release-multi', 'boundary'}
CORPUS = json.loads((CONFIG / 'guard-corpus.json').read_text())['cases']


def edit_class(case):
    data = case['input']
    payload = {'cwd': data['cwd'], 'tool_name': data['tool'], 'tool_input': {'file_path': data['path']}}
    with tempfile.TemporaryDirectory() as state, mock.patch.dict(os.environ, {'XDG_STATE_HOME': state}):
        result = handle_event('PreToolUse', payload)
    return 'deny' if result.output.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny' else 'allow'


class GuardCorpusTest(unittest.TestCase):
    def test_corpus_shape_and_vocabulary(self):
        self.assertEqual(set(RULES['classes']), CLASSES)
        ids = [case['id'] for case in CORPUS]
        self.assertEqual(len(ids), len(set(ids)))
        for case in CORPUS:
            with self.subTest(case=case['id']):
                self.assertEqual(set(case) - {'category'}, {'id', 'input', 'class'})
                self.assertIn(case['class'], CLASSES)
                if case['class'] == 'boundary':
                    self.assertIn(case.get('category'), RULES['boundary_categories'])
                else:
                    self.assertNotIn('category', case)
                self.assertIn(set(case['input']) - {'cwd'}, [{'command'}, {'tool', 'path'}])

    def test_every_case_matches_the_python_classifier(self):
        for case in CORPUS:
            with self.subTest(case=case['id']):
                if 'command' in case['input']:
                    decision = classify_command(case['input']['command'])
                    self.assertEqual(decision.klass, case['class'], case['input']['command'])
                    self.assertEqual(decision.boundary, case.get('category'))
                else:
                    self.assertEqual(edit_class(case), case['class'], case['input'])

    def test_corpus_covers_every_existing_test_hooks_command(self):
        commands = {case['input'].get('command') for case in CORPUS}
        names = ['DENY_COMMANDS', 'DENY_GROUPED', 'ALLOW_GROUPED', 'ALLOW_SEMANTIC', 'DENY_SEMANTIC',
                 'RELEASE_COMMANDS', 'DENY_PUSH_DESTINATION', 'DENY_MALFORMED']
        for name in names:
            for command in getattr(test_hooks, name):
                with self.subTest(list=name, command=command):
                    self.assertIn(command, commands)

    def test_corpus_covers_the_a_row_cases(self):
        by_command = {case['input'].get('command'): case for case in CORPUS}
        for name in ['UNARMED_RELEASES', 'MULTI_RELEASES', 'STASH_ALLOWED', 'STASH_DENIED', 'RESTORE_ALLOWED',
                     'RESTORE_DENIED', 'SWITCH_DENIED', 'AZ_ALLOWED', 'HEREDOC_DENIED', 'HEREDOC_ALLOWED']:
            for command in getattr(test_hooks, name):
                with self.subTest(list=name, command=command):
                    self.assertIn(command, by_command)

    def test_corpus_has_the_a14_boundary_cases_with_their_category(self):
        by_command = {case['input'].get('command'): case for case in CORPUS}
        for command in test_hooks.BOUNDARY_DELETE:
            self.assertEqual((by_command[command]['class'], by_command[command]['category']), ('boundary', 'delete'), command)
        for command in test_hooks.BOUNDARY_MERGE:
            self.assertEqual((by_command[command]['class'], by_command[command]['category']), ('boundary', 'merge'), command)

    def test_linked_worktree_commands_are_state_independent_corpus_cases(self):
        by_command = {case['input'].get('command'): case for case in CORPUS}
        for command, klass in test_hooks.LINKED_WORKTREE_COMMANDS.items():
            with self.subTest(command=command):
                self.assertEqual(by_command[command]['class'], klass)

    def test_edit_cases_include_the_nested_harness_directory_regression(self):
        edits = [case for case in CORPUS if 'tool' in case['input']]
        nested = [c for c in edits if c['input']['path'] == '.claude/hooks.json' and c['input']['cwd'].endswith('/.claude/plugins/x')]
        self.assertTrue(nested)
        self.assertTrue(all(c['class'] == 'deny' for c in nested))


if __name__ == '__main__':
    unittest.main()
