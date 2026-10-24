from pathlib import Path
import unittest

SKILL_DIR = Path(__file__).resolve().parents[1] / 'plugins/orchestra/skills/orchestra'
FILES = ['SKILL.md', 'references/parallel.md', 'references/coordination.md', 'references/repair-rounds.md']


def coordinator_text():
    return '\n'.join((SKILL_DIR / name).read_text() for name in FILES)


class SkillRoutingTests(unittest.TestCase):
    def test_split_by_context(self):
        self.assertIn('Split by context, not by role', coordinator_text())

    def test_model_fit_names_the_inline_refusal(self):
        text = coordinator_text()
        self.assertIn('Model fit', text)
        self.assertIn('the engine refuses it inline', text)
        self.assertIn('another model or a higher effort', text)

    def test_repair_by_failure_kind(self):
        text = coordinator_text()
        self.assertIn('did not try hard enough', text)
        self.assertIn('higher effort', text)
        self.assertIn('lacked knowledge', text)
        self.assertIn('more capable model', text)

    def test_worker_brief_pointer_and_do(self):
        text = coordinator_text()
        self.assertIn('orchestra.py card ID', text)
        self.assertIn('`do`', text)

    def test_no_role_alone_dispatch_rule(self):
        text = coordinator_text()
        self.assertNotIn('the rest to builders through Workflow', text)
        self.assertNotIn('the rest to workers in one Workflow', text)


    def test_a_review_grants_no_external_permission(self):
        """A CLEAN review is evidence for acceptance only; it never stands in for a release permit or the owner."""
        text = (SKILL_DIR / 'references' / 'final-review.md').read_text()
        self.assertIn('A review grants no external permission', text)


if __name__ == '__main__':
    unittest.main()
