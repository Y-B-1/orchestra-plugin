import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
SKILLS = PLUGIN / 'skills'
PHRASES = Path(__file__).resolve().parent / 'skill_phrases'
SOURCES = ROOT / 'docs/SKILL-SOURCES.md'
NOTICES = PLUGIN / 'THIRD-PARTY-NOTICES'
HEADER_TAIL = '; see THIRD-PARTY-NOTICES.'
IDEA = re.compile(r'(.+?) \(idea level\)(?:, |$)')
REPO_SEGMENT = re.compile(r'^(?:derived from )?([\w.-]+/[\w.-]+)@([0-9a-f]{12}) (\S+(?: \S+)*) \(MIT\)$')

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


def source_header(rel):
    lines = [l for l in read(rel).split('\n') if l.startswith('Source:')]
    return lines[0] if lines else None


def parse_header(line):
    """SPEC 8.2 grammar: returns ([(repo, sha12)], [idea names]); raises ValueError."""
    if not line.startswith('Source: ') or not line.endswith(HEADER_TAIL):
        raise ValueError(line)
    repos, ideas = [], []
    for i, seg in enumerate(line[len('Source: '):-len(HEADER_TAIL)].split('; ')):
        if seg.startswith('ideas: '):
            names = IDEA.findall(seg[len('ideas: '):])
            if not names or ', '.join(f'{n} (idea level)' for n in names) != seg[len('ideas: '):]:
                raise ValueError(line)
            ideas += names
            continue
        m = REPO_SEGMENT.match(seg)
        if not m or seg.startswith('derived from ') != (not repos and i == 0):
            raise ValueError(line)
        repos.append((m.group(1), m.group(2)))
    if not repos and not ideas:
        raise ValueError(line)
    return repos, ideas


def sourced_files():
    """Destinations of matrix rows whose License cell names an upstream or idea-level source (SPEC 8.4)."""
    found = set()
    for line in SOURCES.read_text().split('\n'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if not line.startswith('|') or len(cells) != 12:
            continue
        if cells[-1].startswith('MIT:') or 'ideas:' in cells[-1]:
            found.update(re.findall(r'`([a-z-]+/(?:SKILL|references/[a-z-]+)\.md)`', cells[-2]))
    return found - {CLI}


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
            if rel in sourced_files() and not (source_header(rel) or any(l.startswith('Stub:') for l in lines)):
                self.fail(f'{rel} carries neither a Source header nor a Stub line')
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
        body = read('orchestra-worker/SKILL.md').split('Sentinel:')[1].split('\n', 1)[1]
        body = '\n'.join(l for l in body.split('\n') if not l.startswith('Stub:'))
        sentences = [s.strip() for s in re.split(r'(?<=[.:])\s+|\n', body) if len(s.split()) >= 6]
        self.assertTrue(sentences)
        for d in TABLE:
            if d in ('orchestra', 'orchestra-worker'):
                continue
            text = ' '.join(read(f'{d}/{f}') for f in TABLE[d]).lower()
            for sentence in sentences:
                self.assertNotIn(sentence.lower(), text, (d, sentence))


class ProvenanceTests(unittest.TestCase):
    def notices(self):
        return NOTICES.read_text()

    def test_matrix_sources_are_credited_in_notices(self):
        notices, matrix = self.notices(), SOURCES.read_text()
        shas = set(re.findall(r'^\| [^|]+ \| [\w.-]+/[\w.-]+ \| ([0-9a-f]{40}) ', matrix, re.M))
        self.assertEqual(len(shas), 5, shas)
        for sha in shas:
            self.assertIn(sha, notices)
        ideas = set(re.findall(r'ideas: ([^`|;]+? \(idea level\))', matrix))
        self.assertEqual(len(ideas), 3, ideas)
        for name in ideas:
            self.assertIn(name, notices)
        for repo in re.findall(r'\| (?:[\w.-]+/[\w.-]+) \|', matrix):
            self.assertIn(repo.strip('| '), notices)

    def test_every_mit_source_carries_its_license_text(self):
        notices = self.notices()
        self.assertEqual(notices.count('Permission is hereby granted, free of charge'), 5)
        self.assertEqual(notices.count('THE SOFTWARE IS PROVIDED "AS IS"'), 5)
        for holder in ['Jesse Vincent', 'Matt Pocock', 'Garry Tan', 'GitHub, Inc.', 'BMad Code, LLC']:
            self.assertIn(holder, notices)
        self.assertIn('TRADEMARK NOTICE', notices)

    def test_idea_level_sources_carry_no_license_text(self):
        notices = self.notices()
        for name in ['Claude Code security-review', 'Claude Code simplify', 'mattpocock/skills pr']:
            tail = notices.split(f'{name} (idea level)')[-1].split('\n\n')[0]
            self.assertNotIn('Permission is hereby granted', tail)

    def test_grammar_accepts_and_rejects(self):
        ok = ('Source: derived from obra/superpowers@8ca22dba9a94 skills/a/SKILL.md x.md (MIT); '
              'github/spec-kit@ae5ade7234be t.md (MIT); ideas: A b (idea level), C (idea level); '
              'see THIRD-PARTY-NOTICES.')
        self.assertEqual(parse_header(ok), (
            [('obra/superpowers', '8ca22dba9a94'), ('github/spec-kit', 'ae5ade7234be')], ['A b', 'C']))
        self.assertEqual(parse_header('Source: ideas: A (idea level); see THIRD-PARTY-NOTICES.'), ([], ['A']))
        for bad in ['Source: derived from obra/superpowers@8ca22dba9a94 a.md (MIT)',
                    'Source: derived from obra/superpowers@8ca22dba9a9 a.md (MIT); see THIRD-PARTY-NOTICES.',
                    'Source: obra/superpowers@8ca22dba9a94 a.md (MIT); see THIRD-PARTY-NOTICES.',
                    'Source: derived from obra/superpowers@8ca22dba9a94 a.md (Apache); see THIRD-PARTY-NOTICES.',
                    'Source: ideas: A; see THIRD-PARTY-NOTICES.',
                    'Source: see THIRD-PARTY-NOTICES.']:
            with self.assertRaises(ValueError, msg=bad):
                parse_header(bad)

    def test_headers_parse_and_are_credited(self):
        notices = self.notices()
        for rel in files():
            line = source_header(rel)
            if rel == CLI:
                self.assertIsNone(line)
                continue
            if rel not in sourced_files():
                self.assertIsNone(line, f'{rel} is Orchestra text only and takes no Source header')
            if line is None:
                continue
            repos, ideas = parse_header(line)
            for repo, sha12 in repos:
                self.assertRegex(notices, rf'{re.escape(repo)}\b[^\n]*\n?[^\n]*{sha12}[0-9a-f]{{28}}', (rel, repo))
            for name in ideas:
                self.assertIn(f'{name} (idea level)', notices, (rel, name))

    def test_destination_set_is_known_and_excludes_cli(self):
        found = sourced_files()
        self.assertTrue(found)
        self.assertNotIn(CLI, found)
        self.assertLessEqual(found, set(files()))


if __name__ == '__main__':
    unittest.main()
