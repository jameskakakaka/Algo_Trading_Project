"""Full compaction fault injection; process exits are not power-loss tests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from storage_engine.lsm_core import LSMTreeEngine


class SSTableCompactionTests(unittest.TestCase):
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
        for cycle in range(3):
            for key, value in [(2, cycle), ('2', 'string'), ('K', cycle),
                               (f'unique-{cycle}', [cycle, None])]:
                engine.put(key, value)
            engine.flush_to_sstable()
        engine.put(2, None)
        engine.flush_to_sstable()

    def assert_records(self, engine):
        self.assertIsNone(engine.get(2))
        self.assertEqual(engine.get('2'), 'string')
        self.assertEqual(engine.get('K'), 2)
        for cycle in range(3):
            self.assertEqual(engine.get(f'unique-{cycle}'), [cycle, None])

    def reopen(self, engine):
        engine.wal.close()
        return self.engine()

    def test_full_merge_typed_keys_null_and_repeated_restart(self):
        engine = self.engine()
        self.seed(engine)
        previous = 4
        for _ in range(4):
            engine.compact()
            self.assertEqual(len(self.tables()), 1)
            generation = int(self.tables()[0].stem.split('_')[-1])
            self.assertGreater(generation, previous)
            previous = generation
            data = json.loads(self.tables()[0].read_text())
            self.assertEqual(data, [[2, None], ['2', 'string'], ['K', 2],
                                   ['unique-0', [0, None]], ['unique-1', [1, None]],
                                   ['unique-2', [2, None]]])
            engine = self.reopen(engine)
            self.assert_records(engine)

    def test_wal_and_memtable_unchanged_and_replay_has_precedence(self):
        engine = self.engine()
        self.seed(engine)
        engine.put('K', 'WAL latest')
        engine.put('2', None)
        before = (self.root / 'wal.log').read_bytes()
        memory = engine.memtable.table.copy()
        size = engine.memtable.current_size
        with patch.object(engine.wal, 'clear', side_effect=AssertionError('WAL clear')):
            engine.compact()
        self.assertEqual((self.root / 'wal.log').read_bytes(), before)
        self.assertEqual(engine.memtable.table, memory)
        self.assertEqual(engine.memtable.current_size, size)
        recovered = self.reopen(engine)
        self.assertEqual(recovered.get('K'), 'WAL latest')
        self.assertIsNone(recovered.get('2'))
        recovered.flush_to_sstable()
        recovered.compact()
        self.assertEqual(self.reopen(recovered).get('K'), 'WAL latest')

    def test_empty_tables_noop(self):
        engine = self.engine()
        engine.put('only WAL', 1)
        engine.compact()
        self.assertEqual(self.tables(), [])
        self.assertEqual(engine.get('only WAL'), 1)

    def test_publication_sync_precedes_every_deletion(self):
        engine = self.engine()
        self.seed(engine)
        events = []
        real_sync, real_link, real_unlink = os.fsync, os.link, os.unlink

        def sync(fd):
            events.append('sync')
            return real_sync(fd)

        def link(source, destination):
            events.append('link')
            return real_link(source, destination)

        def unlink(path):
            events.append('unlink')
            return real_unlink(path)

        with patch('storage_engine.lsm_core.os.fsync', side_effect=sync), patch(
                'storage_engine.lsm_core.os.link', side_effect=link), patch(
                'storage_engine.lsm_core.os.unlink', side_effect=unlink):
            engine.compact()
        self.assertEqual(events, ['sync', 'link', 'sync'] + ['unlink'] * 5 + ['sync'])

    def test_failures_preserve_data_and_fence_mutations(self):
        # Each case starts with independent durable inputs and an empty WAL.
        cases = ['json.dump', 'os.link', 'file-sync', 'publish-sync',
                 'temp-unlink', 'first-input', 'second-input', 'cleanup-sync']
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                original_root = self.root
                self.root = Path(directory)
                engine = LSMTreeEngine(directory)
                self.addCleanup(engine.wal.close)
                self.seed(engine)
                inputs = {p.name: p.read_bytes() for p in self.tables()}
                real_sync, real_unlink = os.fsync, os.unlink
                sync_calls = 0
                input_calls = 0

                def sync(fd):
                    nonlocal sync_calls
                    sync_calls += 1
                    target = {'file-sync': 1, 'publish-sync': 2, 'cleanup-sync': 3}.get(case)
                    if sync_calls == target:
                        raise OSError('injected')
                    return real_sync(fd)

                def unlink(path):
                    nonlocal input_calls
                    if Path(path).name in inputs:
                        input_calls += 1
                        if input_calls == {'first-input': 1, 'second-input': 2}.get(case):
                            raise OSError('injected')
                    elif case == 'temp-unlink':
                        raise OSError('injected')
                    return real_unlink(path)

                operation = case if case in ('json.dump', 'os.link') else 'os.fsync'
                effect = OSError('injected') if operation == case else sync
                with patch('storage_engine.lsm_core.' + operation, side_effect=effect), patch(
                        'storage_engine.lsm_core.os.unlink', side_effect=unlink):
                    with self.assertRaisesRegex(OSError, 'injected'):
                        engine.compact()
                if case in ('json.dump', 'os.link', 'file-sync', 'publish-sync'):
                    for name, contents in inputs.items():
                        self.assertEqual((self.root / name).read_bytes(), contents)
                for action in (engine.compact, engine.flush_to_sstable,
                               lambda: engine.put('blocked', 1)):
                    with self.assertRaisesRegex(RuntimeError, 'reopen'):
                        action()
                engine.wal.close()
                recovered = LSMTreeEngine(directory)
                self.assert_records(recovered)
                recovered.compact()
                self.assert_records(recovered)
                recovered.wal.close()
                self.root = original_root

    def test_collision_never_overwrites_or_retries(self):
        engine = self.engine()
        self.seed(engine)
        inputs = {p.name: p.read_bytes() for p in self.tables()}
        real_link = os.link
        original = b'[["external", "preserved"]]'

        def collide(source, destination):
            Path(destination).write_bytes(original)
            return real_link(source, destination)

        with patch('storage_engine.lsm_core.os.link', side_effect=collide) as link:
            with self.assertRaises(FileExistsError):
                engine.compact()
        self.assertEqual(link.call_count, 1)
        self.assertEqual(self.tables()[-1].read_bytes(), original)
        for name, contents in inputs.items():
            self.assertEqual((self.root / name).read_bytes(), contents)
        self.assert_records(self.reopen(engine))

    def test_legacy_order_and_generation(self):
        for name, value in [('sstable_9.json', 'old'), ('sstable_100.json', 'new')]:
            (self.root / name).write_text(json.dumps([['K', value], [2, 'integer']]))
        engine = self.engine()
        engine.compact()
        self.assertEqual(self.tables()[0].name, 'sstable_v2_00000000000000000101.json')
        self.assertEqual(self.reopen(engine).get('K'), 'new')

    def test_sole_legacy_merged_and_first_duplicate_match(self):
        (self.root / 'sstable_merged_9.json').write_text(
            '[["K", null], ["K", "second"], ["2", "string"], [2, "integer"]]')
        engine = self.engine()
        engine.compact()
        engine = self.reopen(engine)
        self.assertIsNone(engine.get('K'))
        self.assertEqual(engine.get(2), 'integer')
        self.assertEqual(engine.get('2'), 'string')

    def test_invalid_or_ambiguous_inputs_remain_intact(self):
        engine = self.engine()
        for name, contents in [('sstable_merged_9.json', '[]'),
                               ('sstable_10.json', '[]')]:
            (self.root / name).write_text(contents)
        with self.assertRaisesRegex(ValueError, 'Ambiguous legacy'):
            engine.compact()
        self.assertEqual(len(self.tables()), 2)
        with self.assertRaisesRegex(ValueError, 'Ambiguous legacy'):
            self.reopen(engine)

    def test_malformed_table_fails_before_publication(self):
        for contents in ('{}', '[[true, 1]]', '[[1]]', '[[1, NaN]]'):
            with self.subTest(contents=contents):
                path = self.root / 'sstable_v2_00000000000000000001.json'
                path.write_text(contents)
                engine = self.engine()
                with self.assertRaises(ValueError):
                    engine.compact()
                self.assertEqual(path.read_text(), contents)
                self.assertEqual(self.tables(), [path])
                engine.wal.close()

    def test_abrupt_exit_before_publication_after_sync_and_partial_deletion(self):
        code = '''
import os, sys
from pathlib import Path
from unittest.mock import patch
from storage_engine.lsm_core import LSMTreeEngine
engine = LSMTreeEngine(sys.argv[1])
mode = sys.argv[2]
real_link, real_sync, real_unlink = os.link, os.fsync, os.unlink
calls = 0
def link(*args):
    if mode == 'before-link':
        os._exit(73)
    real_link(*args)
    if mode == 'after-link':
        os._exit(73)
def sync(fd):
    global calls
    real_sync(fd)
    calls += 1
    if mode == 'after-sync' and calls == 2:
        os._exit(73)
def unlink(path):
    real_unlink(path)
    if mode == 'partial-delete' and Path(path).name.startswith('sstable_'):
        os._exit(73)
with patch('storage_engine.lsm_core.os.link', side_effect=link), patch(
        'storage_engine.lsm_core.os.fsync', side_effect=sync), patch(
        'storage_engine.lsm_core.os.unlink', side_effect=unlink):
    engine.compact()
'''
        for mode in ('before-link', 'after-link', 'after-sync', 'partial-delete'):
            with self.subTest(mode=mode):
                engine = self.engine()
                self.seed(engine)
                before = len(self.tables())
                engine.wal.close()
                result = subprocess.run([sys.executable, '-B', '-c', code,
                                         self.directory.name, mode],
                                        cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                self.assertEqual(len(self.tables()), before + (mode in ('after-link', 'after-sync')))
                recovered = self.engine()
                self.assert_records(recovered)
                recovered.compact()
                self.assert_records(self.reopen(recovered))


if __name__ == '__main__':
    unittest.main()
