import ast
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestra_core import guards
from orchestra_core.guards import GUARD_DIGEST_FILES, classify_command, guard_digest, RULES
from orchestra_core.hooks import handle_event
import test_hooks

CONFIG = Path(__file__).resolve().parents[1] / 'plugins/orchestra/config'
CLASSES = {'allow', 'deny', 'release', 'release-multi', 'boundary'}
PLUGIN = Path(__file__).resolve().parents[1] / 'plugins/orchestra'
CORPUS = json.loads((CONFIG / 'guard-corpus.json').read_text())['cases']
MERGED_DELETE_SHAPES = [
    'git branch -D x', 'git branch --delete --force x', 'git branch -df x', 'git branch --del --forc x',
    'git push origin --delete x', 'git push --delete origin x', 'git push origin -d x', 'git push origin --del x']
MERGED_DELETE_DENIED = [
    'git branch -D x y', 'git push origin --delete x y', 'git push origin :x', 'git push https://h/r.git --delete x',
    'git push origin --delete --force x', 'git branch -D -r origin/x', 'git branch -d y && git branch -D x',
    'git branch -D a; git branch -D b', 'cd /o && git branch -D x', 'GIT_DIR=/o git branch -D x']
LONG_OPTIONS = json.loads((Path(__file__).resolve().parent / 'fixtures/git-long-options.json').read_text())


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
                self.assertEqual(set(case) - {'category', 'decision_category', '_doc'}, {'id', 'input', 'class'})
                self.assertIn(case['class'], CLASSES)
                if case['class'] == 'boundary':
                    self.assertIn(case.get('category'), RULES['boundary_categories'])
                else:
                    self.assertNotIn('category', case)
                    if 'decision_category' in case:
                        self.assertEqual((case['class'], case['decision_category']), ('release', 'apiwrite'))
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

    def test_corpus_decision_category_matches(self):
        """SPEC 5.14 item 6: a case may name the Decision category; the guard must report exactly it."""
        all_named = [case for case in CORPUS if 'decision_category' in case]
        for case in all_named:
            with self.subTest(case=case['id']):
                self.assertEqual(classify_command(case['input']['command']).category, case['decision_category'])
        named = [case for case in all_named if case['class'] == 'boundary']
        self.assertGreaterEqual(len(named), 15)
        self.assertEqual({case['decision_category'] for case in named}, {'merged-delete'})
        self.assertEqual({case['decision_category'] for case in all_named if case['class'] == 'release'}, {'apiwrite'})
        by_command = {case['input'].get('command'): case for case in CORPUS}
        for command in MERGED_DELETE_SHAPES:
            with self.subTest(command=command):
                self.assertEqual((by_command[command]['class'], by_command[command]['category'],
                                  by_command[command].get('decision_category')), ('boundary', 'delete', 'merged-delete'))
        for command in MERGED_DELETE_DENIED:
            with self.subTest(command=command):
                self.assertEqual(by_command[command]['class'], 'deny')
        self.assertEqual((by_command['git branch -d -r origin/x']['class'], by_command['git branch -d -r origin/x']['category']),
                         ('boundary', 'delete'))
        self.assertNotIn('decision_category', by_command['git branch -d -r origin/x'])

    def test_merged_delete_decision_carries_kind_remote_branch_and_argv(self):
        local = classify_command('git branch --del --forc x')
        self.assertEqual((local.klass, local.boundary, local.category, local.kind, local.remote, local.branch),
                         ('boundary', 'delete', 'merged-delete', 'local', None, 'x'))
        self.assertEqual(local.argv, ('git', 'branch', '--del', '--forc', 'x'))
        for command in ('git push origin --delete x', 'git push --delete origin x', 'git push origin -d x', 'git push origin --del x'):
            with self.subTest(command=command):
                remote = classify_command(command)
                self.assertEqual((remote.klass, remote.category, remote.kind, remote.remote, remote.branch),
                                 ('boundary', 'merged-delete', 'remote', 'origin', 'x'))
                self.assertEqual(remote.argv, tuple(command.split()))

    def test_merged_delete_stand_alone_reasons(self):
        for command in ('git branch -d y && git branch -D x', 'git branch -D a; git branch -D b', 'cd /o && git branch -D x',
                        'git branch -D x | cat'):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.action, decision.reason), ('deny', 'Execute branch deletions separately'))
        for command in ('git -C $(pwd) branch -D x', 'git -C /o branch -D x', 'git --git-dir=/o branch -D x',
                        'git --work-tree /o push origin --delete x', 'GIT_DIR=/o git branch -D x',
                        'GIT_WORK_TREE=/o git push origin -d x', 'sudo git branch -D x', 'env X=1 git branch -D x',
                        'nice git branch -D x', 'xargs git branch -D x', 'echo x $(git branch -D x)',
                        "bash -c 'git branch -D x'", "sh -c 'git push origin --delete x'"):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.action, decision.reason),
                                 ('deny', 'Branch deletion must run plainly in the session repository'))

    def test_merged_delete_global_config_option_denied(self):
        # R2: a global option before the verb can redirect the remote or the repository the hook checks; fail closed.
        for command in ('git -c core.pager=/tmp/x push origin --delete x2',
                        'git -c core.editor=/h push origin --delete x2',
                        'git --config-env=core.askPass=E push origin --delete x2',
                        'git -c x=y branch -D b', 'git --config-env=x=E branch -D b',
                        'git --namespace=n branch -D b', 'git --namespace n push origin -d x2',
                        'git --exec-path=/x branch -D b', 'git --bare branch -D b', 'git -p push origin --delete x2',
                        'git --no-pager branch -D b'):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.action, decision.reason),
                                 ('deny', 'Branch deletion must run plainly in the session repository'))

    def test_merged_delete_never_widens_what_was_denied(self):
        for command in ('git branch -D x y', 'git branch -D -r origin/x', 'git branch -D --remotes x', 'git branch -D -- x',
                        'git branch -D -u o x', 'git branch -D', 'git branch -D $X', 'git branch -D $(echo x)', 'git branch -D "x y"', 'git branch -D x*',
                        'git push origin --delete x y', 'git push origin --delete', 'git push origin :x',
                        'git push origin --delete :x', 'git push origin --delete x:y', 'git push origin --delete --force x',
                        'git push origin --delete -o x y', 'git push origin --delete --dry-run x', 'git push -n -d origin x',
                        'git push origin --delete +x', 'git push https://h/r.git --delete x', 'git push ./r --delete x',
                        'git push /r --delete x', 'git push git@h:r --delete x', 'git push origin --delete -- x',
                        'git push origin --delete refs/heads/x*', 'git branch -dr origin/x -f'):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'deny', command)

    def test_corpus_covers_every_existing_test_hooks_command(self):
        commands = {case['input'].get('command') for case in CORPUS}
        names = ['MERGED_DELETE_COMMANDS', 'DENY_COMMANDS', 'DENY_GROUPED', 'ALLOW_GROUPED', 'ALLOW_SEMANTIC', 'DENY_SEMANTIC',
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

    def test_inline_walker_resolves_names_concatenations_lists_and_loops(self):
        source = (
            "def one():\n"
            "    hard = 'git reset ' + '--hard'\n"
            "    classify_command(hard)\n"
            "    classify_command('cat <<EOF\\nx ' + hard + '\\nEOF')\n"
            "def two():\n"
            "    a, b = 'git push ', 'origin'\n"
            "    pair = 'p ' + 'one'\n"
            "    self.bash(cwd, pair)\n"
            "def three():\n"
            "    for command in ['l one', 'l two' + ' x']:\n"
            "        classify_command(command)\n"
            "    for command in ('t one',):\n"
            "        self.call(command=command)\n"
            "    names = ['n one', 'n two']\n"
            "    for command in names:\n"
            "        x = {'tool_input': {'command': command}}\n"
            "def four():\n"
            "    for refspec, source, target in [('main', 'm', 'm'), ('HEAD~1:main', 'H', 'm')]:\n"
            "        classify_command('git push origin ' + refspec)\n"
            "def five():\n"
            "    for command in unknown():\n"
            "        classify_command(command)\n"
            "    classify_command(not_bound)\n")
        self.assertEqual(inline_commands(source), {
            'git reset --hard', 'cat <<EOF\nx git reset --hard\nEOF', 'p one',
            'l one', 'l two x', 't one', 'n one', 'n two',
            'git push origin main', 'git push origin HEAD~1:main'})

    def test_inline_walker_scopes_names_to_their_function(self):
        source = (
            "def one():\n"
            "    x = 'bound in one'\n"
            "def two():\n"
            "    classify_command(x)\n")
        self.assertEqual(inline_commands(source), set())

    def test_inline_walker_finds_the_loop_and_concatenated_commands_in_test_hooks(self):
        found = inline_commands((Path(test_hooks.__file__)).read_text())
        loop = ['git push --force origin x', 'git push -f origin x', 'git push --mirror origin',
                'git push origin +x', 'git push --all origin', 'git push --tags origin',
                'git push origin a b', 'git reset --hard',
                'git clean -f', 'git add -A', 'git commit -a -m x',
                'git checkout .', 'git checkout -f x', 'git restore .']
        hard = 'git reset ' + '--hard'
        concatenated = ['cat <<EOF\nx $(' + hard + ')\nEOF',
                        'cat <<EOF\n"$(' + hard + ')"\nEOF',
                        "cat <<EOF\n`" + hard + "` it's\nEOF",
                        'cat <<EOF\necho "\\$(' + hard + ')" "\\`' + hard + '\\`"\nEOF',
                        "cat <<'EOF'\necho '$(" + hard + ")'\nEOF"]
        refspec = ['git push origin ' + r for r in ['main', 'HEAD:main', 'topic:refs/heads/main', 'HEAD~1:main']]
        self.assertEqual(len(loop + concatenated), 19)
        for command in loop + concatenated + refspec:
            with self.subTest(command=command):
                self.assertIn(command, found)

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
        for name in ['UNARMED_RELEASES', 'MULTI_RELEASES', 'STASH_DENIED', 'DENY_GIT_21', 'ALLOW_GIT_21', 'RESTORE_ALLOWED',
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

    def test_mod_fixtures_are_in_sync_with_the_corpus(self):
        result = subprocess.run([sys.executable, str(PLUGIN / 'hooks/mod/fixtures/sync.py'), '--check'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


SOFTEN = {  # corpus id -> the soften level the deny carries; None is a hard deny that normal mode keeps
    'soften-stash': 'warn', 'soften-add-all': 'allow', 'soften-commit-all': 'allow', 'soften-amend': 'warn',
    'soften-push-tags': 'warn', 'soften-push-refspec-colon': 'warn',
    'nosoften-push-prune': None, 'nosoften-push-mirror': None, 'nosoften-stash-then-reset': None,
    'nosoften-stash-then-force-push': None, 'nosoften-push-tags-extra-refspec': None, 'nosoften-push-tags-prune': None}
WORKFLOW = {'workflow-run-release': 'release.yml', 'workflow-run-flags-first': 'deploy.yml'}


class SoftenAndGhRulesTest(unittest.TestCase):
    """D4 2.7: the classifier keeps the protect verdict and marks the denies normal mode may relax; new gh rules."""

    def by_id(self, case_id):
        return next(case for case in CORPUS if case['id'] == case_id)

    def test_soften_level_rides_the_decision_for_every_listed_case(self):
        for case_id, level in SOFTEN.items():
            with self.subTest(case=case_id):
                decision = classify_command(self.by_id(case_id)['input']['command'])
                self.assertEqual((decision.klass, decision.soften), ('deny', level))

    def test_only_deny_decisions_soften_and_default_is_none(self):
        self.assertIsNone(classify_command('git status').soften)
        self.assertIsNone(classify_command('git reset --hard').soften)
        self.assertIsNone(classify_command('git push origin main').soften)
        self.assertIsNone(guards.Decision().soften)
        self.assertIsNone(guards.Decision().workflow)

    def test_two_softened_denies_keep_the_stricter_level(self):
        self.assertEqual(classify_command('git add -A && git stash').soften, 'warn')
        self.assertEqual(classify_command('git stash && git add -A').soften, 'warn')
        self.assertEqual(classify_command("bash -c 'git add -A' && git commit --amend").soften, 'warn')
        self.assertEqual(classify_command('git add -A; git commit -am x').soften, 'allow')

    def test_a_hard_deny_anywhere_in_the_command_drops_soften(self):
        for command in ('git stash; git clean -f', "bash -c 'git stash; git checkout .'", 'echo $(git stash) $(git reset --hard)',
                        'git add -A && echo "$(git push --force origin x)"', 'git stash\ngit branch -D a b'):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.soften), ('deny', None))

    def test_softened_deny_keeps_its_protect_reason(self):
        self.assertEqual(classify_command('git commit --amend').reason, 'Amend rewrites history; make a new commit instead')
        self.assertEqual(classify_command('git push --tags origin').reason, 'Push needs one explicit remote and refspec')
        self.assertEqual(classify_command('git push origin :x').reason, 'Push needs one non-deleting refspec')

    def test_workflow_name_rides_the_decision(self):
        for case_id, name in WORKFLOW.items():
            with self.subTest(case=case_id):
                decision = classify_command(self.by_id(case_id)['input']['command'])
                self.assertEqual((decision.klass, decision.workflow), ('release', name))
        self.assertIsNone(classify_command('gh workflow run').workflow)
        self.assertIsNone(classify_command('gh api -X DELETE repos/o/r').workflow)

    def test_gh_decision_categories(self):
        for command, category in [('gh prm 12', 'ghcustom'), ('gh pr edit 12 --base main', 'prbase'), ('gh pr edit 12 -Bmain', 'prbase'),
                                  ('gh pr edit 12 --base=main', 'prbase'), ('gh api -X DELETE repos/o/r', 'apiwrite'),
                                  ('gh api -X POST repos/o/r/git/refs -f ref=x', 'providerrelease')]:
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.category), ('release', category))

    def test_gh_config_boundaries_and_builtins(self):
        for command in ('gh alias set a b', 'gh alias import f', 'gh alias delete a', 'gh extension install o/r', 'gh ext list'):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.klass, decision.boundary), ('boundary', 'config'))
        for command in ('gh alias list', 'gh pr view 3', 'gh issue list', 'gh repo view', 'gh run view 1', 'gh auth status', 'gh',
                        'gh --help', 'gh -R o/r pr view'):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')

    def test_gh_repo_flag_does_not_hide_the_pair(self):
        pairs = [('gh -R o/r pr merge 7 --admin', 'gh pr merge 7 --admin'), ('gh --repo o/r pr merge 7', 'gh pr merge 7'),
                 ('gh --repo=o/r pr merge 7', 'gh pr merge 7'), ('gh -Ro/r pr merge 7', 'gh pr merge 7'),
                 ('gh pr -R o/r merge 7', 'gh pr merge 7'), ('gh pr merge -R o/r 7', 'gh pr merge 7'),
                 ('gh -R o/r release delete v1 -y', 'gh release delete v1 -y'), ('gh -R o/r repo delete --yes', 'gh repo delete --yes'),
                 ('gh -R o/r release create v1', 'gh release create v1'), ('gh -R o/r workflow run x', 'gh workflow run x'),
                 ('gh -R o/r pr edit 7 --base main', 'gh pr edit 7 --base main'), ('gh -R o/r prm 7', 'gh prm 7'),
                 ('gh -R', 'gh'), ('gh pr merge -R', 'gh pr merge')]
        for flagged, plain in pairs:
            with self.subTest(command=flagged):
                got, want = classify_command(flagged), classify_command(plain)
                self.assertEqual((got.klass, got.category, got.boundary, got.workflow),
                                 (want.klass, want.category, want.boundary, want.workflow))
                self.assertEqual(got.argv, tuple(flagged.split()) if got.argv else got.argv)
        self.assertEqual(classify_command('gh -R o/r workflow run x').workflow, 'x')
        for command in ('gh pr list -R o/r', 'gh pr view -R o/r 7', 'gh release list --repo o/r'):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow')
        with tempfile.TemporaryDirectory() as state, mock.patch.dict(os.environ, {'XDG_STATE_HOME': state}):
            for command in ('gh -R o/r pr merge 7 --admin', 'gh -R o/r release delete v1 -y'):
                with self.subTest(hook=command):
                    payload = {'cwd': state, 'tool_name': 'Bash', 'tool_input': {'command': command}}
                    result = handle_event('PreToolUse', payload, mode='protect', armed=True, autonomy=True)
                    self.assertEqual(result.output.get('hookSpecificOutput', {}).get('permissionDecision'), 'deny')

    def test_line_continuation_is_joined(self):
        nl = chr(10)
        cont = chr(92) + nl  # A backslash and a real newline.
        pairs = [('git ' + cont + 'push --force origin main', 'git push --force origin main'),
                 ('gh pr ' + cont + 'merge 7 --admin', 'gh pr merge 7 --admin'),
                 ('git branch ' + cont + '-D x', 'git branch -D x'),
                 ('rm -r' + cont + 'f /', 'rm -rf /'),
                 ('gh ' + cont + '-R o/r pr merge 7', 'gh -R o/r pr merge 7'),
                 ("bash -c 'git " + cont + "push --force origin main'", "bash -c 'git push --force origin main'"),
                 ('echo $(git ' + cont + 'push --force origin main)', 'echo $(git push --force origin main)'),
                 ('echo "it\'s" # c' + nl + 'git ' + cont + 'push --force origin main',
                  'echo "it\'s" # c' + nl + 'git push --force origin main'),
                 ('cat <<EOF' + nl + "don't" + nl + 'EOF' + nl + 'git ' + cont + 'push --force origin main',
                  'cat <<EOF' + nl + "don't" + nl + 'EOF' + nl + 'git push --force origin main')]
        for continued, joined in pairs:
            with self.subTest(command=continued):
                got, want = classify_command(continued), classify_command(joined)
                self.assertEqual((got.klass, got.category, got.boundary), (want.klass, want.category, want.boundary))
        self.assertNotEqual(classify_command(pairs[0][0]).klass, 'allow')
        self.assertIsNotNone(classify_command(pairs[2][0]).boundary)
        self.assertEqual(classify_command("echo 'git " + cont + "push --force origin main'").klass, 'allow')
        with tempfile.TemporaryDirectory() as state, mock.patch.dict(os.environ, {'XDG_STATE_HOME': state}):
            for command in (pairs[0][0], pairs[1][0]):
                with self.subTest(hook=command):
                    payload = {'cwd': state, 'tool_name': 'Bash', 'tool_input': {'command': command}}
                    result = handle_event('PreToolUse', payload, mode='protect', armed=True, autonomy=True)
                    self.assertEqual(result.output.get('hookSpecificOutput', {}).get('permissionDecision'), 'deny')

    def test_quoted_heredoc_keeps_continuation(self):
        # Bash keeps a backslash-newline inside a quoted-delimiter heredoc body, so the delimiter line closes it.
        nl, bs = chr(10), chr(92)
        for opener in ("<<'EOF'", '<<"EOF"', '<<' + bs + 'EOF'):
            for command, klass in (('git reset --hard', 'deny'), ('gh release create v1', 'release'),
                                   ('git push --force origin main', 'deny')):
                # Bash runs `command`, then the stray `EOF` line; the body without its continuation reads the same.
                text = 'cat ' + opener + nl + 'note ' + bs + nl + 'EOF' + nl + command + nl + 'EOF'
                with self.subTest(opener=opener, command=command):
                    got, want = classify_command(text), classify_command(text.replace(bs + nl, nl))
                    self.assertEqual(classify_command(command).klass, klass)
                    self.assertTrue(want.klass.startswith(klass), want.klass)
                    self.assertEqual((got.klass, got.category, got.boundary), (want.klass, want.category, want.boundary))

    def test_continued_command_after_quoted_heredoc(self):
        # Bash closes a quoted-delimiter heredoc at the first delimiter line (its body keeps the backslash-newline),
        # then joins the continued command after it. The verdict is that command's, or stricter.
        nl, bs, tab = chr(10), chr(92), chr(9)
        commands = (('git reset ' + bs + nl + '--hard', 'deny'), ('gh release ' + bs + nl + 'create v1', 'release'),
                    ('gh release ' + bs + nl + 'delete v1', 'boundary'))
        texts = []
        for opener in ("<<'EOF'", '<<"EOF"', '<<' + bs + 'EOF'):
            texts += [('cat ' + opener + nl + 'note ' + bs + nl + 'EOF' + nl + command + nl + 'EOF', command)
                      for command, _ in commands]
        texts += [("cat <<'A' <<'B'" + nl + 'a ' + bs + nl + 'A' + nl + 'b ' + bs + nl + 'B' + nl + commands[0][0] + nl + 'A' + nl + 'B',
                   commands[0][0]),
                  # The unquoted body joins `a \` with `A`, so the next `A` line closes it.
                  ("cat <<A <<'B'" + nl + 'a ' + bs + nl + 'A' + nl + 'A' + nl + 'b ' + bs + nl + 'B' + nl + commands[2][0] + nl + 'B',
                   commands[2][0]),
                  ("cat <<-'EOF'" + nl + 'note ' + bs + nl + tab + 'EOF' + nl + commands[1][0] + nl + 'EOF', commands[1][0])]
        for text, command in texts:
            joined = command.replace(bs + nl, '')
            with self.subTest(command=text):
                got, want = classify_command(text), classify_command(joined)
                self.assertEqual(want.klass, dict(commands)[command])
                self.assertGreaterEqual(guards._RANK.get(got.klass, 0), guards._RANK[want.klass], got)
                if want.boundary:
                    self.assertIn(got.klass, ('boundary', 'release', 'release-multi', 'deny'))

    def test_gh_api_write_forms(self):
        for command in ('gh api repos/o/r -f default_branch=x', 'gh api repos/o/r -F a=b', 'gh api repos/o/r --field a=b',
                        'gh api repos/o/r --raw-field a=b', 'gh api repos/o/r -fa=b', 'gh api repos/o/r --input=x.json',
                        'gh api -X delete repos/o/r', 'gh api -iXDELETE repos/o/r', 'gh api -H "A: b" -X DELETE repos/o/r',
                        'gh api repos/o/r --method DELETE', 'gh api -X PATCH /repos/o/r', 'gh api -X PATCH https://api.github.com/repos/o/r',
                        'gh api -X POST repos/o/r/pulls/3/reviews%2e%2e/x -f a=b', 'gh api -X PUT repos/o/r/pulls', 'gh api -X POST -f a=b'):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'release', command)
        for command in ('gh api repos/o/r', 'gh api -X GET repos/o/r -f a=b', 'gh api --method=get repos/o/r -F a=b', 'gh api -H "A: b" repos/o/r',
                        'gh api repos/o/r/issues/3/comments -f body=x', 'gh api -X POST /repos/o/r/pulls -f title=t',
                        'gh api -X POST https://api.github.com/repos/o/r/pulls?x=1 -f title=t',
                        'gh api graphql -f query=query', 'gh api -X POST repos/o/r/pulls/3/comments -f body=x'):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, 'allow', command)

    def test_gh_api_write_endpoint_data_and_allow_list_data(self):
        release = RULES['release']
        self.assertTrue(all(isinstance(x, str) for x in release['gh_api_write_endpoints']))
        self.assertEqual(sorted(method for method, _ in release['gh_api_autonomy_allow']), ['POST'] * 4)
        self.assertEqual(sorted(path for _, path in release['gh_api_autonomy_allow']),
                         ['repos/*/*/issues/*/comments', 'repos/*/*/pulls', 'repos/*/*/pulls/*/comments', 'repos/*/*/pulls/*/reviews'])
        self.assertIn('pr', RULES['gh_builtin'])
        self.assertNotIn('prm', RULES['gh_builtin'])
        self.assertEqual(RULES['tools']['scheduler'], ['CronCreate', 'ScheduleWakeup', 'RemoteTrigger'])
        self.assertEqual(RULES['protected']['autonomy_files'], ['.claude/settings.json', '.claude/settings.local.json'])
        self.assertEqual(RULES['soften'], {'stash': 'warn', 'wholesaleAdd': 'allow', 'commitAll': 'allow', 'amend': 'warn',
                                           'pushMulti': 'warn', 'pushRefspec': 'warn'})


LONG_OPTION_DENY = [
    'git add --al', 'git add --a', 'git add --upd', 'git add --no-ignore-rem', 'git reset --har', 'git clean --forc',
    'git clean --f', 'git branch --del --forc x y', 'git checkout --forc', 'git switch --disc', 'git push --mir origin',
    'git push --ta origin', 'git push --pru origin', 'git push --al origin', 'git commit --am -m x', 'git commit --amend',
    'git clean -f --dry']
CHAIN = 'git status && git diff --quiet && git worktree remove X && rmdir Y || true'


class LongOptionAbbreviationTest(unittest.TestCase):
    """SPEC 5.15: a unique long-option prefix counts as the guarded option; exemptions count only in full."""

    def by_command(self):
        return {case['input'].get('command'): case for case in CORPUS}

    def test_fixture_pins_the_ten_verbs_and_the_git_version(self):
        self.assertRegex(LONG_OPTIONS['git_version'], r'^\d+\.\d+\.\d+')
        self.assertEqual(set(LONG_OPTIONS['verbs']),
                         {'add', 'reset', 'clean', 'branch', 'checkout', 'switch', 'restore', 'push', 'commit', 'tag'})
        for verb, options in LONG_OPTIONS['verbs'].items():
            self.assertTrue(options, verb)
            self.assertTrue(all(x.startswith('--') and len(x) > 2 and not x.endswith('=') for x in options), verb)

    def test_no_harmless_option_is_prefix_of_guarded_option(self):
        self.assertEqual(set(LONG_OPTIONS['verbs']), set(guards._LONG_GUARDED))
        for verb, options in LONG_OPTIONS['verbs'].items():
            guarded = set(guards._LONG_GUARDED[verb])
            for option in options:
                if option in guarded:
                    continue
                for target in guarded:
                    with self.subTest(verb=verb, option=option, guarded=target):
                        self.assertFalse(target.startswith(option), f'{option} is a harmless prefix of {target}')

    def test_long_prefix_reads_a_strict_prefix_as_the_first_guarded_option(self):
        guarded = ('--all', '--amend')
        self.assertEqual(guards._long_prefix('commit', '--am', guarded), '--amend')
        self.assertEqual(guards._long_prefix('commit', '--am=x', guarded), '--amend')
        self.assertEqual(guards._long_prefix('commit', '--a', guarded), '--all')
        for token in ('--amend', '--', '-a', '-am', 'am', '--x', '--amendx', ''):
            with self.subTest(token=token):
                self.assertIsNone(guards._long_prefix('commit', token, guarded))
        self.assertIsNone(guards._long_prefix('worktree', '--am', guarded))
        self.assertIsNone(guards._long_prefix('log', '--am', guarded))

    def test_corpus_has_the_5_15_rows_with_their_classes(self):
        by_command = self.by_command()
        for command in LONG_OPTION_DENY:
            with self.subTest(command=command):
                self.assertEqual(by_command[command]['class'], 'deny')
        self.assertEqual(by_command['git push --push-o=x origin main']['class'], 'release')
        self.assertEqual(by_command['git commit -m x file']['class'], 'allow')

    def test_every_full_spelling_keeps_its_class_apart_from_amend(self):
        expected = {'git reset --hard': 'deny', 'git clean -f': 'deny', 'git clean -f --dry-run': 'allow',
                    'git branch -d --force x': 'boundary', 'git branch --delete x': 'boundary',
                    'git push --force origin x': 'deny', 'git push --delete origin x': 'boundary',
                    'git restore --staged .': 'allow', 'git switch --force x': 'deny',
                    'git commit --all -m x': 'deny', 'git commit -m x': 'allow', 'git tag --delete v1': 'boundary',
                    'git worktree remove x': 'boundary', 'git worktree rem x': 'allow'}
        for command, klass in expected.items():
            with self.subTest(command=command):
                self.assertEqual(classify_command(command).klass, klass)

    def test_amend_is_denied_with_its_reason_in_full_and_abbreviated(self):
        for command in ('git commit --amend', 'git commit --am -m x', 'git commit --amen', 'git commit -m x --amend'):
            with self.subTest(command=command):
                decision = classify_command(command)
                self.assertEqual((decision.action, decision.reason), ('deny', 'Amend rewrites history; make a new commit instead'))
        self.assertEqual(classify_command('git commit -m --amend').action, 'allow')

    def test_commit_guarded_flags_come_from_the_rules_table(self):
        self.assertEqual(RULES['git']['commit_guarded_flags'], ['--amend'])


class ChainRegressionTest(unittest.TestCase):
    """SPEC 5.16 item 7: the literal chain and its 13 variants are boundary/delete (regression)."""

    def test_corpus_has_the_chain_and_13_variants_as_boundary_delete(self):
        rows = [case for case in CORPUS if case['id'].startswith('chain-regression-')]
        self.assertEqual(len(rows), 14)
        self.assertEqual(rows[0]['input']['command'], CHAIN)
        for case in rows:
            with self.subTest(case=case['id']):
                self.assertEqual((case['class'], case['category']), ('boundary', 'delete'))


def _nested_shells(levels, width):
    """The rf_security finding 2 input: wrapper option substitutions around nested `bash -c` bodies."""
    body = 'git status'
    for _ in range(levels):
        body = 'sudo -u $(a) x ' + ' '.join(f'$(b) bash -c {shlex.quote(body)}' for _ in range(width))
    return body + '; git ' + 'reset --hard'


class ReadingBudgetTest(unittest.TestCase):
    """FX6: one budget of extra readings per call bounds classification time; ordinary commands never reach it."""

    def test_crafted_nested_shells_deny_well_inside_the_hook_timeout(self):
        for levels, width in ((5, 2), (4, 4), (6, 2), (5, 3)):  # 14, 38, 78 and 97 KB
            command = _nested_shells(levels, width)
            with self.subTest(size=len(command)):
                start = time.perf_counter()
                decision = classify_command(command)
                self.assertLess(time.perf_counter() - start, 5)
                self.assertEqual(decision.action, 'deny')

    def test_spent_budget_denies_as_malformed(self):
        with mock.patch.object(guards, '_READING_BUDGET', 2):
            decision = classify_command('sudo -u $(whoami) $(echo) x $(echo) y $(echo) ls')
        self.assertEqual((decision.action, decision.category), ('deny', 'malformed'))
        self.assertEqual(classify_command('sudo -u $(whoami) $(echo) x $(echo) y $(echo) ls').action, 'allow')

    def test_corpus_commands_stay_far_below_the_budget(self):
        for case in CORPUS:
            if 'command' in case['input']:
                with self.subTest(case=case['id']):
                    classify_command(case['input']['command'])
                    self.assertLess(guards._READING_BUDGET - guards._BUDGET['left'], guards._READING_BUDGET // 4)


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
    """Command-like string values reaching a sink: `classify_command(...)` arguments, payload
    `command`/`cmd` values, `command=` keywords and the second argument of a `bash(cwd, command)`
    helper. A value is a literal, a `+` concatenation of values, or a name bound in the same
    function (or an enclosing scope) to those, to a list of them, or by a `for` loop over a list
    (a tuple target takes the matching tuple element). Patch payloads sent as `apply_patch` input
    are not shell commands."""
    tree = ast.parse(source)
    patch_dicts = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'apply_patch':
            patch_dicts.update(id(arg) for arg in node.args[1:])
    found = set()
    functions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def own_nodes(scope):
        """Nodes of this scope, not descending into nested function scopes."""
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            node = stack.pop()
            yield node
            if not isinstance(node, functions):
                stack.extend(ast.iter_child_nodes(node))

    def values(node, env):
        """The set of strings the expression can take, or None when it is not statically known."""
        if isinstance(node, ast.Constant):
            return {node.value} if isinstance(node.value, str) else None
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = values(node.left, env), values(node.right, env)
            return {a + b for a in left for b in right} if left and right else None
        return None

    def items(node, env):
        """The elements of an iterable expression: a list, tuple or a name bound to one."""
        if isinstance(node, ast.Name):
            return env.get(('list', node.id))
        if isinstance(node, (ast.List, ast.Tuple)):
            return list(node.elts)
        return None

    def bind(env, name, strings):
        if strings:
            env.setdefault(name, set()).update(strings)

    def scope_env(scope, parent):
        env = {key: set(value) if isinstance(value, set) else list(value) for key, value in parent.items()}
        nodes = list(own_nodes(scope))
        for _ in range(3):  # Bindings may depend on later ones; a few passes settle the chains.
            for node in nodes:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    bind(env, name, values(node.value, env))
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        env[('list', name)] = list(node.value.elts)
                elif isinstance(node, (ast.For, ast.comprehension)):
                    elements = items(node.iter, env)
                    if elements is None:
                        continue
                    if isinstance(node.target, ast.Name):
                        for element in elements:
                            bind(env, node.target.id, values(element, env))
                    elif isinstance(node.target, ast.Tuple):
                        for element in elements:
                            if isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == len(node.target.elts):
                                for target, part in zip(node.target.elts, element.elts):
                                    if isinstance(target, ast.Name):
                                        bind(env, target.id, values(part, env))
        return env, nodes

    def literal(node, env):
        found.update(values(node, env) or ())

    def visit(scope, parent):
        env, nodes = scope_env(scope, parent)
        for node in nodes:
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
                if name == 'classify_command' and node.args:
                    literal(node.args[0], env)
                if name == 'bash' and len(node.args) > 1:
                    literal(node.args[1], env)
                for keyword in node.keywords:
                    if keyword.arg == 'command':
                        literal(keyword.value, env)
            elif isinstance(node, ast.Dict) and id(node) not in patch_dicts:
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in ('command', 'cmd'):
                        literal(value, env)
            if isinstance(node, functions):
                visit(node, env)

    visit(tree, {})
    return found


SUITE_COMMANDS = [
    'pytest', 'pytest -q tests', 'python -m pytest', 'python3 -m pytest -x', 'python -m unittest',
    'python3 -m unittest discover -s tests', 'python3 -m unittest tests.test_hooks tests.test_guard_corpus',
    'npm test', 'npm run test', 'npm run test:e2e', 'pnpm test', 'yarn test', 'npx vitest', 'npx vitest run',
    'npx jest', 'npx playwright test', 'go test ./...', 'cargo test', 'make test', 'cd pkg && pytest',
    'env CI=1 npm test', 'time pytest', 'bash -c "pytest -q"', '.venv/bin/pytest', 'uv run pytest',
    'pytest tests/a.py::test_x tests/b.py', 'python -m pytest -k slow',
    'python3 -munittest discover', 'python3 -munittest', 'npm t', 'pnpm t', 'coverage run -m pytest',
    'coverage run --branch -m unittest discover', 'python3 -m unittest src.app.tests', 'python -m unittest tests.test_x',
]
NOT_SUITE_COMMANDS = [
    'npm run build', 'npm install', 'echo pytest', 'grep unittest tests/test_hooks.py', 'cat package.json',
    'git log --oneline', 'python3 script.py', 'python3 -m json.tool x.json', 'ls tests', 'go build ./...',
    'cargo build', 'make build', 'yarn install', 'npx tsc', 'npx playwright install',
    'coverage report', 'coverage run script.py', 'npm tag', 'pnpm tsc',
]
TARGETED_PROBES = [
    'python -m unittest tests.test_x.Class.test_y', 'python3 -m unittest -v tests.test_x.Class.test_y',
    'pytest tests/test_x.py::test_y', 'pytest -q tests/test_x.py::Class::test_y', 'python -m pytest tests/test_x.py::test_y',
    'python3 -munittest tests.test_x.Class.test_y', 'coverage run -m unittest tests.test_x.Class.test_y',
    'coverage run -m pytest tests/test_x.py::test_y',
]


class TestSuiteClassifierTest(unittest.TestCase):
    def test_suite_commands(self):
        for command in SUITE_COMMANDS:
            with self.subTest(command=command):
                self.assertTrue(guards.runs_test_suite(command))

    def test_near_misses_probes_and_non_strings(self):
        for command in NOT_SUITE_COMMANDS + TARGETED_PROBES + ['', "git 'reset", None, 5]:
            with self.subTest(command=command):
                self.assertFalse(guards.runs_test_suite(command))

    def test_a_probe_beside_a_suite_is_still_a_suite(self):
        self.assertTrue(guards.runs_test_suite('pytest tests/a.py::t && pytest'))
        self.assertTrue(guards.runs_test_suite('python -m unittest tests.test_x.Class.test_y tests.test_z'))


if __name__ == '__main__':
    unittest.main()
