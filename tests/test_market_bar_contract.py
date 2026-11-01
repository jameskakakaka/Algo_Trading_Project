"""Offline v1 contract regressions; standard library only."""
import json
import unittest
from decimal import localcontext

from schemas.data_types import (
    BarValidationError, INTERVAL_MS, REQUIRED_FIELDS, canonical_json,
    classify_bar_events, generate_event_id, market_content_equal,
    normalize_decimal, normalize_supported_value, operational_metadata_equal,
    storage_identity, validate_finalized_bar,
)


def bar(timeframe='1m', symbol='BTCUSDT'):
    start = 1800000000000
    end = start + INTERVAL_MS[timeframe]
    return dict(schema_version=1, event_type='market.bar.finalized',
                event_id=generate_event_id('binance', 'spot', symbol, timeframe, start),
                exchange='binance', market='spot', symbol=symbol, timeframe=timeframe,
                open_time_ms=start, end_time_ms=end, is_final=True,
                open='100', high='110', low='90', close='105', volume='0',
                observed_at_ms=end + 2000, published_at_ms=end + 3000,
                source='binance_rest')


class MarketBarContractTests(unittest.TestCase):
    def reject(self, **changes):
        event = dict(bar(), **changes)
        with self.assertRaises(BarValidationError):
            validate_finalized_bar(event)

    def test_valid_intervals(self):
        for interval in INTERVAL_MS:
            with self.subTest(interval=interval):
                event = bar(interval)
                self.assertEqual(validate_finalized_bar(event), event)
                self.assertIsNot(validate_finalized_bar(event), event)

    def test_unique_identities(self):
        events = [bar(t, s) for t in INTERVAL_MS for s in ('BTCUSDT', 'ETHUSDT')]
        self.assertEqual(len({storage_identity(e) for e in events}), 4)
        for event in events[1:]:
            self.assertEqual(classify_bar_events(events[0], event), 'distinct')
        self.assertNotEqual(storage_identity(bar()), storage_identity(dict(
            bar(), open_time_ms=1800000060000, end_time_ms=1800000120000,
            observed_at_ms=1800000122000, published_at_ms=1800000123000,
            event_id='binance:spot:BTCUSDT:1m:1800000060000')))

    def test_timestamp_types_and_units(self):
        for field in ('open_time_ms', 'end_time_ms', 'observed_at_ms', 'published_at_ms'):
            for value in (True, False, 1800000000, 1800000000000000,
                          1800000000000.0, '1800000000000', None):
                with self.subTest(field=field, value=value):
                    self.reject(**{field: value})

    def test_alignment_and_boundaries(self):
        self.reject(open_time_ms=1800000000001)
        for end in (1800000060001, 1800000059999, 1800000000000):
            self.reject(end_time_ms=end)
        with self.assertRaises(BarValidationError):
            generate_event_id('binance', 'spot', 'BTCUSDT', '15m', 1800000060000)

    def test_invalid_prices_and_volume(self):
        for field in ('open', 'high', 'low', 'close'):
            for value in ('0', '-1', '-0'):
                self.reject(**{field: value})
        self.reject(volume='-0.001')
        self.reject(low='106')
        self.reject(high='99')
        self.reject(low='111', high='90')

    def test_decimal_types_and_nonfinite(self):
        for field in ('open', 'high', 'low', 'close', 'volume'):
            for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', float('nan'),
                          float('inf'), 100, True, None, ' 100 ', '', '1_00'):
                with self.subTest(field=field, value=value):
                    self.reject(**{field: value})

    def test_required_fields_and_unknown_fields(self):
        for field in REQUIRED_FIELDS:
            event = bar()
            del event[field]
            with self.subTest(field=field), self.assertRaises(BarValidationError):
                validate_finalized_bar(event)
        self.reject(extra='value')
        for value in (None, [], 'event'):
            with self.assertRaises(BarValidationError):
                validate_finalized_bar(value)

    def test_version_type_and_final_marker(self):
        for value in (True, '1', 1.0, 2):
            self.reject(schema_version=value)
        self.reject(event_type='market.bar.snapshot')
        for value in (False, 1, 'true'):
            self.reject(is_final=value)

    def test_supported_identifiers(self):
        for changes in (dict(exchange='other'), dict(market='futures'),
                        dict(symbol='BTC:USDT'), dict(symbol=''),
                        dict(timeframe='1M'), dict(timeframe='5m'),
                        dict(symbol=123), dict(source='bad:source')):
            self.reject(**changes)
        self.assertEqual(normalize_supported_value('symbol', ' btcusdt '), 'BTCUSDT')
        event = dict(bar(), symbol=' btcusdt ', exchange=' BINANCE ', market='SPOT',
                     source=' BINANCE_REST ')
        self.assertEqual(validate_finalized_bar(event), bar())

    def test_non_ascii_identifiers_rejected_before_case_conversion(self):
        for field, value in (('symbol', 'ßUSDT'), ('symbol', 'ſUSDT'),
                             ('symbol', 'ıUSDT'), ('source', 'Kline'),
                             ('exchange', 'bınance'), ('market', 'ſpot'),
                             ('timeframe', '\u00a01m'), ('symbol', '\u00a0BTCUSDT')):
            with self.subTest(field=field, value=value):
                with self.assertRaises(BarValidationError):
                    normalize_supported_value(field, value)
                self.reject(**{field: value})
        for symbol in ('ßUSDT', 'ſUSDT', 'ıUSDT'):
            with self.assertRaises(BarValidationError):
                generate_event_id('binance', 'spot', symbol, '1m', 1800000000000)

    def test_ascii_identifier_whitespace_and_case_preserved(self):
        for field, value, expected in (
            ('symbol', ' \tbtcusdt\r\n', 'BTCUSDT'),
            ('exchange', '\tBINANCE ', 'binance'),
            ('market', ' SPOT\n', 'spot'),
            ('source', '\rKLINE\t', 'kline'),
            ('timeframe', ' \t15m\n', '15m'),
        ):
            with self.subTest(field=field):
                self.assertEqual(normalize_supported_value(field, value), expected)
        self.assertEqual(validate_finalized_bar(dict(
            bar(), symbol='\tbtcusdt ', exchange=' BINANCE\n',
            market='SPOT\r', timeframe=' 1m\t', source=' BINANCE_REST '
        )), bar())

    def test_event_id_mismatch(self):
        for value in ('wrong', None, 123, 'binance:spot:ETHUSDT:1m:1800000000000'):
            self.reject(event_id=value)

    def test_duplicates_and_metadata(self):
        a = bar()
        b = dict(a, open='1e2', volume='-0.000', observed_at_ms=a['observed_at_ms'] + 1,
                 published_at_ms=a['published_at_ms'] + 2, source='offline_replay')
        self.assertEqual(classify_bar_events(a, b), 'duplicate')
        self.assertTrue(market_content_equal(a, b))
        self.assertFalse(operational_metadata_equal(a, b))
        self.assertTrue(operational_metadata_equal(a, a))
        self.assertNotEqual(canonical_json(a), canonical_json(b))

    def test_content_conflicts(self):
        a = bar()
        for field, value in (('open', '101'), ('high', '111'), ('low', '89'),
                             ('close', '104'), ('volume', '1'),
                             ('end_time_ms', a['end_time_ms'] - 1)):
            with self.subTest(field=field):
                self.assertEqual(classify_bar_events(a, dict(a, **{field: value})), 'conflict')
        self.assertFalse(market_content_equal(a, dict(a, volume='1')))

    def test_metadata_consistency(self):
        self.reject(observed_at_ms=bar()['end_time_ms'] - 1)
        self.reject(published_at_ms=bar()['observed_at_ms'] - 1)
        event = bar()
        event['observed_at_ms'] = event['published_at_ms'] = event['end_time_ms']
        self.assertEqual(validate_finalized_bar(event), event)

    def test_decimal_normalization_and_round_trip(self):
        for value, expected in (('+00100.000', '100'), ('1e2', '100'),
                                ('.0100', '0.01'), ('-0.000', '0')):
            self.assertEqual(normalize_decimal(value), expected)
        exact = '100.123456789012345678901234567890123456789'
        with localcontext() as context:
            context.prec = 3
            self.assertEqual(normalize_decimal(exact), exact)
            event = dict(bar(), open=exact)
            canonical = validate_finalized_bar(event)
            self.assertEqual(json.loads(canonical_json(event)), canonical)
            self.assertEqual(canonical_json(canonical), canonical_json(event))
        self.assertEqual(event['open'], exact)
        for value in ('1e1000000000', '1e-1000000000', '1e' + '9' * 100, '1' * 257):
            with self.assertRaises(BarValidationError):
                normalize_decimal(value)

    def test_stable_storage_encoding(self):
        event = bar()
        self.assertEqual(storage_identity(event), 'bar:v1:binance:spot:BTCUSDT:1m:1800000000000')
        self.assertEqual(storage_identity(event), storage_identity(json.loads(canonical_json(event))))
        self.assertEqual(canonical_json(event), canonical_json(dict(reversed(list(event.items())))))


if __name__ == '__main__':
    unittest.main()
