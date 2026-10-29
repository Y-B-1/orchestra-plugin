"""Layout checks for the shipped plugin: manifests, hook commands, agent and skill frontmatter, no private content."""
import getpass, json, re, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
MODELS = {'claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'}
AGENTS = {'builder', 'builder-mechanical', 'builder-cleanup', 'reviewer', 'reviewer-light', 'reviewer-standards',
          'planner', 'critic', 'investigator', 'investigator-research', 'operator'}


def frontmatter(path):
    text = path.read_text()
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not match:
        raise AssertionError(f'{path} has no frontmatter')
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(':')
        if sep and not key.startswith(' '):
            fields[key.strip()] = value.strip().strip('"')
    return fields


def private_words():
    """The local account name and the git email: neither may appear in a shipped file. The git user name is not
    checked, because the public repository URL carries the owner's account name."""
    email = subprocess.run(['git', 'config', 'user.email'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    words = {getpass.getuser(), email, email.partition('@')[0]}
    return {w for w in words if len(w) >= 3}


class ManifestTest(unittest.TestCase):
    def test_manifests_parse_and_agree_on_the_version(self):
        claude = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        portable = json.loads((PLUGIN / 'plugin.json').read_text())
        self.assertEqual(claude['name'], 'orchestra')
        self.assertEqual(claude['version'], portable['version'])

    def test_every_hook_command_points_at_a_file_that_exists(self):
        hooks = json.loads((PLUGIN / 'hooks/hooks.json').read_text())['hooks']
        self.assertEqual(set(hooks), {'SessionStart', 'PreToolUse', 'Stop'})
        for event, groups in hooks.items():
            for group in groups:
                for hook in group['hooks']:
                    paths = re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^"\s]+)', hook['command'])
                    self.assertTrue(paths, f'{event}: {hook["command"]}')
                    for rel in paths:
                        self.assertTrue((PLUGIN / rel).is_file(), f'{event}: {rel} is missing')


class AgentTest(unittest.TestCase):
    def test_every_agent_pins_a_model_effort_and_tools(self):
        files = sorted((PLUGIN / 'agents').glob('*.md'))
        self.assertEqual({f.stem for f in files}, AGENTS)
        for path in files:
            with self.subTest(path.name):
                fields = frontmatter(path)
                self.assertEqual(fields.get('name'), path.stem)
                self.assertTrue(fields.get('description'))
                self.assertIn(fields.get('model'), MODELS)
                self.assertIn(fields.get('effort'), {'low', 'medium', 'high', 'xhigh', 'max'})
                self.assertTrue(fields.get('tools'))


class SkillTest(unittest.TestCase):
    def test_the_skill_has_a_name_and_description_and_stays_short(self):
        path = PLUGIN / 'skills/orchestra/SKILL.md'
        fields = frontmatter(path)
        self.assertEqual(fields.get('name'), 'orchestra')
        self.assertTrue(fields.get('description'))
        self.assertLess(len(path.read_text().splitlines()), 200)


    def test_every_reference_is_named_by_its_skill_and_stays_short(self):
        """A reference loads only when its SKILL.md names it with a condition; an unnamed one is never read."""
        for ref in sorted((PLUGIN / 'skills').glob('*/references/*.md')):
            skill = (ref.parent.parent / 'SKILL.md').read_text()
            with self.subTest(str(ref.relative_to(PLUGIN))):
                self.assertTrue(f'references/{ref.name}' in skill, 'a reference file its skill never names')
                self.assertLessEqual(len(ref.read_text().splitlines()), 60)

    def test_every_skill_is_reachable_short_and_well_formed(self):
        """A skill no agent file or the main skill names is dead weight; one over 70 lines costs every load."""
        readers = (PLUGIN / 'skills/orchestra/SKILL.md').read_text() + ''.join(
            f.read_text() for f in (PLUGIN / 'agents').glob('*.md'))
        for d in sorted((PLUGIN / 'skills').iterdir()):
            if not d.is_dir():
                continue
            with self.subTest(d.name):
                text = (d / 'SKILL.md').read_text()
                fields = frontmatter(d / 'SKILL.md')
                self.assertEqual(fields.get('name'), d.name)
                if d.name != 'orchestra':
                    self.assertTrue('Load when' in fields.get('description', ''), 'a skill without a narrow trigger')
                self.assertLessEqual(len(text.splitlines()), 200 if d.name == 'orchestra' else 70)
                if d.name != 'orchestra':
                    self.assertTrue(f'orchestra:{d.name}' in readers or f'`{d.name}`' in readers, 'a skill nothing names')

    def test_every_agent_that_names_a_skill_can_load_it(self):
        for path in (PLUGIN / 'agents').glob('*.md'):
            body = path.read_text()
            for name in re.findall(r'orchestra:([a-z-]+)', body):
                with self.subTest(path.name, skill=name):
                    self.assertTrue((PLUGIN / 'skills' / name / 'SKILL.md').exists())
                    self.assertIn('Skill', frontmatter(path).get('tools', ''))

class ReviewLoopTest(unittest.TestCase):
    def test_every_agent_loads_no_other_skill_unless_named(self):
        for path in sorted((PLUGIN / 'agents').glob('*.md')):
            self.assertIn('Load no other skill', path.read_text(), path.name)

    def test_no_file_states_a_review_round_cap_other_than_three(self):
        files = list((PLUGIN / 'skills').rglob('*.md')) + list((PLUGIN / 'agents').glob('*.md'))
        words = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'a third': 3, 'third': 3}
        for path in files:
            text = path.read_text().lower()
            for m in re.finditer(r'(?:at most |up to |after |never )?(\d+|one|two|three|four|a third|third) (?:repair )?rounds?', text):
                n = m.group(1)
                n = int(n) if n.isdigit() else words[n]
                if 'review' in text[max(0, m.start() - 200):m.end() + 200] or 'repair' in text[max(0, m.start() - 200):m.end() + 200]:
                    self.assertEqual(n, 3, f'{path.name}: {m.group(0)}')
            self.assertNotIn('review ends there', text, path.name)


class PrivacyTest(unittest.TestCase):
    def test_no_shipped_file_holds_a_personal_path_or_name(self):
        words = private_words()
        for path in PLUGIN.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.png':
                continue
            text = path.read_text(errors='replace')
            with self.subTest(str(path.relative_to(ROOT))):
                self.assertNotIn('/Users/', text)
                self.assertNotIn('/home/', text)
                for word in words:
                    self.assertNotIn(word.lower(), text.lower())


if __name__ == '__main__':
    unittest.main()
