"""Layout checks for the shipped plugin: manifests, hook commands, agent and skill frontmatter, no private content."""
import getpass, json, re, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
MODELS = {'claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'}
AGENTS = {'builder', 'reviewer', 'planner', 'critic', 'investigator'}


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


    def test_every_reference_is_in_the_situation_table_and_stays_short(self):
        skill = (PLUGIN / 'skills/orchestra/SKILL.md').read_text()
        named = set(re.findall(r'`([a-z-]+\.md)`', skill))
        files = {f.name for f in (PLUGIN / 'skills/orchestra/references').glob('*.md')}
        self.assertEqual(named & files, files, 'a reference file no situation loads')
        self.assertTrue({n for n in named if n != 'SKILL.md'} <= files, 'a situation names a missing file')
        for f in (PLUGIN / 'skills/orchestra/references').glob('*.md'):
            with self.subTest(f.name):
                self.assertLessEqual(len(f.read_text().splitlines()), 60)


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
