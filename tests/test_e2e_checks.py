"""Tests for `lean.py e2e-doctor` (scripts/e2e_checks.py): one ok or gap line per check of the e2e setup."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

from tests.support import LEAN, make_repo

KEYS = ('TYPESAFE_AI_API_KEY', 'AI_GATEWAY_API_KEY', 'OPENROUTER_API_KEY')


class E2eDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = str(Path(self.tmp.name).resolve() / 'repo')
        make_repo(self.cwd)

    def doctor(self, *args, env=None):
        base = {k: v for k, v in os.environ.items() if k not in KEYS}  # keys come from the test, not the machine
        r = subprocess.run([sys.executable, str(LEAN), 'e2e-doctor', *args], cwd=self.cwd, capture_output=True, text=True,
                           env={**base, **(env or {})})
        return r.returncode, r.stdout

    def set_up_e2e(self, config='export default { filters: [decisionFilter({ model: m(process.env.TYPESAFE_AI_API_KEY) })] }'):
        root = Path(self.cwd)
        (root / 'e2e.config.ts').write_text(config)
        (root / 'package.json').write_text(json.dumps({'devDependencies': {'e2e': '^0.23.1', '@e2e-dev/decision': '^0.3.3'}}))
        (root / '.env.e2e.local').write_text('TYPESAFE_AI_API_KEY=sekret-value\n')
        (root / '.agents' / 'skills' / 'e2e').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'e2e' / 'SKILL.md').write_text('skill')

    def test_e2e_doctor_passes_a_complete_setup_and_never_prints_a_key_value(self):
        self.set_up_e2e()
        code, out = self.doctor()
        self.assertEqual(code, 0, out)
        self.assertEqual([line.split()[0] for line in out.splitlines()], ['ok'] * 6, out)
        self.assertIn('TYPESAFE_AI_API_KEY', out)
        self.assertNotIn('sekret-value', out)

    def test_e2e_doctor_names_each_gap(self):
        self.set_up_e2e('export default { agent: process.env.OPENROUTER_API_KEY }')
        (Path(self.cwd) / 'package.json').write_text(json.dumps({'dependencies': {'e2e': '1'}}))
        (Path(self.cwd) / '.env.e2e.local').unlink()
        (Path(self.cwd) / '.agents' / 'skills' / 'e2e' / 'SKILL.md').unlink()
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        gaps = [line for line in out.splitlines() if line.startswith('gap')]
        self.assertEqual(len(gaps), 4, out)
        self.assertTrue(any('filters' in g for g in gaps) and any('@e2e-dev/decision' in g for g in gaps), out)
        self.assertTrue(any('OPENROUTER_API_KEY' in g for g in gaps) and any('SKILL.md' in g for g in gaps), out)
        code, out = self.doctor(env={'OPENROUTER_API_KEY': 'v4lue'})
        self.assertNotIn('OPENROUTER_API_KEY', ''.join(line for line in out.splitlines() if line.startswith('gap')))
        self.assertNotIn('v4lue', out)

    def test_e2e_doctor_without_a_config_gives_the_setup_command_and_rejects_bad_usage(self):
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count('gap'), 1, out)
        self.assertIn('npx e2e init --yes', out)
        self.assertIn('npm install --save-dev e2e @e2e-dev/web ai@^7', out)
        r = subprocess.run([sys.executable, str(LEAN), 'e2e-doctor', '--bogus'], cwd=self.cwd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('lean.py e2e-doctor [--config PATH]', r.stderr)
        self.assertEqual(self.doctor('--config')[0], 2)

    def test_e2e_doctor_expects_the_key_a_provider_reads_when_the_config_names_none(self):
        self.set_up_e2e('export default { filters: [decisionFilter({ model: typeSafeAi.decisionModel("jev-latest") })] }')
        (Path(self.cwd) / '.env.e2e.local').unlink()
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        self.assertIn('gap key TYPESAFE_AI_API_KEY', out)
        self.assertEqual(self.doctor(env={'TYPESAFE_AI_API_KEY': 'v'})[0], 0)

    def test_e2e_doctor_does_not_find_a_config_above_the_repository(self):
        (Path(self.cwd).parent / 'e2e.config.ts').write_text('export default {}')
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        self.assertIn('gap no e2e config found', out)

    def test_e2e_doctor_outside_a_repository_looks_only_in_its_own_folder(self):
        (Path(self.tmp.name) / 'e2e.config.ts').write_text('export default {}')
        plain = Path(self.tmp.name) / 'plain'
        plain.mkdir()
        self.cwd = str(plain)
        code, out = self.doctor()
        self.assertEqual(code, 1, out)
        self.assertIn('gap no e2e config found', out)


if __name__ == '__main__':
    unittest.main()
