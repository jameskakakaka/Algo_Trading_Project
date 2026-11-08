"""Offline integration with synthetic REST and real temporary LSM directories."""
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch

from ingestion.finalized_bars import FinalizedBarFetcher, TimeEvidence
from schemas.data_types import generate_event_id, storage_identity, validate_finalized_bar
from storage_engine.lsm_core import LSMTreeEngine
from streaming.bar_processor import ProcessResult
from streaming.offline_pipeline import AcceptedBarStore, OfflineBarPipeline

T, M = 1800000000000, 60000
NOW = T + 100*M


def row(index=0, step=M, close='105'):
    opening = T + index*step
    return [opening, '100.000', '110', '90', close,
            '12.12345678901234567890123456789', opening+step-1,
            '1200', 5, '6', '600', '0']


def event(index=0, symbol='BTCUSDT', timeframe='1m', **changes):
    step = M if timeframe == '1m' else 15*M
    opening = T+index*step
    bar = dict(schema_version=1, event_type='market.bar.finalized',
               event_id=generate_event_id('binance', 'spot', symbol, timeframe, opening),
               exchange='binance', market='spot', symbol=symbol, timeframe=timeframe,
               open_time_ms=opening, end_time_ms=opening+step, is_final=True,
               open='100', high='110', low='90', close='105', volume=row()[5],
               observed_at_ms=NOW, published_at_ms=NOW, source='binance_rest')
    bar.update(changes)
    return bar


class Response:
    status_code = 200
    headers = {}

    def __init__(self, rows):
        self.rows = rows

    def json(self):
        return self.rows


class SyntheticHTTP:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(kwargs)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return Response(reply)


class CountingStore:
    def __init__(self, engine):
        self.engine = engine
        self.writes = 0
        self.failure = None

    def get(self, key):
        return self.engine.get(key)

    def put(self, *, key, value):
        self.writes += 1
        if self.failure == 'before':
            raise OSError('before write')
        self.engine.put(key=key, value=value)
        if self.failure == 'after':
            raise OSError('after durable write: unknown to caller')


class OfflinePipelineTests(unittest.TestCase):
    def setUp(self):
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.engines = []
        self.addCleanup(self.close_engines)
        self.engine = self.open_engine()
        self.store = CountingStore(self.engine)

    def open_engine(self):
        engine = LSMTreeEngine(self.directory.name)
        self.engines.append(engine)
        return engine

    def close_engines(self):
        for engine in self.engines:
            engine.wal.close()

    def pipeline(self, replies=None, now=NOW):
        http = SyntheticHTTP(replies or [])
        fetcher = FinalizedBarFetcher(http, lambda: TimeEvidence(now), lambda _: None, retries=0)
        pipeline = OfflineBarPipeline(self.store, fetcher=fetcher)
        stream = pipeline.register_stream(exchange='binance', symbol='BTCUSDT',
                                          timeframe='1m', start_time_ms=T)
        return pipeline, stream, http

    def fetch(self, pipeline, count=1, start=T, **kwargs):
        args = dict(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                    start_time_ms=start, end_time_ms=start+count*M)
        args.update(kwargs)
        return pipeline.fetch_and_store(now_ms=NOW, **args)

    def test_finalized_rest_to_exact_storage_and_order(self):
        pipeline, stream, _ = self.pipeline([[row(1), row(0), row(2)]])
        result = self.fetch(pipeline, 3)
        self.assertTrue(result.complete)
        self.assertEqual(self.store.writes, 3)
        self.assertEqual([d.processing.next_cursor_ms for d in result.deliveries], [T+M, T+2*M, T+3*M])
        for index in range(3):
            self.assertEqual(self.engine.get(storage_identity(event(index))), event(index))
        self.assertEqual(pipeline.snapshot(stream)['confirmed_next_cursor_ms'], T+3*M)

    def test_fetch_overlap_and_delivery_duplicates_skip_writes(self):
        pipeline, stream, _ = self.pipeline([[row(), row()]])
        batch = self.fetch(pipeline)
        self.assertEqual(len(batch.fetched.duplicates), 1)
        before = pipeline.snapshot(stream)
        duplicate = pipeline.deliver(event(open='1e2', source='replay'), now_ms=NOW)
        self.assertEqual(duplicate.processing.outcome, 'duplicate')
        self.assertEqual(duplicate.persistence, 'not_attempted')
        self.assertEqual(self.store.writes, 1)
        self.assertEqual(pipeline.snapshot(stream), before)

    def test_processing_conflict_does_not_overwrite(self):
        pipeline, stream, _ = self.pipeline()
        pipeline.deliver(event(), now_ms=NOW)
        result = pipeline.deliver(event(close='106'), now_ms=NOW)
        self.assertEqual(result.processing.outcome, 'conflict')
        self.assertEqual(self.store.writes, 1)
        self.assertEqual(self.engine.get(storage_identity(event()))['close'], '105')
        self.assertIsNotNone(pipeline.snapshot(stream)['processor']['conflict'])
        self.assertEqual(pipeline.deliver(event(1), now_ms=NOW).processing.outcome, 'deferred')

    def test_fetch_conflict_fences_entire_batch(self):
        pipeline, _, http = self.pipeline([[row(), row(close='106'), row(1)]])
        result = self.fetch(pipeline, 2)
        self.assertTrue(result.fenced)
        self.assertFalse(result.complete)
        self.assertEqual(self.store.writes, 0)
        self.assertIsNotNone(pipeline.quarantine)
        self.assertEqual(self.fetch(pipeline).deliveries, ())
        self.assertEqual(len(http.calls), 1)

    def test_mixed_symbol_timeframe_storage_isolation(self):
        pipeline, _, _ = self.pipeline()
        keys = set()
        for symbol, timeframe in [('BTCUSDT', '1m'), ('ETHUSDT', '1m'), ('BTCUSDT', '15m'), ('ETHUSDT', '15m')]:
            if (symbol, timeframe) != ('BTCUSDT', '1m'):
                pipeline.register_stream(exchange='binance', symbol=symbol, timeframe=timeframe, start_time_ms=T)
            for index in range(2):
                bar = event(index, symbol, timeframe)
                delivery = pipeline.deliver(bar, now_ms=NOW)
                self.assertTrue(delivery.storage_confirmed)
                keys.add(delivery.processing.storage_key)
                self.assertEqual(self.engine.get(storage_identity(bar)), bar)
        self.assertEqual(len(keys), 8)
        self.assertEqual(self.store.writes, 8)

    def test_gap_blocks_and_backfill_restores(self):
        pipeline, stream, _ = self.pipeline([[row(), row(2)], [row(1), row(2)]])
        first = self.fetch(pipeline, 3)
        self.assertFalse(first.complete)
        self.assertEqual(first.fetched.gaps, [T+M])
        self.assertEqual(first.deliveries[1].processing.outcome, 'gap')
        state = pipeline.snapshot(stream)
        self.assertEqual(state['confirmed_next_cursor_ms'], T+M)
        self.assertEqual(state['processor']['next_cursor_ms'], T+M)
        self.assertIsNone(self.engine.get(storage_identity(event(2))))
        second = self.fetch(pipeline, 2, start=T+M)
        self.assertTrue(second.complete)
        self.assertEqual(pipeline.snapshot(stream)['confirmed_next_cursor_ms'], T+3*M)
        self.assertEqual(self.store.writes, 3)

    def test_restart_replay_reconciles_existing_without_rewrites(self):
        pipeline, stream, _ = self.pipeline()
        for index in range(7):
            pipeline.deliver(event(index), now_ms=NOW)
        self.engine.wal.close()
        self.engine = self.open_engine()
        self.store = CountingStore(self.engine)
        rebuilt, stream, _ = self.pipeline()
        for index in range(7):
            result = rebuilt.deliver(event(index, source='replay'), now_ms=NOW)
            self.assertEqual(result.persistence, 'already_stored')
            self.assertTrue(result.storage_confirmed)
            self.assertFalse(result.write_acknowledged)
            self.assertEqual(self.engine.get(storage_identity(event(index))), event(index))
        self.assertEqual(self.store.writes, 0)
        self.assertEqual(rebuilt.snapshot(stream)['processor']['next_cursor_ms'], T+7*M)

    def test_storage_conflict_on_restart_fences_without_overwrite(self):
        self.engine.put(key=storage_identity(event()), value=event())
        pipeline, stream, _ = self.pipeline()
        result = pipeline.deliver(event(close='106'), now_ms=NOW)
        self.assertEqual(result.persistence, 'conflict')
        self.assertTrue(result.fenced)
        self.assertFalse(result.storage_confirmed)
        self.assertEqual(result.confirmed_next_cursor_ms, T)
        self.assertEqual(pipeline.snapshot(stream)['processor']['next_cursor_ms'], T+M)
        self.assertEqual(self.store.writes, 0)
        self.assertEqual(self.engine.get(storage_identity(event()))['close'], '105')
        self.assertIsNotNone(pipeline.quarantine)

    def test_write_failure_after_acceptance_fences_all_streams(self):
        pipeline, stream, _ = self.pipeline()
        pipeline.register_stream(exchange='binance', symbol='ETHUSDT', timeframe='1m', start_time_ms=T)
        self.store.failure = 'before'
        result = pipeline.deliver(event(), now_ms=NOW)
        self.assertEqual(result.processing.outcome, 'accepted')
        self.assertEqual(result.persistence, 'storage_error')
        self.assertFalse(result.storage_confirmed)
        self.assertEqual(result.confirmed_next_cursor_ms, T)
        self.assertEqual(pipeline.snapshot(stream)['processor']['next_cursor_ms'], T+M)
        self.store.failure = None
        for bar in (event(), event(symbol='ETHUSDT')):
            self.assertEqual(pipeline.deliver(bar, now_ms=NOW).persistence, 'fenced')
        self.assertEqual(self.store.writes, 1)

    def test_unknown_write_reconciled_only_after_reopen_and_rebuild(self):
        pipeline, _, _ = self.pipeline()
        self.store.failure = 'after'
        failed = pipeline.deliver(event(), now_ms=NOW)
        self.assertEqual(failed.persistence, 'storage_error')
        self.assertFalse(failed.storage_confirmed)
        self.assertEqual(pipeline.deliver(event(), now_ms=NOW).persistence, 'fenced')
        self.engine.wal.close()
        self.engine = self.open_engine()
        self.store = CountingStore(self.engine)
        rebuilt, _, _ = self.pipeline()
        reconciled = rebuilt.deliver(event(), now_ms=NOW)
        self.assertEqual(reconciled.persistence, 'already_stored')
        self.assertEqual(self.store.writes, 0)
        self.assertTrue(reconciled.storage_confirmed)

    def test_absent_failed_write_replayed_after_reopen(self):
        pipeline, _, _ = self.pipeline()
        self.store.failure = 'before'
        pipeline.deliver(event(), now_ms=NOW)
        self.engine.wal.close()
        self.engine = self.open_engine()
        self.store = CountingStore(self.engine)
        rebuilt, _, _ = self.pipeline()
        self.assertEqual(rebuilt.deliver(event(), now_ms=NOW).persistence, 'stored')
        self.assertEqual(self.store.writes, 1)

    def test_real_wal_sync_error_fences_and_reconciles(self):
        pipeline, _, _ = self.pipeline()
        with patch('storage_engine.lsm_core.os.fsync', side_effect=OSError('sync failure')):
            result = pipeline.deliver(event(), now_ms=NOW)
        self.assertTrue(result.fenced)
        self.assertFalse(result.storage_confirmed)
        self.assertTrue(self.engine.wal.failed)
        self.engine.wal.close()
        self.engine = self.open_engine()
        # A recovered readable WAL entry is not proof its failed fsync succeeded.
        # Republish/synchronize recovered state before declaring reconciliation.
        self.engine.flush_to_sstable()
        self.store = CountingStore(self.engine)
        rebuilt, _, _ = self.pipeline()
        self.assertEqual(rebuilt.deliver(event(), now_ms=NOW).persistence, 'already_stored')

    def test_invalid_and_unfinished_events_never_persist(self):
        pipeline, stream, _ = self.pipeline()
        before = pipeline.snapshot(stream)
        for bar in (None, event(close=None), event(is_final=False), event(end_time_ms=T+M-1)):
            self.assertEqual(pipeline.deliver(bar, now_ms=NOW).processing.outcome, 'rejected')
        self.assertEqual(pipeline.snapshot(stream), before)
        unfinished, _, _ = self.pipeline([[row()]], now=T+M-1)
        batch = self.fetch(unfinished)
        self.assertFalse(batch.complete)
        self.assertEqual(batch.deliveries, ())
        self.assertEqual(self.store.writes, 0)

    def test_replay_has_no_inference_or_execution(self):
        pipeline, _, _ = self.pipeline([[row(), row(1)]])
        batch = self.fetch(pipeline, 2)
        for delivery in batch.deliveries:
            decision = delivery.processing
            self.assertFalse(decision.inference_ready)
            self.assertFalse(decision.paper_trading_enabled)
            self.assertIn('historical_replay', decision.inference_blocks)
            self.assertIn('model_metadata_missing', decision.inference_blocks)

    def test_adapter_refuses_nonaccepted_and_copies_values(self):
        adapter = AcceptedBarStore(self.store)
        for outcome in ('duplicate', 'conflict', 'gap', 'out_of_order', 'rejected', 'deferred'):
            with self.assertRaises(ValueError):
                adapter.persist(event(), ProcessResult(outcome, '', storage_key=storage_identity(event())))
        self.assertEqual(self.store.writes, 0)
        pipeline, _, _ = self.pipeline()
        bar = event()
        pipeline.deliver(bar, now_ms=NOW)
        bar['close'] = '106'
        self.assertEqual(self.engine.get(storage_identity(event()))['close'], '105')

    def test_partial_fetch_and_storage_read_failure_are_explicit(self):
        pipeline, stream, _ = self.pipeline([[row()], TimeoutError('timeout')])
        result = self.fetch(pipeline, 2)
        self.assertFalse(result.complete)
        self.assertTrue(result.fetched.errors)
        self.assertEqual(pipeline.snapshot(stream)['confirmed_next_cursor_ms'], T+M)
        with patch.object(self.store, 'get', side_effect=OSError('read failure')):
            delivery = pipeline.deliver(event(1), now_ms=NOW)
        self.assertEqual(delivery.persistence, 'storage_error')
        self.assertTrue(delivery.fenced)

    def test_corrupt_stored_value_never_overwritten(self):
        self.engine.put(key=storage_identity(event()), value={'invalid': 'bar'})
        pipeline, _, _ = self.pipeline()
        result = pipeline.deliver(event(), now_ms=NOW)
        self.assertTrue(result.fenced)
        self.assertEqual(result.persistence, 'storage_error')
        self.assertEqual(self.store.writes, 0)
        self.assertEqual(self.engine.get(storage_identity(event())), {'invalid': 'bar'})


if __name__ == '__main__':
    unittest.main()
