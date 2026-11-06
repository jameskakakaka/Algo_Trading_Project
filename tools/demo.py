"""Network-free smoke: synthetic REST, durable bars, restart, features and gates."""
import contextlib
import io
import json
import tempfile

from ai_op.research import train
from schemas.data_types import storage_identity
from storage_engine.lsm_core import LSMTreeEngine
from streaming.offline_pipeline import OfflineBarPipeline
from streaming.research_pipeline import ResearchPipeline
from tools.fixtures import START, MINUTE, fetcher


def run_demo():
    source, now = fetcher(160)
    selected = source.fetch(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                            start_time_ms=START, end_time_ms=START+160*MINUTE)
    assert selected.complete
    # Request-start evidence before the final close excludes that last candle.
    early, _ = fetcher(160)
    from ingestion.finalized_bars import TimeEvidence
    early.clock = lambda: TimeEvidence(START+159*MINUTE)
    unfinished = early.fetch(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                             start_time_ms=START, end_time_ms=START+160*MINUTE)
    assert not unfinished.complete and unfinished.deferred
    with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
        engine = LSMTreeEngine(directory)
        try:
            pipeline = OfflineBarPipeline(engine)
            stream = pipeline.register_stream(exchange='binance', symbol='BTCUSDT',
                                              timeframe='1m', start_time_ms=START)
            for bar in selected.bars:
                assert pipeline.deliver(bar, now_ms=now).storage_confirmed
            duplicate = pipeline.deliver(selected.bars[-1], now_ms=now)
            assert duplicate.processing.outcome == 'duplicate'
        finally:
            engine.wal.close()
        reopened = LSMTreeEngine(directory)
        try:
            research = ResearchPipeline(OfflineBarPipeline(reopened))
            stream = research.register_stream(exchange='binance', symbol='BTCUSDT',
                                              timeframe='1m', start_time_ms=START)
            feature_rows = 0
            for bar in selected.bars:
                assert reopened.get(storage_identity(bar)) == bar
                assert research.deliver(bar, now_ms=now).persistence == 'already_stored'
                if research.latest[stream][1] is not None:
                    feature_rows += 1
            artifact, _ = train(selected.bars, provenance='synthetic deterministic fixture; no market performance claim')
            blocked = False
            try:
                research.predict(stream, artifact, now_ms=now)  # safe replay default
            except ValueError:
                blocked = True
            assert blocked
            probability = research.predict(stream, artifact, now_ms=now, replay=False)
            assert 0 <= probability <= 1
            gap_pipeline = OfflineBarPipeline(reopened)
            gap_pipeline.register_stream(exchange='binance', symbol='BTCUSDT',
                                         timeframe='1m', start_time_ms=START)
            assert gap_pipeline.deliver(selected.bars[2], now_ms=now).processing.outcome == 'gap'
            assert gap_pipeline.deliver(selected.bars[0], now_ms=now).storage_confirmed
            changed = dict(selected.bars[0], close='99')
            assert gap_pipeline.deliver(changed, now_ms=now).processing.outcome == 'conflict'
        finally:
            reopened.wal.close()
    return dict(source='synthetic REST fixtures', finalized_bars=160, restart_reconciled=160,
                feature_rows=feature_rows, duplicate='suppressed', gap='detected', conflict='quarantined',
                historical_inference='blocked', simulated_live_compatibility='passed',
                paper_execution='disabled', network_requests=0,
                profitability='not evaluated', kafka='not used')


def main():
    print(json.dumps(run_demo(), indent=2))


if __name__ == '__main__':
    main()
