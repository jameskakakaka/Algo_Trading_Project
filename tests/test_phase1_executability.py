"""Offline regression tests for Phase 1 executability."""
import ast
import contextlib
import io
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from storage_engine import data_lake_worker


ROOT = Path(__file__).resolve().parents[1]


class FakeConsumer:
    def __init__(self, records=(), error=None):
        self.records = records
        self.error = error
        self.closed = False

    def subscription(self):
        return {'raw_market_data'}

    def __iter__(self):
        for record in self.records:
            yield SimpleNamespace(value=record)
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


class FakeStore:
    def __init__(self):
        self.writes = []
        self.wal = Mock()

    def put(self, *, key, value):
        self.writes.append((key, value))


class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def make_worker(self, records=(), error=None):
        consumer = FakeConsumer(records, error)
        store = FakeStore()
        kafka = SimpleNamespace(KafkaConsumer=Mock(return_value=consumer))
        with patch.dict(sys.modules, {'kafka': kafka}), patch.object(
            data_lake_worker, 'LSMTreeEngine', return_value=store
        ):
            worker = data_lake_worker.DataLakeWorker()
        return worker, consumer, store

    def test_target_modules_parse(self):
        for name in ('lsm_core.py', 'data_lake_worker.py'):
            with self.subTest(module=name):
                path = ROOT / 'storage_engine' / name
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

    def test_consumer_closes_when_storage_initialization_fails(self):
        for close_error in (None, RuntimeError('close failed')):
            with self.subTest(close_error=close_error):
                consumer = FakeConsumer()
                consumer.close = Mock(wraps=consumer.close, side_effect=close_error)
                kafka = SimpleNamespace(KafkaConsumer=Mock(return_value=consumer))
                initialization_error = OSError('storage initialization failed')
                with patch.dict(sys.modules, {'kafka': kafka}), patch.object(
                    data_lake_worker, 'LSMTreeEngine', side_effect=initialization_error
                ) as store_factory:
                    with self.assertRaises(OSError) as raised:
                        data_lake_worker.DataLakeWorker()
                self.assertIs(raised.exception, initialization_error)
                kafka.KafkaConsumer.assert_called_once()
                store_factory.assert_called_once_with(data_dir='./data')
                consumer.close.assert_called_once_with()
                if close_error is None:
                    self.assertTrue(consumer.closed)
                else:
                    self.assertIs(raised.exception.__cause__, close_error)

    def test_three_records_are_written_inside_iteration(self):
        records = [dict(timestamp=str(i), symbol='BTC', close=i) for i in range(3)]
        worker, consumer, store = self.make_worker(records)

        class CheckingConsumer(FakeConsumer):
            def __iter__(self):
                for index, record in enumerate(self.records):
                    self_test.assertEqual(len(store.writes), index)
                    yield SimpleNamespace(value=record)
                self_test.assertEqual(len(store.writes), 3)

        self_test = self
        worker.consumer = CheckingConsumer(records)
        worker.start_listenting()
        self.assertEqual(store.writes, list(zip(range(3), records)))
        for (_, value), record in zip(store.writes, records):
            self.assertIs(value, record)
        self.assertTrue(worker.consumer.closed)
        store.wal.close.assert_called_once_with()

    def test_cleanup_on_subscription_error(self):
        worker, consumer, store = self.make_worker()
        consumer.subscription = Mock(side_effect=RuntimeError('subscription failed'))
        with self.assertRaisesRegex(RuntimeError, 'subscription failed'):
            worker.start_listenting()
        self.assertTrue(consumer.closed)
        store.wal.close.assert_called_once_with()

    def test_wal_closes_even_if_consumer_close_fails(self):
        worker, consumer, store = self.make_worker()
        consumer.close = Mock(side_effect=RuntimeError('close failed'))
        with self.assertRaisesRegex(RuntimeError, 'close failed'):
            worker.start_listenting()
        store.wal.close.assert_called_once_with()

    def test_cleanup_on_normal_empty_exit(self):
        worker, consumer, store = self.make_worker()
        worker.start_listenting()
        self.assertTrue(consumer.closed)
        store.wal.close.assert_called_once_with()
        self.assertEqual(store.writes, [])

    def test_cleanup_on_keyboard_interrupt(self):
        worker, consumer, store = self.make_worker(error=KeyboardInterrupt())
        worker.start_listenting()
        self.assertTrue(consumer.closed)
        store.wal.close.assert_called_once_with()

    def test_cleanup_on_processing_error(self):
        worker, consumer, store = self.make_worker([{'timestamp': 'invalid'}])
        with self.assertRaises(ValueError):
            worker.start_listenting()
        self.assertTrue(consumer.closed)
        store.wal.close.assert_called_once_with()

    def test_main_dispatches_to_existing_worker_api(self):
        with patch.object(data_lake_worker, 'DataLakeWorker') as factory:
            data_lake_worker.main()
        factory.assert_called_once_with()
        factory.return_value.start_listenting.assert_called_once_with()

    def test_script_entry_point_dispatch_and_cleanup(self):
        consumer = FakeConsumer()
        store = FakeStore()
        kafka = SimpleNamespace(KafkaConsumer=Mock(return_value=consumer))
        lsm = SimpleNamespace(LSMTreeEngine=Mock(return_value=store))
        with patch.dict(sys.modules, {'kafka': kafka, 'lsm_core': lsm}):
            runpy.run_path(str(ROOT / 'storage_engine' / 'data_lake_worker.py'),
                           run_name='__main__')
        kafka.KafkaConsumer.assert_called_once()
        lsm.LSMTreeEngine.assert_called_once_with(data_dir='./data')
        self.assertTrue(consumer.closed)
        store.wal.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
