import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/orchestra'
sys.path.insert(0, str(PLUGIN / 'scripts'))
from orchestra_core import profiles
import generate


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='Orchestra package with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Plugin with spaces'
        self.home = Path(self.temp.name) / 'config'
        (self.root / 'profiles/codex').mkdir(parents=True)
        self.source = self.root / 'profiles/codex/orchestra_builder.toml'
        self.source.write_text('name="orchestra_builder"\ndeveloper_instructions="Root __ORCHESTRA_ROOT__"\n')

    def test_install_upgrade_uninstall_preserves_unowned_files(self):
        (self.home / 'agents').mkdir(parents=True)
        untouched = self.home / 'agents/personal.toml'
        untouched.write_text('name="personal"')
        profiles.install(self.root, self.home)
        target = self.home / 'agents/orchestra_builder.toml'
        self.assertIn(str(self.root), tomllib.loads(target.read_text())['developer_instructions'])
        self.source.write_text('name="orchestra_builder"\ndeveloper_instructions="New __ORCHESTRA_ROOT__"\n')
        profiles.install(self.root, self.home)
        self.assertIn('New', target.read_text())
        profiles.uninstall(self.home)
        self.assertFalse(target.exists())
        self.assertEqual(untouched.read_text(), 'name="personal"')

    def test_collision_and_changed_receipt_block_before_any_write(self):
        profiles.install(self.root, self.home)
        target = self.home / 'agents/orchestra_builder.toml'
        target.write_text('my edits')
        for operation in [lambda: profiles.install(self.root, self.home), lambda: profiles.uninstall(self.home)]:
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(target.read_text(), 'my edits')

    def test_unowned_target_is_never_overwritten(self):
        (self.home / 'agents').mkdir(parents=True)
        target = self.home / 'agents/orchestra_builder.toml'
        target.write_text('unowned')
        with self.assertRaises(ValueError):
            profiles.install(self.root, self.home)
        self.assertEqual(target.read_text(), 'unowned')

    def test_symlink_and_receipt_traversal_are_rejected(self):
        profiles.install(self.root, self.home)
        target = self.home / 'agents/orchestra_builder.toml'
        original = target.read_bytes()
        target.unlink()
        other = self.home / 'unrelated'
        other.write_bytes(original)
        target.symlink_to(other)
        with self.assertRaises(ValueError):
            profiles.uninstall(self.home)
        target.unlink()
        receipt = self.home / 'orchestra/profiles-receipt.json'
        receipt.write_text(json.dumps({'schema_version':1,'files':{'../unrelated':'a'*64}}))
        with self.assertRaises(ValueError):
            profiles.uninstall(self.home)
        self.assertEqual(other.read_bytes(), original)

    def test_symlinked_install_locations_reject_before_writes(self):
        for relative in ['', 'agents', 'orchestra', 'orchestra/profiles-receipt.json', 'orchestra/profiles.lock']:
            for operation in [profiles.install, profiles.uninstall]:
                with self.subTest(relative=relative, operation=operation.__name__), tempfile.TemporaryDirectory() as directory:
                    home = Path(directory) / 'home'
                    other = Path(directory) / 'unrelated'
                    other.mkdir()
                    link = home / relative if relative else home
                    link.parent.mkdir(parents=True, exist_ok=True)
                    destination = other
                    if relative.endswith(('.json', '.lock')):
                        destination = other / 'file'
                        destination.write_text('{"schema_version":1,"files":{}}')
                    link.symlink_to(destination)
                    before = sorted((str(p.relative_to(other)), p.read_bytes() if p.is_file() else None) for p in other.rglob('*'))
                    with self.assertRaises(ValueError):
                        operation(self.root, home) if operation is profiles.install else operation(home)
                    after = sorted((str(p.relative_to(other)), p.read_bytes() if p.is_file() else None) for p in other.rglob('*'))
                    self.assertEqual(before, after)


class NativeTests(unittest.TestCase):
    def test_generated_assets_match_and_profiles_pin_settings(self):
        for name, content in generate.generated().items():
            self.assertEqual((PLUGIN / name).read_text(), content, name)
            if name.endswith('.toml'):
                data = tomllib.loads(content)
                self.assertIn(data['model'], ['gpt-6-astra','gpt-6.1-sol'])
                self.assertIn(data['model_reasoning_effort'], ['low','medium','high'])
                self.assertFalse(data['agents']['enabled'])

    def test_separate_hook_definitions_and_contained_catalogs(self):
        root = json.loads((PLUGIN / 'plugin.json').read_text())
        claude = json.loads((PLUGIN / '.claude-plugin/plugin.json').read_text())
        self.assertNotEqual(root['extensions']['com.openai']['hooks'], claude['hooks'])
        self.assertFalse((PLUGIN / 'hooks/hooks.json').exists())
        for path in [ROOT/'.agents/plugins/marketplace.json', ROOT/'.claude-plugin/marketplace.json']:
            source = json.loads(path.read_text())['plugins'][0]['source']
            relative = source['path'] if isinstance(source, dict) else source
            self.assertEqual((ROOT/relative).resolve(), PLUGIN.resolve())


if __name__ == '__main__':
    unittest.main()
