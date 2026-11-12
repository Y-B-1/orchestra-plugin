import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_release
from tests.support import git, make_repo


class BuildSymlinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = make_repo(Path(self.tmp.name) / 'repo')
        self.out = Path(self.tmp.name) / 'out'
        (self.repo / 'plugins/orchestra').mkdir(parents=True)
        (self.repo / 'plugins/orchestra/plugin.json').write_text('{"version":"9.9.9"}')
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/real.txt').write_text('hello\n')

    def commit(self):
        git(self.repo, 'add', '--', 'plugins', 'docs', 'link')
        git(self.repo, 'commit', '-q', '-m', 'x')

    def test_in_repo_symlink_is_left_out_and_target_stays(self):
        (self.repo / 'link').symlink_to('docs/real.txt')
        self.commit()
        build_release.build(self.out, root=self.repo)
        with tarfile.open(self.out / 'orchestra-9.9.9.tar.gz') as tar:
            names = tar.getnames()
        with zipfile.ZipFile(self.out / 'orchestra-9.9.9.zip') as z:
            znames = z.namelist()
        for listing in (names, znames):
            self.assertIn('orchestra-9.9.9/docs/real.txt', listing)
            self.assertNotIn('orchestra-9.9.9/link', listing)

    def test_symlink_leaving_the_repo_is_rejected(self):
        outside = Path(self.tmp.name) / 'outside.txt'
        outside.write_text('x')
        (self.repo / 'link').symlink_to(outside)
        self.commit()
        with self.assertRaisesRegex(ValueError, 'Distribution symlinks are unsupported'):
            build_release.build(self.out, root=self.repo)

    def test_development_files_are_left_out(self):
        keep = ['plugins/orchestra/hooks/hooks.json', 'docs/real.txt']
        drop = ['tests/test_x.py', '.agents/skills/a.md', 'package.json', 'package-lock.json', 'e2e.config.ts', '.mcp.json',
                'bench/README.md', '.github/workflows/ci.yml', '.claude/skills/a.md', '.cursor/mcp.json']
        for name in keep + drop:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text('x\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'x')
        build_release.build(self.out, root=self.repo)
        with tarfile.open(self.out / 'orchestra-9.9.9.tar.gz') as tar:
            names = set(tar.getnames())
        for name in keep:
            self.assertIn('orchestra-9.9.9/' + name, names)
        for name in drop:
            self.assertNotIn('orchestra-9.9.9/' + name, names)

    def test_private_content_is_refused(self):
        samples = ['/' + 'home/someone/notes', '/' + 'Users/someone/notes', 'github_pat_' + 'A' * 22, 'xoxb-' + '1' * 12,
                   'AKIA' + 'A' * 16, 'ghp_' + 'a' * 24]
        for sample in samples:
            with self.subTest(sample=sample[:8]):
                (self.repo / 'docs/real.txt').write_text(sample + '\n')
                git(self.repo, 'add', '-A')
                git(self.repo, 'commit', '-q', '-m', 'x')
                with self.assertRaisesRegex(ValueError, 'Private content candidate'):
                    build_release.build(self.out, root=self.repo)


if __name__ == '__main__':
    unittest.main()
