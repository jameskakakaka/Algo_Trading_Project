"""Real-file fault injection; process exits do not simulate power loss."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from storage_engine.lsm_core import LSMTreeEngine


class SSTablePublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def engine(self):
        engine = LSMTreeEngine(self.directory.name)
        self.addCleanup(engine.wal.close)
        return engine

    def tables(self):
        return sorted(self.root.glob('sstable_*.json'))

    def seed(self, engine):
        # Explicit flush permits fault injection after all puts acknowledged.
        for key in range(4):
            engine.put(key, f'value-{key}')

    def assert_seed(self, engine):
        for key in range(4):
            self.assertEqual(engine.get(key), f'value-{key}')

    def recover(self, engine):
        engine.wal.close()
        recovered = self.engine()
        self.assert_seed(recovered)
        return recovered

    def test_successful_threshold_flush_retires_wal(self):
        engine = self.engine()
        for key in range(5):
            engine.put(key, key)
        self.assertEqual((self.root / 'wal.log').read_bytes(), b'')
        self.assertEqual(engine.memtable.current_size, 0)
        self.assertEqual(len(self.tables()), 1)
        engine.wal.close()
        recovered = self.engine()
        for key in range(5):
            self.assertEqual(recovered.get(key), key)

    def test_publication_and_retirement_operation_order(self):
        engine = self.engine()
        self.seed(engine)
        events = []
        real_sync, real_link, real_replace = os.fsync, os.link, os.replace

        def sync(descriptor):
            events.append('fsync')
            return real_sync(descriptor)

        def publish(source, destination):
            events.append('publish')
            return real_link(source, destination)

        def retire(source, destination):
            events.append('retire')
            return real_replace(source, destination)

        with patch('storage_engine.lsm_core.os.fsync', side_effect=sync), patch(
                'storage_engine.lsm_core.os.link', side_effect=publish), patch(
                'storage_engine.lsm_core.os.replace', side_effect=retire):
            engine.flush_to_sstable()
        self.assertEqual(events, ['fsync', 'publish', 'fsync', 'fsync',
                                  'retire', 'fsync'])

    def test_frozen_clock_multiple_flushes_and_manual_compaction(self):
        engine = self.engine()
        with patch('storage_engine.lsm_core.time.time', return_value=1), patch.object(
                engine, 'compact', side_effect=AssertionError('automatic compaction')):
            for key in range(20):
                engine.put(key, key)
        self.assertEqual(len(self.tables()), 4)
        engine.wal.close()
        recovered = self.engine()
        recovered.compact()
        self.assertEqual(len(self.tables()), 1)
        for key in range(20):
            self.assertEqual(recovered.get(key), key)

    def test_before_publication_failures_preserve_wal(self):
        for operation in ('json.dump', 'os.fsync', 'os.link'):
            with self.subTest(operation=operation):
                engine = self.engine()
                self.seed(engine)
                original = (self.root / 'wal.log').read_bytes()
                with patch('storage_engine.lsm_core.' + operation,
                           side_effect=OSError('injected')):
                    with self.assertRaisesRegex(OSError, 'injected'):
                        engine.flush_to_sstable()
                self.assertEqual((self.root / 'wal.log').read_bytes(), original)
                self.assertEqual(self.tables(), [])
                self.assert_seed(engine)
                with self.assertRaisesRegex(RuntimeError, 'reopen'):
                    engine.put('blocked', 1)
                with self.assertRaisesRegex(RuntimeError, 'reopen'):
                    engine.flush_to_sstable()
                self.recover(engine).wal.close()

    def test_publication_directory_sync_failure_does_not_retire_wal(self):
        engine = self.engine()
        self.seed(engine)
        original = (self.root / 'wal.log').read_bytes()
        with patch('storage_engine.lsm_core._sync_directory',
                   side_effect=OSError('directory sync')), patch.object(
                       engine.wal, 'clear') as retire:
            with self.assertRaisesRegex(OSError, 'directory sync'):
                engine.flush_to_sstable()
            retire.assert_not_called()
        self.assertEqual(len(self.tables()), 1)
        self.assertEqual((self.root / 'wal.log').read_bytes(), original)
        self.recover(engine)

    def test_after_durable_publication_before_retirement(self):
        engine = self.engine()
        self.seed(engine)
        with patch.object(engine.wal, 'clear', side_effect=OSError('before retirement')):
            with self.assertRaisesRegex(OSError, 'before retirement'):
                engine.flush_to_sstable()
        self.assertEqual(len(self.tables()), 1)
        recovered = self.recover(engine)
        # Duplicated WAL replay must not override subsequent updates forever.
        recovered.put(0, 'new')
        recovered.flush_to_sstable()
        recovered.wal.close()
        self.assertEqual(self.engine().get(0), 'new')

    def test_retirement_failure_before_and_after_atomic_replace(self):
        real_replace = os.replace
        for after in (False, True):
            with self.subTest(after=after):
                engine = self.engine()
                self.seed(engine)

                def fail_replace(source, destination):
                    if after:
                        real_replace(source, destination)
                    raise OSError('retirement replace')

                with patch('storage_engine.lsm_core.os.replace', side_effect=fail_replace):
                    with self.assertRaisesRegex(OSError, 'retirement replace'):
                        engine.flush_to_sstable()
                self.recover(engine).wal.close()

    def test_retirement_fsync_failures(self):
        real_sync = os.fsync
        # Flush fsync sequence: table, publication directory, empty WAL,
        # retirement directory. Fail either of the final two operations.
        for failed_call in (3, 4):
            with self.subTest(failed_call=failed_call):
                engine = self.engine()
                self.seed(engine)
                calls = 0

                def sync(descriptor):
                    nonlocal calls
                    calls += 1
                    if calls == failed_call:
                        raise OSError('retirement sync')
                    return real_sync(descriptor)

                with patch('storage_engine.lsm_core.os.fsync', side_effect=sync):
                    with self.assertRaisesRegex(OSError, 'retirement sync'):
                        engine.flush_to_sstable()
                self.recover(engine).wal.close()

    def test_incomplete_temporaries_are_ignored_and_preserved(self):
        for name in ('.sstable-orphan', '.wal-orphan'):
            (self.root / name).write_bytes(b'[[broken')
        engine = self.engine()
        self.seed(engine)
        engine.flush_to_sstable()
        self.recover(engine)
        for name in ('.sstable-orphan', '.wal-orphan'):
            self.assertEqual((self.root / name).read_bytes(), b'[[broken')

    def test_repeated_restart_generations_and_newest_wins(self):
        expected = {}
        for cycle in range(5):
            engine = self.engine()
            for key, value in [('K', cycle), (cycle, f'cycle-{cycle}'), ('2', cycle)]:
                engine.put(key, value)
                expected[key] = value
            engine.flush_to_sstable()
            engine.wal.close()
            recovered = self.engine()
            for key, value in expected.items():
                self.assertEqual(recovered.get(key), value)
            recovered.wal.close()
        self.assertEqual(len(self.tables()), 5)

    def test_typed_keys_and_null_across_generations(self):
        engine = self.engine()
        engine.put(2, 'old integer')
        engine.put('2', 'old string')
        engine.flush_to_sstable()
        engine.put(2, None)
        engine.put('2', 'new string')
        engine.put('text', None)
        engine.flush_to_sstable()
        engine.wal.close()
        recovered = self.engine()
        self.assertIsNone(recovered.get(2))
        self.assertEqual(recovered.get('2'), 'new string')
        self.assertIsNone(recovered.get('text'))
        self.assertIsNone(recovered.get('missing'))

    def test_publication_collision_does_not_overwrite(self):
        engine = self.engine()
        self.seed(engine)
        real_link = os.link
        original = b'[["existing", "preserved"]]'

        def collide(source, destination):
            Path(destination).write_bytes(original)
            return real_link(source, destination)

        with patch('storage_engine.lsm_core.os.link', side_effect=collide):
            with self.assertRaises(FileExistsError):
                engine.flush_to_sstable()
        self.assertEqual(self.tables()[0].read_bytes(), original)
        recovered = self.recover(engine)
        self.assertEqual(recovered.get('existing'), 'preserved')

    def test_legacy_numeric_order_and_new_tables_take_precedence(self):
        (self.root / 'sstable_9.json').write_text('[["K", "old"]]')
        (self.root / 'sstable_10.json').write_text('[["K", "legacy new"]]')
        engine = self.engine()
        self.assertEqual(engine.get('K'), 'legacy new')
        engine.put('K', 'new generation')
        engine.flush_to_sstable()
        engine.wal.close()
        self.assertEqual(self.engine().get('K'), 'new generation')
        self.assertEqual((self.root / 'sstable_9.json').read_text(), '[["K", "old"]]')

    def test_ambiguous_legacy_order_fails_without_modifying_files(self):
        for name in ('sstable_9.json', 'sstable_merged_10.json'):
            (self.root / name).write_text('[["K", "legacy"]]')
        before = {p.name: p.read_bytes() for p in self.tables()}
        with self.assertRaisesRegex(ValueError, 'Ambiguous legacy'):
            self.engine()
        self.assertEqual({p.name: p.read_bytes() for p in self.tables()}, before)

    def test_abrupt_exit_at_publication_and_retirement_boundaries(self):
        code = '''
import os, sys
from unittest.mock import patch
from storage_engine.lsm_core import LSMTreeEngine
engine = LSMTreeEngine(sys.argv[1])
for key in range(4):
    engine.put(key, 'value-' + str(key))
operation = sys.argv[2]
real = getattr(os, operation)
def crash(*args, **kwargs):
    real(*args, **kwargs)
    os._exit(73)
with patch('storage_engine.lsm_core.os.' + operation, side_effect=crash):
    engine.flush_to_sstable()
'''
        for operation in ('link', 'replace'):
            with self.subTest(operation=operation):
                result = subprocess.run([sys.executable, '-B', '-c', code,
                                         self.directory.name, operation],
                                        cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                recovered = self.engine()
                self.assert_seed(recovered)
                recovered.wal.close()


if __name__ == '__main__':
    unittest.main()
