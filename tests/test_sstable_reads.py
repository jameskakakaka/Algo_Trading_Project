"""Phase 2B.0 read correctness using real files, below compaction threshold."""
import json
from pathlib import Path
import tempfile
import unittest

from storage_engine.lsm_core import LSMTreeEngine


class SSTableReadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def engine(self):
        engine = LSMTreeEngine(self.directory.name)
        self.addCleanup(engine.wal.close)
        return engine

    def test_five_mixed_keys_flush_and_survive_restart(self):
        engine = self.engine()
        records = [('z', 'last'), (2, 'integer'), ('2', 'string'),
                   (-3, 'negative'), ('apple', 'nonnumeric')]
        for key, value in records:
            engine.put(key, value)
        self.assertEqual(engine.memtable.current_size, 0)
        files = list(Path(self.directory.name).glob('sstable_*.json'))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text()),
                         [[-3, 'negative'], [2, 'integer'], ['2', 'string'],
                          ['apple', 'nonnumeric'], ['z', 'last']])
        for key, value in records:
            self.assertEqual(engine.get(key), value)
        engine.wal.close()
        recovered = self.engine()
        for key, value in records:
            with self.subTest(key=key):
                self.assertEqual(recovered.get(key), value)
        self.assertIsNone(recovered.get('missing'))
        self.assertIsNone(recovered.get(99))

    def test_integer_and_string_keys_are_distinct_in_memory_and_on_disk(self):
        engine = self.engine()
        engine.put(2, 'integer')
        engine.put('2', 'string')
        for on_disk in (False, True):
            if on_disk:
                engine.flush_to_sstable()
            self.assertEqual(engine.get(2), 'integer')
            self.assertEqual(engine.get('2'), 'string')
            self.assertIsNone(engine.get('02'))
            self.assertIsNone(engine.get(2.0))

    def test_null_update_shadows_old_sstable_value_and_recovers(self):
        engine = self.engine()
        engine.put('K', 'old')
        engine.flush_to_sstable()
        self.assertEqual(engine.get('K'), 'old')
        engine.put('K', None)
        self.assertTrue(engine.memtable.contains('K'))
        self.assertIsNone(engine.get('K'))
        engine.wal.close()
        recovered = self.engine()
        self.assertTrue(recovered.memtable.contains('K'))
        self.assertIsNone(recovered.get('K'))

    def test_null_sstable_value_and_missing_keys(self):
        engine = self.engine()
        self.assertIsNone(engine.get('missing'))
        engine.put(1, None)
        engine.flush_to_sstable()
        engine.wal.close()
        recovered = self.engine()
        self.assertIsNone(recovered.get(1))
        self.assertIsNone(recovered.get(True))
        self.assertIsNone(recovered.get('missing'))
        self.assertIsNone(recovered.get(99))

    def test_integer_aliases_do_not_match_memtable(self):
        engine = self.engine()
        engine.put(1, 'integer')
        self.assertIsNone(engine.memtable.get(True))
        self.assertIsNone(engine.get(True))
        self.assertIsNone(engine.get(1.0))

    def test_existing_pair_format_is_read_without_rewriting(self):
        path = Path(self.directory.name) / 'sstable_123.json'
        original = b'[["name", "text"], ["2", "string"], [2, "integer"]]'
        path.write_bytes(original)
        engine = self.engine()
        self.assertEqual(engine.get('name'), 'text')
        self.assertEqual(engine.get('2'), 'string')
        self.assertEqual(engine.get(2), 'integer')
        self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
