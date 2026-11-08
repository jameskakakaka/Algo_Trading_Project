"""Real-file WAL tests; deliberately avoid the unsafe SSTable publication path."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from storage_engine.lsm_core import LSMTreeEngine, WriteAheadLog


class WALRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'wal.log'

    def engine(self):
        engine = LSMTreeEngine(self.directory.name)
        self.addCleanup(engine.wal.close)
        return engine

    def test_abrupt_process_exit_recovers_acknowledged_writes(self):
        code = '''
import os, sys
from storage_engine.lsm_core import LSMTreeEngine
engine = LSMTreeEngine(sys.argv[1])
engine.put(1700000000000, {"close": 42.5, "nested": [True, None, "雪"]})
engine.put(1700000060000, {"close": 43})
os._exit(0)
'''
        result = subprocess.run(
            [sys.executable, '-B', '-c', code, self.directory.name],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        recovered = self.engine()
        self.assertEqual(recovered.get(1700000000000),
                         {'close': 42.5, 'nested': [True, None, '雪']})
        self.assertEqual(recovered.get(1700000060000), {'close': 43})

    def test_replay_preserves_types_order_and_last_write_wins(self):
        engine = self.engine()
        records = [(2, {'v': 'first'}), ('2', ['string key']),
                   ('a::b\n雪', {'v': None}), (2, {'v': 'last'})]
        for key, value in records:
            engine.put(key, value)
        engine.wal.close()
        recovered = self.engine()
        self.assertEqual(recovered.wal.replay(), records)
        self.assertEqual(list(recovered.memtable.table), [2, '2', 'a::b\n雪'])
        self.assertEqual(recovered.memtable.table[2], {'v': 'last'})
        self.assertEqual(recovered.memtable.table['2'], ['string key'])

    def test_restarts_do_not_relog_or_trigger_flush(self):
        wal = WriteAheadLog(str(self.path))
        for key in range(6):
            wal.append(key, {'v': key})
        wal.close()
        original = self.path.read_bytes()
        for _ in range(3):
            engine = self.engine()
            self.assertEqual(engine.memtable.current_size, 6)
            engine.wal.close()
            self.assertEqual(self.path.read_bytes(), original)
            self.assertEqual(list(Path(self.directory.name).glob('sstable*')), [])

    def test_legacy_records_recover_in_file_order(self):
        self.path.write_bytes(b'12::{"v":"old::value"}\nname::[1,true,null]\n12::{"v":"new"}\n')
        engine = self.engine()
        self.assertEqual(engine.memtable.table, {12: {'v': 'new'}, 'name': [1, True, None]})

    def test_unterminated_tail_is_removed_before_next_append(self):
        for tail in (b'["wal-v1",2,', b'["wal-v1",2,"complete JSON"]', b'\xff'):
            with self.subTest(tail=tail):
                prefix = b'1::{"v":1}\n'
                self.path.write_bytes(prefix + tail)
                engine = self.engine()
                self.assertEqual(engine.memtable.table, {1: {'v': 1}})
                self.assertEqual(self.path.read_bytes(), prefix)
                engine.put(3, {'v': 3})
                engine.wal.close()
                reopened = self.engine()
                self.assertEqual(reopened.memtable.table, {1: {'v': 1}, 3: {'v': 3}})
                reopened.wal.close()

    def test_terminated_corruption_is_never_a_torn_tail(self):
        for suffix in (b'2::{"v":2}\n', b'', b'unterminated'):
            with self.subTest(suffix=suffix):
                contents = b'1::{"v":1}\nbad record\n' + suffix
                self.path.write_bytes(contents)
                with self.assertRaisesRegex(ValueError, 'Corrupt WAL record at line 2'):
                    self.engine()
                self.assertEqual(self.path.read_bytes(), contents)

    def test_sync_failure_does_not_acknowledge_or_update_memory(self):
        engine = self.engine()
        with patch('storage_engine.lsm_core.os.fsync', side_effect=OSError('sync failed')):
            with self.assertRaisesRegex(OSError, 'sync failed'):
                engine.put(1, {'v': 1})
        self.assertEqual(engine.memtable.table, {})
        with self.assertRaisesRegex(RuntimeError, 'close and reopen'):
            engine.put(2, {'v': 2})

    def test_directory_sync_failure_does_not_acknowledge(self):
        engine = self.engine()
        with patch('storage_engine.lsm_core.os.fsync',
                   side_effect=[None, OSError('directory sync failed')]):
            with self.assertRaisesRegex(OSError, 'directory sync failed'):
                engine.put(1, {'v': 1})
        self.assertEqual(engine.memtable.table, {})

    def test_append_synchronizes_file_and_directory(self):
        engine = self.engine()
        with patch('storage_engine.lsm_core.os.fsync', wraps=os.fsync) as sync:
            engine.put(1, {'v': 1})
        self.assertEqual(sync.call_count, 2)

    def test_failed_tail_repair_sync_aborts_initialization(self):
        self.path.write_bytes(b'1::1\nincomplete')
        with patch('storage_engine.lsm_core.os.fsync', side_effect=OSError('repair sync failed')):
            with self.assertRaisesRegex(OSError, 'repair sync failed'):
                self.engine()


if __name__ == '__main__':
    unittest.main()
