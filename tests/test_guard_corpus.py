import ast
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestra_core.guards import GUARD_DIGEST_FILES, classify_command, guard_digest, RULES
from orchestra_core.hooks import handle_event
import test_hooks

CONFIG = Path(__file__).resolve().parents[1] / 'plugins/orchestra/config'
CLASSES = {'allow', 'deny', 'release', 'release-multi', 'boundary'}
PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
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

    def test_corpus_covers_every_inline_test_hooks_command(self):
        """R2 F2: walk test_hooks.py with ast, so a command written inline in a test cannot escape."""
        commands = {case['input'].get('command') for case in CORPUS}
        found = inline_commands((Path(test_hooks.__file__)).read_text())
        self.assertGreater(len(found), 10)
        for command in sorted(found):
            with self.subTest(command=command):
                self.assertIn(command, commands)

    def test_inline_walker_finds_classify_calls_payloads_and_helper_calls(self):
        source = (
            "classify_command('a one')\n"
            "x = {'tool_input': {'command': 'b two'}}\n"
            "self.bash(cwd, 'c three')\n"
            "self.pre('apply_patch', {'command': '*** patch'})\n"
            "self.call(command='d four')\n")
        self.assertEqual(inline_commands(source), {'a one', 'b two', 'c three', 'd four'})

    def test_pre_b2_inline_commands_are_in_the_corpus(self):
        commands = {case['input'].get('command') for case in CORPUS}
        for command in PRE_B2_INLINE_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, commands)

    def test_every_rules_key_has_a_doc_entry_and_underscore_keys_are_ignored(self):
        raw = json.loads((CONFIG / 'guard-rules.json').read_text())
        keys = {key for key in raw if not key.startswith('_')}
        self.assertEqual(keys, set(RULES))
        self.assertIsInstance(raw['_doc'], dict)
        for key in keys:
            with self.subTest(key=key):
                self.assertIsInstance(raw['_doc'].get(key), str)
                self.assertTrue(raw['_doc'][key].strip())
        self.assertEqual(set(raw['_doc']) - keys, set())
        self.assertNotIn('_doc', RULES)


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


class GuardDigestTest(unittest.TestCase):
    """SPEC 10.3 guard digest: path, NUL, decimal length, NUL, bytes; missing counts as zero bytes."""

    def scratch(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for rel in GUARD_DIGEST_FILES:
            if (PLUGIN / rel).is_file():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(PLUGIN / rel, root / rel)
        return root

    def test_file_order_and_input_format(self):
        self.assertEqual(GUARD_DIGEST_FILES, ('config/guard-rules.json', 'scripts/orchestra_core/guards.py',
                                              'scripts/orchestra_core/hooks.py', 'hooks/mod/guard.ts'))
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        digest = hashlib.sha256()
        for rel in GUARD_DIGEST_FILES:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            data = rel.encode() * 3
            (root / rel).write_bytes(data)
            digest.update(rel.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
        self.assertEqual(guard_digest(root), digest.hexdigest())

    def test_missing_file_counts_as_zero_bytes(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        digest = hashlib.sha256()
        for rel in GUARD_DIGEST_FILES:
            digest.update(rel.encode() + b'\0' + b'0' + b'\0')
        self.assertEqual(guard_digest(root), digest.hexdigest())

    def test_default_root_is_this_plugin_copy(self):
        self.assertEqual(guard_digest(), guard_digest(PLUGIN))
        self.assertRegex(guard_digest(), r'^[0-9a-f]{64}$')

    def test_digest_changes_when_any_one_of_the_four_files_changes(self):
        root = self.scratch()
        base = guard_digest(root)
        self.assertEqual(base, guard_digest(PLUGIN))
        seen = {base}
        for rel in GUARD_DIGEST_FILES:
            with self.subTest(file=rel):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                before = path.read_bytes() if path.exists() else None
                path.write_bytes((before or b'') + b' ')
                changed = guard_digest(root)
                self.assertNotIn(changed, seen)
                seen.add(changed)
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)
                self.assertEqual(guard_digest(root), base)


PRE_B2_INLINE_COMMANDS = [
    'git push origin', 'git push origin main', 'git push origin HEAD:main:other',
    'git -C other push origin main', 'git -C elsewhere push origin HEAD:main',
    'echo "git push origin HEAD:main"', 'sudo -nu root git push origin HEAD:main',
    "sh -c 'git push origin main'", 'env --chdir=other git push origin main',
]


def inline_commands(source):
    """Command-like string literals: classify_command(...) arguments, payload `command`/`cmd` values,
    `command=` keywords and the second argument of a `bash(cwd, command)` helper. Patch payloads
    sent as `apply_patch` input are not shell commands."""
    tree = ast.parse(source)
    patch_dicts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'apply_patch':
            patch_dicts.update(id(arg) for arg in node.args[1:])
    found = set()

    def literal(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
            if name == 'classify_command' and node.args:
                literal(node.args[0])
            if name == 'bash' and len(node.args) > 1:
                literal(node.args[1])
            for keyword in node.keywords:
                if keyword.arg == 'command':
                    literal(keyword.value)
        elif isinstance(node, ast.Dict) and id(node) not in patch_dicts:
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in ('command', 'cmd'):
                    literal(value)
    return found


if __name__ == '__main__':
    unittest.main()
