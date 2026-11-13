"""Layout checks for the shipped plugin: manifests, hook commands, agent and skill frontmatter, no private content."""
import getpass, json, re, subprocess, tempfile, unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
MODELS = {'opus', 'sonnet', 'haiku'}  # family aliases: each follows the newest model of its family
FABLE = 'fable'  # one agent only: the critic's third point of view
AGENTS = {'builder', 'builder-mechanical', 'builder-cleanup', 'reviewer', 'reviewer-light', 'reviewer-standards',
          'planner', 'critic', 'critic-fable', 'investigator', 'investigator-research', 'operator'}


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


QUOTED = {'"': re.compile(r'"(?:[^"\\]|\\.)*"\s*(?:#.*)?$'), "'": re.compile(r"'(?:[^']|'')*'\s*(?:#.*)?$")}


def model_ok(model, stem):
    """A family alias, or a full id of the same family (claude-fable-... only for the critic)."""
    families = {FABLE} if stem == 'critic-fable' else MODELS
    return model in families or any(re.fullmatch(rf'claude-{f}-[\w.-]+', model or '') for f in families)


def strict_problems(text):
    """Frontmatter lines that a real YAML reader would reject or misread (standard library only, no PyYAML):
    an unquoted value holding a colon and a space or ending in a colon, or a quoted value that is not closed or holds a bare quote."""
    match = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not match:
        return ['no frontmatter']
    problems = []
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(':')
        if not sep or line.startswith((' ', '#', '-')):
            continue
        value = value.strip()
        if value[:1] in ('"', "'"):
            closed = QUOTED[value[0]].match(value)
            if not closed:
                problems.append(f'{key}: quoted value is not closed or holds a bare quote')
        elif ': ' in value or value.endswith(':'):
            problems.append(f'{key}: unquoted value holds a colon and a space or ends in a colon')
    return problems


# Account names CI runners and containers use; they are ordinary words, so they are not private.
GENERIC_ACCOUNTS = {'runner', 'runneradmin', 'root', 'user', 'admin', 'dev', 'test', 'max', 'ubuntu', 'vscode', 'node'}


EMAIL = subprocess.run(['git', 'config', 'user.email'], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # read once


def private_words():
    """The local account name and the git email: neither may appear in a shipped file. The git user name is not
    checked, because the public repository URL carries the owner's account name."""
    words = {getpass.getuser(), EMAIL, EMAIL.partition('@')[0]}
    return {w for w in words if len(w) >= 3 and w.lower() not in GENERIC_ACCOUNTS}


def private_hits(text, words):
    """Words that appear in the text as whole words, case-insensitive."""
    return {w for w in words if re.search(rf'(?<![\w]){re.escape(w)}(?![\w])', text, re.I)}


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
                self.assertTrue(model_ok(fields.get('model'), path.stem), fields.get('model'))
                self.assertIn(fields.get('effort'), {'low', 'medium', 'high', 'xhigh', 'max'})
                self.assertTrue(fields.get('tools'))
        self.assertTrue(model_ok('claude-sonnet-5-5', 'builder'))
        self.assertTrue(model_ok('claude-fable-5-2', 'critic-fable'))
        self.assertFalse(model_ok('claude-opus-5-5', 'critic-fable'))
        self.assertFalse(model_ok('gpt-5', 'builder'))


class FrontmatterTest(unittest.TestCase):
    def test_strict_check_catches_an_unquoted_colon_and_an_unclosed_quote(self):
        self.assertEqual(strict_problems('---\nname: x\ndescription: Use when: a thing\n---\n'),
                         ['description: unquoted value holds a colon and a space or ends in a colon'])
        self.assertTrue(strict_problems('---\nname: x\ndescription: Use when:\n---\n'))
        self.assertEqual(strict_problems('---\nname: x\ndescription: "Use it\n---\n'),
                         ['description: quoted value is not closed or holds a bare quote'])
        self.assertEqual(strict_problems('---\nname: x\ndescription: "Use when: a thing"\n---\n'), [])
        self.assertEqual(strict_problems("---\nname: x\ndescription: 'Use when: x'  # note\n---\n"), [])
        self.assertEqual(strict_problems('---\nname: x\ndescription: "a" # note\n---\n'), [])

    def test_every_skill_and_agent_frontmatter_is_valid_yaml_in_shape(self):
        for path in sorted(PLUGIN.glob('skills/*/SKILL.md')) + sorted(PLUGIN.glob('agents/*.md')):
            with self.subTest(str(path.relative_to(PLUGIN))):
                self.assertEqual(strict_problems(path.read_text()), [])


class WritingTest(unittest.TestCase):
    def test_a_description_stays_short(self):
        """Every description sits in context all the time; a long one costs every session."""
        for path in sorted(PLUGIN.glob('skills/*/SKILL.md')) + sorted(PLUGIN.glob('agents/*.md')):
            with self.subTest(str(path.relative_to(PLUGIN))):
                self.assertLessEqual(len(frontmatter(path).get('description', '').split()), 90)

    def test_a_rule_sentence_lives_in_one_file(self):
        """One source per rule. Agent files may repeat each other, because each loads alone."""
        homes = {}
        for path in sorted(PLUGIN.rglob('*.md')):
            rel = str(path.relative_to(PLUGIN))
            body = re.sub(r'^---\n.*?\n---\n', '', path.read_text(), flags=re.S)
            for sentence in re.split(r'(?<=[.!?])\s+|\n', body):
                sentence = ' '.join(sentence.lstrip('-* 0123456789.').split())
                if len(sentence) >= 70:
                    homes.setdefault(sentence, set()).add(rel)
        for sentence, files in homes.items():
            with self.subTest(sentence[:60]):
                self.assertLessEqual(len({f for f in files if not f.startswith('agents/')}) + (1 if any(f.startswith('agents/') for f in files) else 0), 1,
                                     f'repeated in {sorted(files)}')


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
                self.assertLessEqual(len(ref.read_text().splitlines()), 100)

    def test_no_plugin_file_names_a_repo_only_path(self):
        """An installed plugin has no plugins/orchestra/ folder; pointers use <plugin>/skills/..."""
        for f in sorted(PLUGIN.rglob('*.md')):
            for n, line in enumerate(f.read_text().splitlines(), 1):
                with self.subTest(f'{f.relative_to(PLUGIN)}:{n}'):
                    self.assertNotIn('plugins/orchestra/', line)

    def test_every_reference_path_resolves(self):
        """A pointer to a reference file that does not exist sends an agent looking for nothing."""
        skills = PLUGIN / 'skills'
        for f in sorted(list(PLUGIN.glob('agents/*.md')) + list(skills.glob('**/*.md'))):
            own = f.parent.parent if f.parent.name == 'references' else f.parent
            for n, line in enumerate(f.read_text().splitlines(), 1):
                for m in re.finditer(r'(?:<plugin>/skills/)?(?:([a-z-]+)/)?references/([a-z0-9-]+\.md)', line):
                    skill, name = m.group(1), m.group(2)
                    with self.subTest(f'{f.relative_to(PLUGIN)}:{n} {m.group(0)}'):
                        if skill:
                            self.assertTrue((skills / skill / 'references' / name).is_file())
                        else:
                            named = set(re.findall(r'orchestra:([a-z-]+)', line))
                            homes = [own] + [skills / s for s in named]
                            self.assertTrue(any((h / 'references' / name).is_file() for h in homes),
                                            'a bare references/ path must exist beside this skill or a skill the line names')

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

class WizardTemplateTest(unittest.TestCase):
    TEMPLATE = PLUGIN / 'skills/orchestra/references/wizard-template.sh'

    def test_the_template_is_valid_bash(self):
        self.assertEqual(subprocess.run(['bash', '-n', str(self.TEMPLATE)]).returncode, 0)

    def test_upsert_twice_keeps_one_line_and_the_value_survives_sourcing(self):
        value = "a b # $HOME it's \"q\""
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / '.env'
            script = f'env_upsert KEY "$V"; env_upsert KEY "$V"; env_upsert OTHER x; . "$ENV_FILE"; printf %s "$KEY"'
            r = subprocess.run(['bash', '-c', f'. "{self.TEMPLATE}"; {script}'], capture_output=True, text=True,
                               env={'PATH': '/usr/bin:/bin', 'WIZARD_SOURCE_ONLY': '1', 'ENV_FILE': str(env), 'V': value})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sum(l.startswith('KEY=') for l in env.read_text().splitlines()), 1)
            self.assertTrue(r.stdout.endswith(value), r.stdout)


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
                self.assertEqual(private_hits(text, words), set())

    def test_no_tracked_file_holds_a_credential_or_the_owner_account_name(self):
        secret = re.compile(r'gh[op]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}'
                            r'|sk-ant-api[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')
        words = private_words()
        tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, text=True).stdout.split('\0')
        for name in filter(None, tracked):
            path = ROOT / name
            if not path.is_file() or path.is_symlink() or path.suffix in {'.png', '.lock'} or name == 'package-lock.json':
                continue
            text = path.read_text(errors='replace')
            with self.subTest(name):
                if name != 'tests/test_check.py':  # holds fake credentials as scan fixtures
                    self.assertIsNone(secret.search(text))
                self.assertEqual(private_hits(text, words), set())

    def test_ci_account_name_is_not_private_but_a_real_name_is(self):
        with mock.patch('getpass.getuser', return_value='runner'):
            self.assertNotIn('runner', private_words())
        with mock.patch('getpass.getuser', return_value='jdoe'):
            self.assertIn('jdoe', private_words())
        self.assertEqual(private_hits('see /Users/jdoe/x', {'jdoe'}), {'jdoe'})
        self.assertEqual(private_hits('jdoes', {'jdoe'}), set())


if __name__ == '__main__':
    unittest.main()
