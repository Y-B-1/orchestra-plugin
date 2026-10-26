"""The generator refuses unknown tool names and an oversized agent catalog."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / 'plugins' / 'orchestra'
spec = importlib.util.spec_from_file_location('generate', PLUGIN / 'scripts' / 'generate.py')
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


class GenerateToolsTests(unittest.TestCase):
    def copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(PLUGIN / 'config', root / 'config')
        shutil.copytree(PLUGIN / 'skills', root / 'skills')
        return root

    def edit_builder(self, root, change):
        path = root / 'config' / 'roles.json'
        data = json.loads(path.read_text())
        role = next(r for r in data['roles'] if r['id'] == 'builder')
        change(role)
        path.write_text(json.dumps(data))

    def test_misspelled_tool_names_the_agent(self):
        root = self.copy()
        self.edit_builder(root, lambda r: r.update(tools=r['tools'] + ['Raed']))
        with self.assertRaises(ValueError) as caught:
            generate.generated(root)
        self.assertIn('builder', str(caught.exception))
        self.assertIn('Raed', str(caught.exception))

    def test_mcp_tool_and_scoped_bash_pass(self):
        root = self.copy()
        self.edit_builder(root, lambda r: r.update(tools=r['tools'] + ['mcp__x__y', 'Bash(git status:*)']))
        self.assertIn('agents/builder.md', generate.generated(root))

    def test_oversized_catalog_is_refused(self):
        root = self.copy()
        self.edit_builder(root, lambda r: r.update(description=r['description'] + 'x' * 60000))
        with self.assertRaises(ValueError) as caught:
            generate.generated(root)
        self.assertIn('builder', str(caught.exception))

    def test_real_config_generates(self):
        self.assertTrue(generate.generated())


if __name__ == '__main__':
    unittest.main()
