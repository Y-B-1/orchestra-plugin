"""Run locations and the project policy file."""
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'plugins/orchestra/scripts'))

from orchestra_core.paths import load_policy


class LoadPolicyTests(unittest.TestCase):
    def test_a_malformed_policy_names_the_file_and_the_json_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'policy.json'
            path.write_text('{"schema_version": 1,}')
            with self.assertRaises(ValueError) as caught:
                load_policy(tmp)
            self.assertRegex(str(caught.exception), '^Invalid project policy %s: .+: line 1 column [0-9]+' % re.escape(str(path)))


if __name__ == '__main__':
    unittest.main()
