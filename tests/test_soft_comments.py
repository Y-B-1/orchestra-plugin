"""E3: in normal mode a trailing `#` comment no longer makes a softened command strict; nothing after it is hidden."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_guard_modes import RepoCase, verdict
from orchestra_core import guards, hooks


class SoftCommentTest(RepoCase):
    def normal(self, command):
        return verdict(self.bash(command, 'normal'))

    def test_a_trailing_comment_keeps_the_softened_verdict_of_the_bare_command(self):
        for bare, want in (('git add -A', 'allow'), ('git commit -a -m x', 'allow'), ('git stash', 'warn'),
                           ('git commit --amend -m x', 'warn')):
            with self.subTest(command=bare):
                self.assertEqual(self.normal(bare), want)
                self.assertEqual(self.normal(bare + ' # note'), want)
                self.assertEqual(self.normal(bare + ' # it\'s a "note"'), want)

    def test_protect_still_denies_the_commented_command(self):
        self.assertEqual(verdict(self.bash('git add -A # note', 'protect')), 'deny')

    def test_a_denied_command_after_the_comment_line_is_still_denied(self):
        for command in ('git add -A # note\ngit push --force origin main',
                        'git add -A # note\ngit push origin --delete main',
                        'git add -A # note\ngit reset --hard',
                        'git add -A # note\ngit push origin :main'):
            with self.subTest(command=command):
                self.assertEqual(self.normal(command), 'deny')

    def test_a_denied_command_before_the_comment_is_still_denied(self):
        self.assertEqual(self.normal('git add -A; git push --force origin main # note'), 'deny')

    def test_a_comment_that_hides_a_substitution_stays_strict(self):
        self.assertEqual(self.normal('git add -A # $(git reset --hard)'), 'deny')

    def test_a_hash_inside_quotes_or_glued_to_a_word_is_not_a_comment(self):
        self.assertEqual(self.normal('git add -A "a # b"'), 'allow')
        self.assertEqual(self.normal('git add -A a#b'), 'allow')
        self.assertEqual(self.normal('git add -A "a # b"; git push --force origin main'), 'deny')
        self.assertEqual(self.normal('git add -A a#b; git push --force origin main'), 'deny')

    def test_an_escaped_hash_is_not_a_comment(self):
        self.assertEqual(self.normal('git add -A \\# x; git push --force origin main'), 'deny')

    def test_a_quote_inside_a_comment_does_not_join_the_next_lines(self):
        self.assertEqual(self.normal("git add -A # it's\ngit push origin --delete main # it's"), 'deny')
        self.assertEqual(self.normal("git add -A # it's\ngit push --force origin main"), 'deny')

    def test_a_hash_the_classifier_may_read_as_a_word_stays_strict(self):
        self.assertEqual(self.normal('git add -A a=(x)#;git push --force origin main'), 'deny')
        self.assertEqual(self.normal('git add -A \\\n#x;git push --force origin main'), 'deny')

    def test_the_word_start_set_is_the_guards_own(self):
        self.assertIs(hooks._WORD_START, guards._WORD_START)


if __name__ == '__main__':
    unittest.main()
