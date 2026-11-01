"""Deterministic single-writer model tests; stdlib only, real local files.

Run: python3 -B -m unittest discover -s tests -p test_storage_lifecycle.py -v
Failure context includes seed/index and the exact executed operation prefix.
"""
from collections import Counter
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

from storage_engine import lsm_core as storage

SEEDS = (0, 1, 7, 42, 73, 101, 2025, 65537)
STEPS = 300
KEYS = (0, '0', 2, '2', -3, '-3', '', '02', 'a::b\n雪', 10**20, 'hot')
MISSING = object()


def visible_state(engine):
    """Presence oracle: public get cannot distinguish stored null from absence.

    Test-created directories contain v2 tables only. Independently reconstruct
    their numeric order rather than calling the production enumeration helper.
    """
    state = {}
    paths = sorted(Path(engine.data_dir).glob('sstable_v2_*.json'),
                   key=lambda p: int(p.stem.split('_')[-1]))
    for path in paths:
        table = {}
        for key, value in json.loads(path.read_text(encoding='utf-8')):
            table.setdefault(key, value)
        state.update(table)
    state.update(engine.memtable.table)
    return state


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        # Reads print per file; retain unittest diagnostics without megabytes of noise.
        sink = redirect_stdout(io.StringIO())
        sink.__enter__()
        self.addCleanup(sink.__exit__, None, None, None)

    def engine(self, directory):
        engine = storage.LSMTreeEngine(directory)
        self.addCleanup(engine.wal.close)
        return engine

    def reopen(self, engine):
        engine.wal.close()
        return self.engine(engine.data_dir)

    def check(self, engine, expected):
        self.assertEqual(visible_state(engine), expected)
        # Compare exact key identities, not stringified identities.
        self.assertEqual({(type(k), k) for k in visible_state(engine)},
                         {(type(k), k) for k in expected})
        for key, value in expected.items():
            self.assertEqual(engine.get(key), value, repr(key))
        for key in ('never-written', 987654321, True, 2.0):
            self.assertIsNone(engine.get(key))

    def compact(self, engine):
        wal = Path(engine.wal.filepath).read_bytes()
        memory = deepcopy(engine.memtable.table)
        size = engine.memtable.current_size
        engine.compact()
        self.assertEqual(Path(engine.wal.filepath).read_bytes(), wal)
        self.assertEqual(engine.memtable.table, memory)
        self.assertEqual(engine.memtable.current_size, size)

    def put(self, engine, expected, key, value):
        # Guard every successful workload put against implicit compaction.
        with patch.object(engine, 'compact', side_effect=AssertionError('automatic compaction')):
            engine.put(key, value)
        expected[key] = deepcopy(value)  # Only after acknowledgment.

    def test_seeded_complete_lifecycle(self):
        for seed in SEEDS:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as directory:
                rng = random.Random(seed)
                engine = self.engine(directory)
                expected, trace, counts = {}, [], Counter()
                for index in range(STEPS):
                    action = rng.choice(('put', 'put', 'get', 'flush', 'compact',
                                         'reopen', 'overwrite'))
                    key = rng.choice(KEYS)
                    value = rng.choice((None, index, f'雪-{seed}-{index}',
                                        {'seed': seed, 'nested': [index, None, {'ok': True}]},
                                        [False, {'value': index}, 'text']))
                    trace.append((action, key, value))
                    try:
                        counts[action] += 1
                        if action in ('put', 'overwrite'):
                            self.put(engine, expected, key, value)
                            if action == 'overwrite':
                                self.put(engine, expected, key, {'latest': [seed, index, None]})
                                counts['extra-put'] += 1
                        elif action == 'get':
                            self.assertEqual(engine.get(key), expected.get(key))
                        elif action == 'flush':
                            engine.flush_to_sstable()
                        elif action == 'compact':
                            self.compact(engine)
                        else:
                            before = Path(engine.wal.filepath).read_bytes()
                            engine = self.reopen(engine)
                            self.assertEqual(Path(engine.wal.filepath).read_bytes(), before)
                        self.check(engine, expected)
                    except Exception as error:
                        self.fail(f'seed={seed} index={index} counts={dict(counts)} '
                                  f'error={error!r}\nreplay prefix={trace!r}')
                # WAL overlay/replay on both sides of compaction, then persisted state.
                self.put(engine, expected, 2, None)
                self.put(engine, expected, '2', {'overlay': seed})
                engine = self.reopen(engine)
                self.check(engine, expected)
                self.compact(engine)
                engine = self.reopen(engine)
                self.check(engine, expected)
                engine.flush_to_sstable()
                self.compact(engine)
                for _ in range(3):
                    engine = self.reopen(engine)
                    self.check(engine, expected)
                print(f'seed={seed} steps={STEPS} counts={dict(counts)}', file=sys.stderr)

    def test_partial_wal_write_is_uncertain_and_tail_repair_is_stable(self):
        for complete in (False, True):
            with self.subTest(complete=complete), tempfile.TemporaryDirectory() as directory:
                engine = self.engine(directory)
                expected = {}
                self.put(engine, expected, 2, 'acknowledged')
                self.put(engine, expected, '2', None)
                before = Path(engine.wal.filepath).read_bytes()
                real_write = engine.wal.file.write
                attempted = {'new': [None, '雪']}

                def partial(record):
                    real_write(record if complete else record[:len(record) // 2])
                    engine.wal.file.flush()
                    raise OSError('partial write')

                with patch.object(engine.wal.file, 'write', side_effect=partial):
                    with self.assertRaisesRegex(OSError, 'partial write'):
                        engine.put(2, attempted)
                self.assertEqual(engine.memtable.table, expected)
                for action in (lambda: engine.put('blocked', 1),
                               engine.flush_to_sstable, engine.compact):
                    with self.assertRaisesRegex(RuntimeError, 'reopen'):
                        action()
                engine = self.reopen(engine)
                selected = deepcopy(expected)
                if complete:
                    selected[2] = attempted  # Recovered uncertainty, not an ack.
                else:
                    self.assertEqual(Path(engine.wal.filepath).read_bytes(), before)
                self.check(engine, selected)
                for _ in range(3):
                    engine = self.reopen(engine)
                    self.check(engine, selected)
                self.put(engine, selected, 2, 'new acknowledgment')
                engine.flush_to_sstable()
                self.compact(engine)
                self.check(self.reopen(engine), selected)

    def test_fault_matrix(self):
        # Counters scoped to the operation under test, never the seed setup.
        flush = (('json.dump', 1), ('os.fsync', 1), ('os.link', 1),
                 ('os.fsync', 2), ('os.unlink', 1), ('os.fsync', 3),
                 ('os.replace', 1), ('os.fsync', 4))
        compact = (('json.dump', 1), ('os.fsync', 1), ('os.link', 1),
                   ('os.fsync', 2), ('os.unlink', 1), ('os.unlink', 2),
                   ('os.unlink', 3), ('os.fsync', 3))
        wal = (('write', 1), ('flush', 1), ('os.fsync', 1), ('os.fsync', 2))
        total = 0
        for operation, points in (('put', wal), ('flush', flush),
                                  ('threshold', flush), ('compact', compact)):
            for target, occurrence in points:
                for after in (False, True):
                    label = (operation, target, occurrence, 'after' if after else 'before')
                    with self.subTest(fault=label), tempfile.TemporaryDirectory() as directory:
                        engine = self.engine(directory)
                        expected = {}
                        for cycle in range(3):
                            for key in (2, '2', 'hot'):
                                self.put(engine, expected, key, [cycle, str(type(key)), None])
                            engine.flush_to_sstable()
                        self.put(engine, expected, 2, None)
                        self.put(engine, expected, '2', {'pending': [True, None]})
                        if operation == 'threshold':
                            self.put(engine, expected, 'third', 3)
                            self.put(engine, expected, 'fourth', 4)
                        wal_before = Path(engine.wal.filepath).read_bytes()
                        memory_before = deepcopy(engine.memtable.table)
                        inputs = {p.name: p.read_bytes() for p in Path(directory).glob('sstable_*.json')}
                        # A failed overwrite may supersede the acknowledged value.
                        uncertain_key = 'hot' if operation == 'put' else 'fifth'
                        uncertain_value = {'uncertain': list(label)}
                        calls = 0
                        # Threshold put synchronizes its WAL before entering flush.
                        wal_syncs = 2 if operation == 'threshold' and target == 'os.fsync' else 0
                        failure_call = occurrence + wal_syncs
                        owner, attribute = ((engine.wal.file, target) if target in ('write', 'flush')
                                            else (getattr(storage, target.split('.')[0]), target.split('.')[1]))
                        real = getattr(owner, attribute)

                        def inject(*args, **kwargs):
                            nonlocal calls
                            calls += 1
                            if calls == failure_call:
                                if after:
                                    real(*args, **kwargs)
                                raise OSError('phase2d injected')
                            return real(*args, **kwargs)

                        with ExitStack() as stack:
                            stack.enter_context(patch.object(owner, attribute, side_effect=inject))
                            with self.assertRaisesRegex(OSError, 'phase2d injected'):
                                if operation in ('put', 'threshold'):
                                    engine.put(uncertain_key, uncertain_value)
                                elif operation == 'flush':
                                    engine.flush_to_sstable()
                                else:
                                    engine.compact()
                        self.assertGreaterEqual(calls, failure_call, label)
                        # All three mutations must be fenced, without touching files.
                        before_fence = {p.name: p.read_bytes() for p in Path(directory).iterdir()}
                        for action in (lambda: engine.put('blocked', 1),
                                       engine.flush_to_sstable, engine.compact):
                            with self.assertRaisesRegex(RuntimeError, 'reopen'):
                                action()
                        self.assertEqual({p.name: p.read_bytes() for p in Path(directory).iterdir()}, before_fence)
                        if operation == 'compact':
                            self.assertEqual(Path(engine.wal.filepath).read_bytes(), wal_before)
                            self.assertEqual(engine.memtable.table, memory_before)
                            self.assertEqual(engine.memtable.current_size, len(memory_before))
                        for name, contents in inputs.items():
                            if (Path(directory) / name).exists():
                                self.assertEqual((Path(directory) / name).read_bytes(), contents)
                        engine = self.reopen(engine)
                        # Keep acknowledged model untouched. The only legal uncertainty
                        # is old/absent versus the attempted latest value for this key.
                        recovered = visible_state(engine)
                        selected = deepcopy(expected)
                        if operation in ('put', 'threshold'):
                            actual = recovered.get(uncertain_key, MISSING)
                            old = expected.get(uncertain_key, MISSING)
                            self.assertTrue(actual == old or actual == uncertain_value, label)
                            if actual == uncertain_value:
                                selected[uncertain_key] = uncertain_value
                        self.check(engine, selected)
                        for _ in range(3):
                            engine = self.reopen(engine)
                            self.check(engine, selected)
                        # Resume normal lifecycle and overwrite uncertainty with an ack.
                        self.put(engine, selected, uncertain_key, {'acknowledged-after-reopen': True})
                        engine.flush_to_sstable()
                        self.compact(engine)
                        engine = self.reopen(engine)
                        self.check(engine, selected)
                        total += 1
        print(f'fault scenarios={total} (before/after real operation)', file=sys.stderr)


if __name__ == '__main__':
    unittest.main()
