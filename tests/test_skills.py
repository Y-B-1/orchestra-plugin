import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
SKILLS = PLUGIN / 'skills'
PHRASES = Path(__file__).resolve().parent / 'skill_phrases'

TABLE = {
    'orchestra': ['SKILL.md', 'references/coordination.md', 'references/briefs.md', 'references/cli.md',
                  'references/triage.md', 'references/handoff.md', 'references/parallel.md',
                  'references/worktrees.md', 'references/finishing.md', 'references/repair-rounds.md',
                  'references/final-review.md', 'references/audit-axes.md', 'references/autonomy.md'],
    'orchestra-worker': ['SKILL.md'],
    'orchestra-investigate': ['SKILL.md', 'references/code.md', 'references/docs.md'],
    'orchestra-design': ['SKILL.md', 'references/design.md', 'references/plan.md', 'references/product.md'],
    'orchestra-critique': ['SKILL.md'] + [f'references/{m}.md' for m in [
        'requirements', 'feasibility', 'scope', 'judge', 'spec', 'standards', 'ledger', 'surface']],
    'orchestra-build': ['SKILL.md'] + [f'references/{m}.md' for m in [
        'implementation', 'frontend', 'sensitive', 'mechanical', 'repair', 'cleanup']],
    'orchestra-review': ['SKILL.md'] + [f'references/{m}.md' for m in [
        'checkpoint', 'final', 'correctness', 'architecture', 'security', 'cleanliness', 'specialists']],
    'orchestra-operate': ['SKILL.md', 'references/gate.md', 'references/cleanup.md', 'references/release.md'],
}
CLI = 'orchestra/references/cli.md'


def files():
    return [f'{d}/{f}' for d, names in TABLE.items() for f in names]


def read(rel):
    return (SKILLS / rel).read_text()


def frontmatter(rel):
    text = read(rel)
    if not text.startswith('---\n'):
        return {}
    fields = {}
    for line in text[4:].split('\n---\n')[0].split('\n'):
        key, sep, value = line.partition(':')
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def roles():
    return json.loads((PLUGIN / 'config/roles.json').read_text())['roles']


class SkillTreeTests(unittest.TestCase):
    def test_every_spec_file_exists_and_nothing_else_is_shipped(self):
        for rel in files():
            self.assertTrue((SKILLS / rel).is_file(), rel)
        actual = {p.relative_to(SKILLS).as_posix() for p in SKILLS.rglob('*') if p.is_file()}
        self.assertEqual(actual, set(files()))

    def test_sentinel_and_stub_lines(self):
        sentinels = {}
        for rel in files():
            lines = read(rel).split('\n')
            if rel == CLI:
                self.assertFalse([l for l in lines if l.startswith(('Sentinel:', 'Stub:'))], rel)
                continue
            found = [l for l in lines if l.startswith('Sentinel:')]
            self.assertEqual(found, [f'Sentinel: {rel}'], rel)
            sentinels[rel] = found[0]
            text = read(rel)
            before = text.split(found[0])[0]
            body = before.split('\n---\n', 1)[1] if before.startswith('---\n') else before
            self.assertTrue(all(l.startswith('Source:') or not l.strip() for l in body.split('\n')), rel)
            if not any(l.startswith('Stub:') for l in lines):
                self.fail(f'{rel} carries no Stub line')
        for a, sa in sentinels.items():
            for b in sentinels:
                if a != b:
                    self.assertNotIn(sa, read(b), (a, b))

    def test_budgets(self):
        for d in TABLE:
            self.assertLessEqual(len(read(f'{d}/SKILL.md').encode()), 4096, d)
        self.assertLessEqual(len(read('orchestra-worker/SKILL.md').encode()), 2048)
        for rel in files():
            if '/references/' in rel and rel not in (CLI, 'orchestra/references/coordination.md'):
                self.assertLessEqual(len(read(rel).encode()), 6144, rel)
        self.assertLessEqual(len(read('orchestra/references/briefs.md').encode()), 1800)

    def test_generated_agent_budgets(self):
        agents = sorted((PLUGIN / 'agents').glob('*.md'))
        self.assertLessEqual((PLUGIN / 'agents/orchestrator.md').stat().st_size, 10500)
        for path in agents:
            if path.name != 'orchestrator.md':
                self.assertLessEqual(path.stat().st_size, 2650, path.name)
        self.assertLess(sum(p.stat().st_size for p in agents), 32000)


class PreloadTests(unittest.TestCase):
    def agent_front(self, name):
        text = (PLUGIN / 'agents' / f'{name}.md').read_text()
        return dict(l.split(': ', 1) for l in text.split('---')[1].strip().split('\n'))

    def test_agents_list_exactly_the_expected_skills_and_they_resolve(self):
        by_id = {r['id']: r for r in roles()}
        for path in sorted((PLUGIN / 'agents').glob('*.md')):
            role = by_id[path.stem if path.stem in by_id else next(i for i in by_id if path.stem.startswith(i + '-'))]
            expected = ['orchestra'] if role['id'] == 'orchestrator' else ['orchestra-worker', role['skill']]
            listed = [n.strip() for n in self.agent_front(path.stem)['skills'].strip('[]').split(',')]
            self.assertEqual(listed, expected, path.name)
            for name in listed:
                self.assertTrue((SKILLS / name / 'SKILL.md').is_file(), name)
                self.assertEqual(frontmatter(f'{name}/SKILL.md').get('name'), name)
                self.assertNotEqual(frontmatter(f'{name}/SKILL.md').get('disable-model-invocation', '').lower(), 'true')

    def test_every_declared_worker_mode_has_its_file(self):
        for role in roles():
            if role['id'] == 'orchestrator':
                continue
            for mode in role['modes']:
                self.assertTrue((SKILLS / role['skill'] / 'references' / f'{mode}.md').is_file(), (role['id'], mode))

    def test_role_skills_direct_the_worker_to_its_mode_file(self):
        for role in roles():
            if role['id'] == 'orchestrator':
                continue
            text = read(f"{role['skill']}/SKILL.md")
            self.assertIn('references/<Mode>.md', text)
            self.assertIn('`Mode:` line', text)
            self.assertIn('STATUS: BLOCKED', text)


class PhraseTests(unittest.TestCase):
    def test_per_directory_phrase_files(self):
        for d in TABLE:
            data = json.loads((PHRASES / f'{d}.json').read_text())
            self.assertIn(f'Sentinel: {d}/SKILL.md', data['phrases'], d)
            haystack = '\n'.join(read(f'{d}/{f}') for f in TABLE[d]).lower()
            for phrase in data['phrases']:
                self.assertIn(phrase.lower(), haystack, (d, phrase))

    def test_worker_contract_phrases_do_not_repeat_in_role_skills(self):
        sentences = [s.strip() for s in re.split(r'(?<=[.:])\s+|\n', read('orchestra-worker/SKILL.md').split(
            'Stub:')[1].split('\n', 1)[1]) if len(s.split()) >= 6]
        self.assertTrue(sentences)
        for d in TABLE:
            if d in ('orchestra', 'orchestra-worker'):
                continue
            text = ' '.join(read(f'{d}/{f}') for f in TABLE[d]).lower()
            for sentence in sentences:
                self.assertNotIn(sentence.lower(), text, (d, sentence))


if __name__ == '__main__':
    unittest.main()
