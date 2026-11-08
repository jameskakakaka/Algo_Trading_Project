"""Synthetic consumer correctness tests; no services or third-party imports."""
import json
import unittest
from decimal import Decimal

from schemas.data_types import INTERVAL_MS, generate_event_id, storage_identity
from streaming.bar_processor import BarProcessor, ModelSpec, decimal_ohlcv

T = 1800000000000
M = 60000


def bar(index=0, symbol='BTCUSDT', timeframe='1m', **changes):
    step = INTERVAL_MS[timeframe]
    opening = T + index * step
    event = dict(schema_version=1, event_type='market.bar.finalized',
                 event_id=generate_event_id('binance', 'spot', symbol, timeframe, opening),
                 exchange='binance', market='spot', symbol=symbol, timeframe=timeframe,
                 open_time_ms=opening, end_time_ms=opening+step, is_final=True,
                 open='100', high='110', low='90', close='105', volume='12.12345678901234567890123456789',
                 observed_at_ms=opening+step+1000, published_at_ms=opening+step+2000,
                 source='binance_rest')
    event.update(changes)
    return event


def model(symbol='BTCUSDT', timeframe='1m', warmup=2):
    return ModelSpec('binance', 'spot', symbol, timeframe, warmup)


class BarProcessorTests(unittest.TestCase):
    def setUp(self):
        self.processor = BarProcessor(window_size=3, history_size=4, max_age_ms=2*M)
        self.stream = self.register()

    def register(self, symbol='BTCUSDT', timeframe='1m', processor=None, start=T):
        return (processor or self.processor).register_stream(
            exchange='binance', symbol=symbol, timeframe=timeframe, start_time_ms=start)

    def process(self, event, **kwargs):
        return self.processor.process(event, now_ms=kwargs.pop('now_ms', T+20*M), **kwargs)

    def test_duplicate_ignores_metadata_and_decimal_spelling(self):
        self.assertEqual(self.process(bar()).outcome, 'accepted')
        before = self.processor.snapshot(self.stream)
        duplicate = bar(open='1e2', source='offline_replay', observed_at_ms=T+M+3000,
                        published_at_ms=T+M+4000)
        for _ in range(10):
            result = self.process(duplicate)
            self.assertEqual(result.outcome, 'duplicate')
            self.assertFalse(result.inference_ready)
        self.assertEqual(self.processor.snapshot(self.stream), before)

    def test_conflict_quarantine_and_fence(self):
        self.process(bar())
        result = self.process(bar(close='106'))
        self.assertEqual(result.outcome, 'conflict')
        state = self.processor.snapshot(self.stream)
        self.assertEqual(state['window'], [])
        self.assertEqual([b['close'] for b in state['conflict']], ['105', '106'])
        self.assertEqual(self.process(bar(1)).outcome, 'deferred')
        self.assertEqual(self.processor.snapshot(self.stream), state)

    def test_interleaved_stream_isolation(self):
        streams = [self.stream, self.register('ETHUSDT'), self.register(timeframe='15m')]
        streams.append(self.register('ETHUSDT', '15m'))
        for index in range(2):
            for symbol, timeframe in [('BTCUSDT', '1m'), ('ETHUSDT', '1m'),
                                      ('BTCUSDT', '15m'), ('ETHUSDT', '15m')]:
                self.assertEqual(self.process(bar(index, symbol, timeframe), now_ms=T+60*M).outcome, 'accepted')
        for stream in streams:
            snapshot = self.processor.snapshot(stream)
            self.assertEqual(len(snapshot['window']), 2)
            self.assertTrue(all((b['symbol'], b['timeframe']) == stream[2:] for b in snapshot['window']))
        keys = {storage_identity(bar(0, s, t)) for s in ('BTCUSDT', 'ETHUSDT') for t in ('1m', '15m')}
        self.assertEqual(len(keys), 4)

    def test_gap_backfill_and_resubmission(self):
        self.process(bar())
        gap = self.process(bar(2), replay=False, model=model())
        self.assertEqual(gap.outcome, 'gap')
        self.assertEqual(gap.missing_range, (T+M, T+2*M))
        self.assertEqual(gap.next_cursor_ms, T+M)
        self.assertEqual(len(self.processor.snapshot(self.stream)['window']), 1)
        restored = self.process(bar(1), replay=False, model=model(), now_ms=T+3*M+2000)
        self.assertEqual(restored.outcome, 'accepted')
        self.assertIn('unresolved_gap', restored.inference_blocks)
        last = self.process(bar(2), replay=False, model=model(), now_ms=T+3*M+2000)
        self.assertTrue(last.inference_ready)
        self.assertIsNone(self.processor.snapshot(self.stream)['recovery_end_ms'])
        self.assertEqual([b['open_time_ms'] for b in self.processor.snapshot(self.stream)['window']], [T, T+M, T+2*M])

    def test_recovery_high_water_does_not_shrink(self):
        self.process(bar(4))
        self.process(bar(2))
        for index in range(4):
            result = self.process(bar(index), replay=False, model=model(), now_ms=T+5*M+2000)
            self.assertFalse(result.inference_ready)
            self.assertIn('unresolved_gap', result.inference_blocks)
        self.assertTrue(self.process(bar(4), replay=False, model=model(), now_ms=T+5*M+2000).inference_ready)

    def test_older_unknown_is_not_a_duplicate(self):
        for index in range(6):
            self.process(bar(index))
        before = self.processor.snapshot(self.stream)
        self.assertEqual(len(before['window']), 3)
        self.assertEqual(len(before['history']), 4)
        self.assertEqual(self.process(bar(0)).outcome, 'out_of_order')
        self.assertEqual(self.process(bar(2)).outcome, 'duplicate')
        self.assertEqual(self.processor.snapshot(self.stream), before)
        self.assertEqual(self.process(bar(2, close='106')).outcome, 'conflict')

    def test_initial_cursor_rejects_unknown_older_record(self):
        processor = BarProcessor()
        stream = self.register(processor=processor, start=T+M)
        before = processor.snapshot(stream)
        result = processor.process(bar(), now_ms=T+3*M)
        self.assertEqual(result.outcome, 'out_of_order')
        self.assertEqual(processor.snapshot(stream), before)

    def test_malformed_inputs_do_not_mutate_state(self):
        self.process(bar())
        before = self.processor.snapshot(self.stream)
        for event in (None, {}, [], bar(close=None), bar(close=105.0),
                      dict(bar(), symbol='ßUSDT'), bar(end_time_ms=T+M+60000),
                      bar(volume='NaN'), bar(open_time_ms=True), bar(is_final=False)):
            with self.subTest(event=event):
                self.assertEqual(self.process(event).outcome, 'rejected')
                self.assertEqual(self.processor.snapshot(self.stream), before)

    def test_json_boundaries(self):
        for payload in ('null', '{bad', '[]', '{"x":1,"x":2}', None,
                        json.dumps(bar(close=None)), json.dumps(bar(close=105.0))):
            before = self.processor.snapshot(self.stream)
            result = self.processor.process_json(payload, now_ms=T+20*M)
            self.assertEqual(result.outcome, 'rejected')
            self.assertEqual(self.processor.snapshot(self.stream), before)
        self.assertEqual(self.processor.process_json(json.dumps(bar()), now_ms=T+20*M).outcome, 'accepted')
        self.assertEqual(self.processor.process_json(json.dumps(bar()), now_ms=T+20*M).outcome, 'duplicate')

    def test_exact_decimal_conversion_and_storage_key(self):
        event = bar()
        values = decimal_ohlcv(event)
        self.assertEqual(values['volume'], Decimal(event['volume']))
        self.assertIsInstance(values['close'], Decimal)
        with self.assertRaises(ValueError):
            decimal_ohlcv(bar(volume=None))
        result = self.process(event)
        self.assertEqual(result.storage_key, storage_identity(event))
        self.assertEqual(result.storage_key, 'bar:v1:binance:spot:BTCUSDT:1m:1800000000000')

    def test_replay_warmup_and_live_gates(self):
        first = self.process(bar(), replay=False, model=model(), now_ms=T+M+2000)
        self.assertIn('insufficient_warmup', first.inference_blocks)
        second = self.process(bar(1), model=model(), now_ms=T+2*M+2000)
        self.assertIn('historical_replay', second.inference_blocks)
        live = self.process(bar(2), replay=False, model=model(), now_ms=T+3*M+2000)
        self.assertTrue(live.inference_ready)
        self.assertFalse(live.paper_trading_enabled)

    def test_stale_and_model_mismatch_blocks(self):
        stale = self.process(bar(), replay=False, model=model(warmup=1))
        self.assertTrue(stale.stale)
        self.assertIn('stale_record', stale.inference_blocks)
        mismatch = self.process(bar(1), replay=False, model=model(timeframe='15m'), now_ms=T+2*M+2000)
        self.assertIn('model_stream_mismatch', mismatch.inference_blocks)
        no_model = self.process(bar(2), replay=False, now_ms=T+3*M+2000)
        self.assertIn('model_metadata_missing', no_model.inference_blocks)
        too_large = self.process(bar(3), replay=False, model=model(warmup=4), now_ms=T+4*M+2000)
        self.assertIn('insufficient_warmup', too_large.inference_blocks)

    def test_staleness_recomputed_at_each_call(self):
        self.process(bar(), replay=False, model=model(warmup=1), now_ms=T+M+2000)
        result = self.process(bar(), replay=False, model=model(warmup=1), now_ms=T+20*M)
        self.assertTrue(result.stale)
        self.assertFalse(result.inference_ready)

    def test_future_metadata_and_unregistered_stream_defer_without_mutation(self):
        before = self.processor.snapshot(self.stream)
        self.assertEqual(self.process(bar(), now_ms=T+M).reason, 'future_metadata')
        self.assertEqual(self.process(bar(symbol='ETHUSDT')).reason, 'unregistered_stream')
        self.assertEqual(self.processor.snapshot(self.stream), before)

    def test_snapshot_and_input_mutation_cannot_change_internal_state(self):
        event = bar()
        self.process(event)
        event['close'] = '106'
        view = self.processor.snapshot(self.stream)
        view['history'][0]['close'] = '107'
        view['window'].clear()
        actual = self.processor.snapshot(self.stream)
        self.assertEqual(actual['window'][0]['close'], '105')
        self.assertEqual(actual['history'][0]['close'], '105')

    def test_conflict_in_one_stream_does_not_fence_another(self):
        eth = self.register('ETHUSDT')
        self.process(bar())
        self.process(bar(close='106'))
        self.assertEqual(self.process(bar(symbol='ETHUSDT')).outcome, 'accepted')
        self.assertIsNone(self.processor.snapshot(eth)['conflict'])

    def test_capacity_and_invalid_context(self):
        processor = BarProcessor(window_size=1, history_size=1, max_streams=1)
        self.register(processor=processor)
        with self.assertRaises(ValueError):
            self.register('ETHUSDT', processor=processor)
        with self.assertRaises(ValueError):
            self.register(processor=processor)
        for kwargs in (dict(window_size=True), dict(history_size=1), dict(max_streams=0)):
            with self.assertRaises(ValueError):
                BarProcessor(**kwargs)
        before = self.processor.snapshot(self.stream)
        for kwargs in (dict(now_ms=True), dict(replay='false'), dict(model='path')):
            args = dict(now_ms=T+20*M)
            args.update(kwargs)
            with self.assertRaises(ValueError):
                self.processor.process(bar(), **args)
        self.assertEqual(self.processor.snapshot(self.stream), before)


if __name__ == '__main__':
    unittest.main()
