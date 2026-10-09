import os
import sys
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_release


def git(repo, *args):
    subprocess.run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args],
                   cwd=repo, check=True, capture_output=True)


class BuildSymlinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.out = Path(self.tmp.name) / 'out'
        (self.repo / 'plugins/orchestra').mkdir(parents=True)
        (self.repo / 'plugins/orchestra/plugin.json').write_text('{"version":"9.9.9"}')
        (self.repo / 'docs').mkdir()
        (self.repo / 'docs/real.txt').write_text('hello\n')
        git(self.repo, 'init', '-q')

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


if __name__ == '__main__':
    unittest.main()
