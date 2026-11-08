import contextlib
import io
import tempfile
import unittest

from ai_op.research import train
from storage_engine.lsm_core import LSMTreeEngine
from streaming.offline_pipeline import OfflineBarPipeline
from streaming.research_pipeline import ResearchPipeline
from tools.demo import run_demo
from tools.fixtures import START, bars


class EndToEndTests(unittest.TestCase):
    def test_real_demo(self):
        result = run_demo()
        self.assertEqual(result['restart_reconciled'], 160)
        self.assertEqual(result['paper_execution'], 'disabled')
        self.assertEqual(result['network_requests'], 0)

    def test_duplicate_no_feature_row_and_gap_blocks_prediction(self):
        events = bars()
        artifact, _ = train(events, provenance='synthetic-test')
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            engine = LSMTreeEngine(directory)
            self.addCleanup(engine.wal.close)
            research = ResearchPipeline(OfflineBarPipeline(engine))
            stream = research.register_stream(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                                              start_time_ms=START)
            now = events[-1]['published_at_ms']
            for bar in events[:-2]:
                research.deliver(bar, now_ms=now)
            before = list(research.features[stream].window)
            research.deliver(events[-3], now_ms=now)
            self.assertEqual(list(research.features[stream].window), before)
            research.deliver(events[-1], now_ms=now)
            with self.assertRaises(ValueError):
                research.predict(stream, artifact, now_ms=now, replay=False)
