import hashlib
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
        'checkpoint', 'final', 'correctness', 'architecture', 'security', 'cleanliness', 'specialists', 'standards']],
    'orchestra-operate': ['SKILL.md', 'references/gate.md', 'references/cleanup.md', 'references/release.md'],
}
CLI = 'orchestra/references/cli.md'
# O18: the no-Mode BLOCKED rule is a named exception to O15; worker and every role skill carry it verbatim.
MODE_RULE = 'If the brief has no `Mode:` line, stop and report `STATUS: BLOCKED`.'
ROLE_SKILLS = [d for d in TABLE if d not in ('orchestra', 'orchestra-worker')]
DELETION_TEST = ('Apply the deletion test. If deleting a module only moves its complexity to the callers, '
                 'it earns its place. If the complexity vanishes, it was a pass-through.')
MATERIALITY = ('A finding blocks only when it has a real, material impact on the requirements, tests or frameworks '
               'the prompt names: a named requirement unmet, a named test failing or certain to fail, a binding '
               'framework or charter rule broken, or a security or data-loss defect. An issue with no such impact, '
               'or one affecting under about 20% of a piece of work that is otherwise correct while every named '
               'requirement and test still holds, is a note. Notes go to the run brief and never trigger repair '
               'or hold.')
EXTRACT = ('Extract shared code only with two verified callers. Reuse an existing helper first. '
           'Count the net lines saved. Reject an abstraction that serves a single use.')
TAGS = ['code that nothing calls; search for real usage before you claim it',
        'hand-written code that the standard library already provides',
        'a dependency or helper that duplicates a platform feature',
        'an abstraction, option or hook with one use or none',
        'a smaller equivalent that saves five lines or more']
LIVENESS = ("Check liveness: a live process, and the transcript's last modification time. "
            'A journal line records what started, not what still runs.')
# O15: a rule two actors both execute appears once in each actor's skills, worded identically.
IDENTICAL_COPIES = [
    ('orchestra/references/briefs.md', 'orchestra-design/references/plan.md',
     'A link alone does not carry a rule into an empty context.'),
    ('orchestra/references/worktrees.md', 'orchestra-operate/references/cleanup.md',
     'A dirty or untracked worktree is not disposable. Show the file list and the three ways out: commit to a '
     'named branch, move the files out, or delete them as unrecoverable. The coordinator or user picks.'),
    ('orchestra/references/handoff.md', 'orchestra-operate/references/cleanup.md', LIVENESS),
    ('orchestra-design/references/design.md', 'orchestra-review/references/architecture.md', DELETION_TEST),
    ('orchestra-design/references/design.md', 'orchestra-build/references/cleanup.md', DELETION_TEST),
    ('orchestra-design/references/design.md', 'orchestra-review/references/architecture.md',
     'One adapter is a hypothetical seam; two adapters, usually production and test, make a real one.'),
    ('orchestra-design/references/design.md', 'orchestra-review/references/architecture.md', EXTRACT),
    ('orchestra-design/references/design.md', 'orchestra-build/references/cleanup.md', EXTRACT),
    ('orchestra-design/references/plan.md', 'orchestra-critique/references/feasibility.md',
     'A plan several times longer than its spec has written the code instead.'),
    ('orchestra-design/references/plan.md', 'orchestra-critique/references/feasibility.md',
     'A line that decides nothing, such as "handle edge cases", is a gap.'),
    ('orchestra-build/references/sensitive.md', 'orchestra-review/references/security.md',
     'A leaked secret needs rotation, and rewriting history does not replace it.'),
    ('orchestra-review/SKILL.md', 'orchestra-critique/SKILL.md', MATERIALITY),
] + [('orchestra-review/references/cleanliness.md', 'orchestra-build/references/cleanup.md', t) for t in TAGS]


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


LICENSE_SHA256 = {  # sha256 of the stripped upstream LICENSE at each pinned commit
    'obra/superpowers': 'bcbb871b4f72630bb35e1a28b11c083faabecd0751ded874762a75978caa318b',
    'mattpocock/skills': 'b50c2b2b687a9e47af56bb60908332828bb99aa7443ad5e007edcb311e23aba6',
    'garrytan/gstack': '0d18a6a75ad842e427f78e7f00739499330ee37c065363bcf44a7f07325e2ba6',
    'github/spec-kit': 'e32449d23085399adc1222f7a17408b730550258e51627c153cb108ca9955823',
    'bmad-code-org/BMAD-METHOD': '5034ff7cfe62bcef92188117a3b0e2c2fa4b8bea29a6f972368a9edc4893e557',
}
RULE = '=' * 64 + '\n'


def license_blocks(notices):
    """{repo: license text from 'MIT License' to the end of its section}, stripped."""
    blocks = {}
    for section in notices.split(RULE):
        m = re.match(r'([\w.-]+/[\w.-]+)\nRepository: ', section)
        if m and '\nMIT License' in section:
            blocks[m.group(1)] = section[section.index('\nMIT License'):].strip()
    return blocks


def source_header(rel):
    try:
        return header_in(read(rel))
    except ValueError as e:
        raise ValueError(f'{rel}: {e}')


def header_in(text):
    """The Source line, which must be the very first line after any frontmatter, with no blank line before it."""
    body = text.split('\n---\n', 1)[1] if text.startswith('---\n') else text
    lines = body.split('\n')
    found = [l for l in lines if l.startswith('Source:')]
    if not found:
        return None
    first = lines[0]
    if found[0] != first or len(found) > 1:
        raise ValueError(f'Source header must be the first line after frontmatter, once: {found}')
    return first


def parse_header(line):
    """SPEC 8.2 grammar: returns ([(repo, sha12)], [idea names]); raises ValueError."""
    if not line.startswith('Source: ') or not line.endswith(HEADER_TAIL):
        raise ValueError(line)
    repos, ideas = [], []
    segments = line[len('Source: '):-len(HEADER_TAIL)].split('; ')
    for i, seg in enumerate(segments):
        if seg.startswith('ideas: '):
            if ideas or i != len(segments) - 1:
                raise ValueError(line)
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
            # K2 (budget rule): review SKILL.md holds the materiality paragraph, so its cap is 4480 (was 4096).
            self.assertLessEqual(len(read(f'{d}/SKILL.md').encode()), 4480 if d == 'orchestra-review' else 4096, d)
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
        sentences = [x for x in sentences if x not in MODE_RULE]
        self.assertTrue(sentences)
        for d in TABLE:
            if d in ('orchestra', 'orchestra-worker'):
                continue
            text = ' '.join(read(f'{d}/{f}') for f in TABLE[d]).lower()
            for sentence in sentences:
                self.assertNotIn(sentence.lower(), text, (d, sentence))


class CohesionTests(unittest.TestCase):
    def test_mode_rule_is_byte_identical_in_worker_and_every_role_skill(self):
        for d in ['orchestra-worker'] + ROLE_SKILLS:
            self.assertEqual(read(f'{d}/SKILL.md').count(MODE_RULE), 1, d)

    def test_worker_does_not_cap_fix_rounds(self):
        # 2.2 ladder: repair and hold belong to the coordinator (no round cap); the worker stops on its own blockers only.
        worker = read('orchestra-worker/SKILL.md').lower()
        self.assertNotIn('failed fixes', worker)
        self.assertIn('blocker in your own assignment', worker)

    def test_shared_rules_are_identical_in_both_actors_files(self):
        for a, b, sentence in IDENTICAL_COPIES:
            for rel in (a, b):
                self.assertIn(sentence, read(rel), (rel, sentence))

    def test_coordinator_rules_have_one_owner(self):
        owners = [('dirty bytes', 'SKILL.md'), ('explicit user request', 'SKILL.md'),
                  ('reserve every card', 'references/parallel.md'),
                  ('empty context', 'references/briefs.md'),
                  ('exact artifact', 'references/repair-rounds.md')]
        coordinator = [f for f in TABLE['orchestra'] if f != 'references/cli.md']
        for phrase, owner in owners:
            hits = [f for f in coordinator if phrase in read(f'orchestra/{f}').lower()]
            self.assertEqual(hits, [owner], phrase)

    def test_skill_and_coordination_share_no_four_word_phrase(self):
        def grams(rel):
            body = read(f'orchestra/{rel}').split('Sentinel:')[1].lower()
            w = re.findall(r"[a-z0-9`<>:/_.'-]+", body)
            return {tuple(w[i:i + 4]) for i in range(len(w) - 3)}
        self.assertEqual(grams('SKILL.md') & grams('references/coordination.md'), set())

    def test_specialist_contract_has_both_sides(self):
        final_review = read('orchestra/references/final-review.md')
        self.assertIn('`Lens: specialist:<name>`', final_review)
        self.assertIn('specialists.md', final_review)
        self.assertNotIn('The lens never gates', final_review)
        headings = re.findall(r'^## (\S+)\s*$', read('orchestra-review/references/specialists.md'), re.M)
        for name in ['frontend', 'visual']:
            self.assertIn(name, headings)
        self.assertIn('specialist:<name>', read('orchestra-review/references/final.md'))

    def test_autonomy_documents_the_spec_cli(self):
        text = read('orchestra/references/autonomy.md')
        for command in ['autonomy arm', 'autonomy disarm', 'autonomy status', 'park TASK --reason TEXT',
                        'unpark TASK']:
            self.assertIn(command, text)
        self.assertNotIn('--max-passes', text)

    def test_handoff_ledger_line_has_the_six_e2_fields(self):
        line = next(l for l in read('orchestra/references/handoff.md').split('\n') if 'artifact SHA' in l)
        for field in ['time', 'card', 'action', 'round', 'decision']:
            self.assertIn(field, line)

    def test_operator_gate_does_not_judge_requirements(self):
        self.assertNotIn('Requirements met', read('orchestra-operate/references/gate.md'))

    def test_final_lens_table_covers_every_category(self):
        rows = re.findall(r'^\| `(\w+)\.md` \| ([^|]+?) \|', read('orchestra-review/references/final.md'), re.M)
        self.assertEqual(sorted(r[0] for r in rows), ['correctness', 'security', 'standards'])
        seen = []
        for _, cats in rows:
            seen += [c.strip() for c in cats.split(',')]
        self.assertEqual(len(seen), len(set(seen)), seen)
        self.assertEqual(set(seen), {'requirements', 'correctness', 'tests', 'architecture', 'security',
                                     'standards', 'cleanup'})

    def test_a_lens_file_never_points_into_another_lens_file(self):
        lenses = ['correctness', 'architecture', 'security', 'cleanliness', 'standards']
        for lens in lenses:
            text = read(f'orchestra-review/references/{lens}.md')
            for other in lenses:
                if other != lens:
                    self.assertNotIn(f'{other}.md', text, (lens, other))


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
        blocks = license_blocks(notices)
        self.assertEqual(set(blocks), set(LICENSE_SHA256))
        for repo, text in blocks.items():
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), LICENSE_SHA256[repo], repo)

    def test_pstack_and_omc_are_credited_as_idea_level_only(self):
        notices = self.notices()
        for name in ['pstack', 'OMC']:
            self.assertIn(f'\n{name} (idea level)\n', notices)
            tail = notices.split(f'{name} (idea level)')[-1].split('\n\n')[0]
            self.assertNotIn('Permission is hereby granted', tail)

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
                    'Source: ideas: A (idea level); obra/superpowers@8ca22dba9a94 a.md (MIT); see THIRD-PARTY-NOTICES.',
                    'Source: ideas: A (idea level); ideas: B (idea level); see THIRD-PARTY-NOTICES.',
                    'Source: derived from obra/superpowers@8ca22dba9a94 a.md (MIT); ideas: A (idea level); '
                    'github/spec-kit@ae5ade7234be t.md (MIT); see THIRD-PARTY-NOTICES.',
                    'Source: see THIRD-PARTY-NOTICES.']:
            with self.assertRaises(ValueError, msg=bad):
                parse_header(bad)

    def test_header_must_lead_the_body_after_frontmatter(self):
        src = 'Source: ideas: A (idea level); see THIRD-PARTY-NOTICES.'
        self.assertEqual(header_in(f'{src}\n\nSentinel: x\n'), src)
        self.assertEqual(header_in(f'---\nname: n\n---\n{src}\nSentinel: x\n'), src)
        self.assertIsNone(header_in('Sentinel: x\nbody\n'))
        for bad in [f'Sentinel: x\n{src}\n', f'---\nname: n\n---\nSentinel: x\n{src}\n',
                    f'text\n{src}\nSentinel: x\n', f'{src}\n{src}\nSentinel: x\n']:
            with self.assertRaises(ValueError, msg=bad):
                header_in(bad)

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
