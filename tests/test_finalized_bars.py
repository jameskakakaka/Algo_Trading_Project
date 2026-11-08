"""Synthetic HTTP/clock tests; never imports a network client."""
import unittest
from ingestion.finalized_bars import FinalizedBarFetcher, TimeEvidence
from schemas.data_types import BarValidationError, validate_finalized_bar

T = 1800000000000
M = 60000


def row(opening=T, step=M, close='105'):
    return [opening, '100.000', '110', '90', close, '12.12345678901234567890123456789',
            opening + step - 1, '1200', 5, '6', '600', '0']


class Response:
    def __init__(self, body=None, status=200, headers=None):
        self.body, self.status_code, self.headers = body, status, headers or {}

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Client:
    def __init__(self, replies):
        self.replies, self.calls = iter(replies), []

    def get(self, url, **kwargs):
        self.calls.append(kwargs)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FinalizedBarTests(unittest.TestCase):
    def setup_fetcher(self, replies, now=T + 20*M, uncertainty=0, **kwargs):
        client, sleeps = Client(replies), []
        fetcher = FinalizedBarFetcher(client, lambda: TimeEvidence(now, uncertainty),
                                     sleeps.append, **kwargs)
        return fetcher, client, sleeps

    def fetch(self, fetcher, count=1, timeframe='1m', start=T):
        return fetcher.fetch(exchange='binance', symbol='BTCUSDT', timeframe=timeframe,
                             start_time_ms=start, end_time_ms=start + count*(M if timeframe == '1m' else 15*M))

    def test_valid_intervals_conversion_precision_and_identity(self):
        for timeframe, step in [('1m', M), ('15m', 15*M)]:
            f, client, _ = self.setup_fetcher([Response([row(step=step)])])
            result = self.fetch(f, timeframe=timeframe)
            self.assertTrue(result.complete)
            event = result.bars[0]
            self.assertEqual(event['end_time_ms'], T + step)
            self.assertEqual(event['volume'], row()[5])
            self.assertEqual(validate_finalized_bar(event), event)
            self.assertEqual(event['event_id'], f'binance:spot:BTCUSDT:{timeframe}:{T}')
            self.assertEqual(client.calls[0]['params']['endTime'], T + step - 1)
            self.assertEqual(client.calls[0]['timeout'], (3.0, 10.0))

    def test_boundary_safety_and_uncertainty(self):
        for now, uncertainty, accepted in [(T+M-1, 0, False), (T+M, 0, False),
                                           (T+M+1999, 0, False), (T+M+2000, 0, True),
                                           (T+M+2000, 1, False), (T+M+2500, 500, True)]:
            with self.subTest(now=now, uncertainty=uncertainty):
                f, _, _ = self.setup_fetcher([Response([row()])], now, uncertainty)
                result = self.fetch(f)
                self.assertEqual(result.complete, accepted)
                self.assertEqual(len(result.bars), int(accepted))
                self.assertEqual(result.deferred, [] if accepted else [T])
        f, _, _ = self.setup_fetcher([Response([row()])], T+M, safety_delay_ms=0)
        self.assertTrue(self.fetch(f).complete)

    def test_pre_request_evidence_cannot_be_upgraded_by_response(self):
        times = iter([TimeEvidence(T+M-1), TimeEvidence(T+10*M)])
        f, _, _ = self.setup_fetcher([Response([row()])])
        f.clock = lambda: next(times)
        self.assertFalse(self.fetch(f).complete)

    def test_retry_uses_fresh_request_start_evidence(self):
        times = iter([TimeEvidence(T+M-1), TimeEvidence(T+M+2000)])
        f, _, _ = self.setup_fetcher([TimeoutError(), Response([row()])])
        f.clock = lambda: next(times)
        self.assertTrue(self.fetch(f).complete)

    def test_unfinished_tail_keeps_contiguous_prefix_only(self):
        f, _, _ = self.setup_fetcher([Response([row(), row(T+M)])], now=T+M+2000)
        result = self.fetch(f, 2)
        self.assertEqual(len(result.bars), 1)
        self.assertEqual(result.deferred, [T+M])
        self.assertEqual(result.next_cursor_ms, T+M)
        self.assertFalse(result.complete)

    def test_excessive_uncertainty(self):
        f, client, _ = self.setup_fetcher([], uncertainty=501)
        result = self.fetch(f)
        self.assertFalse(result.complete)
        self.assertEqual(client.calls, [])
        self.assertIn('clock_uncertainty', result.errors[0])
        self.assertEqual(result.next_cursor_ms, T)

    def test_overlap_duplicates_and_ordering(self):
        f, _, _ = self.setup_fetcher([Response([row(T+M), row()]),
                                      Response([row(T+M), row(T+2*M)])], page_size=2)
        result = self.fetch(f, 3)
        self.assertTrue(result.complete)
        self.assertEqual([b['open_time_ms'] for b in result.bars], [T, T+M, T+2*M])
        self.assertEqual(len(result.duplicates), 1)

    def test_repeated_snapshots_and_conflict_quarantine(self):
        for close, conflict in [('105.000', False), ('106', True)]:
            f, _, _ = self.setup_fetcher([Response([row(), row(close=close)])])
            result = self.fetch(f)
            self.assertEqual(bool(result.conflicts), conflict)
            self.assertEqual(len(result.duplicates), int(not conflict))
            self.assertEqual(result.complete, not conflict)
            if conflict:
                self.assertEqual(result.bars, [])
                self.assertEqual(result.next_cursor_ms, T)

    def test_cross_page_conflict(self):
        f, _, _ = self.setup_fetcher([Response([row()]),
                                      Response([row(close='106'), row(T+M)])])
        result = self.fetch(f, 2)
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.next_cursor_ms, T)
        self.assertEqual(len(result.bars), 1)

    def test_missing_middle_and_restart_backfill(self):
        f, _, _ = self.setup_fetcher([Response([row(), row(T+2*M)])])
        result = self.fetch(f, 3)
        self.assertEqual(result.gaps, [T+M])
        self.assertEqual(result.next_cursor_ms, T+M)
        self.assertFalse(result.complete)
        f, client, _ = self.setup_fetcher([Response([row(T+M), row(T+2*M)])])
        resumed = self.fetch(f, 2, start=result.next_cursor_ms)
        self.assertTrue(resumed.complete)
        self.assertEqual(client.calls[0]['params']['startTime'], T+M)

    def test_non_progress_and_page_budget(self):
        f, _, _ = self.setup_fetcher([Response([row()]), Response([row()])])
        result = self.fetch(f, 2)
        self.assertIn('non_progressing_page', result.errors)
        self.assertFalse(result.complete)
        f, _, _ = self.setup_fetcher([Response([row()])], max_pages=1)
        self.assertIn('page_budget_exhausted', self.fetch(f, 2).errors)

    def test_retries_timeout_rate_limit_and_server_error(self):
        for failure in [TimeoutError('timeout'), OSError('connection'),
                        Response(status=429, headers={'Retry-After': '2'}),
                        Response(status=503)]:
            with self.subTest(failure=failure):
                f, client, sleeps = self.setup_fetcher([failure, Response([row()])])
                result = self.fetch(f)
                self.assertTrue(result.complete)
                self.assertEqual(len(client.calls), 2)
                self.assertEqual(len(sleeps), 1)
                if isinstance(failure, Response) and failure.status_code == 429:
                    self.assertEqual(sleeps, [2.0])

    def test_retry_exhaustion_and_partial_download(self):
        f, client, _ = self.setup_fetcher([Response([row()]), TimeoutError(), TimeoutError(), TimeoutError()])
        result = self.fetch(f, 2)
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(len(result.bars), 1)
        self.assertEqual(result.next_cursor_ms, T+M)
        self.assertFalse(result.complete)
        self.assertIn('retries_exhausted', result.errors[0])

    def test_retry_after_budget_and_permanent_status(self):
        for response in [Response(status=429, headers={'Retry-After': '100'}),
                         Response(status=429, headers={'Retry-After': 'bad'}),
                         Response(status=418), Response(status=400)]:
            f, client, sleeps = self.setup_fetcher([response])
            result = self.fetch(f)
            self.assertTrue(result.errors)
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(sleeps, [])

    def test_malformed_json_and_response_shape(self):
        for body in [ValueError('bad JSON'), {}, [row(), row()], [row()[:-1]]]:
            f, _, _ = self.setup_fetcher([Response(body)], page_size=1)
            result = self.fetch(f)
            self.assertTrue(result.errors)
            self.assertFalse(result.complete)
            self.assertEqual(result.bars, [])

    def test_invalid_row_fields_and_page_atomicity(self):
        for index, value in [(0, True), (6, T+M), (8, True), (8, -1),
                             (1, 100.0), (2, '99'), (5, '-1'), (7, 'NaN'),
                             (9, -1), (10, 'Infinity'), (11, None)]:
            bad = row(T+M)
            bad[index] = value
            f, _, _ = self.setup_fetcher([Response([row(), bad])])
            result = self.fetch(f, 2)
            self.assertTrue(result.errors)
            self.assertEqual(result.bars, [])

    def test_outside_range_and_empty_response(self):
        f, _, _ = self.setup_fetcher([Response([row(T-M)])])
        self.assertTrue(self.fetch(f).errors)
        f, _, _ = self.setup_fetcher([Response([])])
        result = self.fetch(f, 2)
        self.assertEqual(result.gaps, [T, T+M])
        self.assertFalse(result.complete)

    def test_input_and_configuration_validation(self):
        f, _, _ = self.setup_fetcher([])
        for changes in [dict(start_time_ms=True), dict(end_time_ms=T),
                        dict(timeframe='5m'), dict(exchange='other'),
                        dict(start_time_ms=T+1)]:
            args = dict(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                        start_time_ms=T, end_time_ms=T+M)
            args.update(changes)
            with self.assertRaises(ValueError):
                f.fetch(**args)
        for kwargs in [dict(page_size=0), dict(page_size=1001), dict(retries=-1),
                       dict(timeout=(0, 1)), dict(max_pages=True), dict(retry_delay_s=float('inf'))]:
            with self.assertRaises(ValueError):
                self.setup_fetcher([], **kwargs)

    def test_same_stream_deterministic_across_calls(self):
        identities = []
        for now in (T+10*M, T+20*M):
            f, _, _ = self.setup_fetcher([Response([row()])], now)
            identities.append(self.fetch(f).bars[0]['event_id'])
        self.assertEqual(*identities)


if __name__ == '__main__':
    unittest.main()
