import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bench'))
import bench


class QueueFileLowDiskTests(unittest.TestCase):
    def test_queue_file_stops_with_a_message_when_disk_is_low(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        runs = Path(tmp.name) / 'runs'
        runs.mkdir()
        queue = Path(tmp.name) / 'queue.txt'
        queue.write_text('plain:t1:1\n')
        rounds = []

        def fixture():
            rounds.append(1)
            if len(rounds) > 3:
                raise AssertionError('queue_file keeps starting the same item')

        out = io.StringIO()
        with mock.patch.object(bench, 'RUNS', runs), mock.patch.object(bench, 'free_gb', lambda: 1.0), \
                mock.patch.object(bench, 'ensure_fixture', fixture), mock.patch.object(bench.time, 'sleep', lambda s: None), \
                contextlib.redirect_stdout(out):
            bench.queue_file(queue)

        self.assertIn('only 1.0 GB free; stopping', out.getvalue())
        self.assertEqual(rounds, [], 'no item may start while the disk is low')
        self.assertFalse((runs / 'plain-t1-1' / 'skip').exists(), 'low disk must not mark an item skipped')


if __name__ == '__main__':
    unittest.main()
