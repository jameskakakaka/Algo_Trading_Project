"""Shared bounded-window features v1. Storage retains decimals; ML uses float.

Each row recomputes from exactly the trailing 60 completed 1m bars. EMA uses an
SMA seed; RSI/ATR use Wilder smoothing. This intentionally replaces legacy ta
initialization, and cannot load legacy models. Offline and streaming call this
same implementation, including the same warm-up and window reset policy.
"""
import math
from collections import deque
from statistics import fmean, pstdev

from schemas.data_types import validate_finalized_bar

VERSION = 'bounded-indicators-v1'
TIMEFRAME = '1m'
WARMUP = 60
FEATURES = ('RSI_14', 'MACD_hist', 'BB_high', 'BB_low', 'Dist_to_EMA50',
            'ATR_14', 'close', 'volume')


def _ema(values, period):
    result = [fmean(values[:period])]
    for value in values[period:]:
        result.append(result[-1] + 2 / (period + 1) * (value - result[-1]))
    return result


def _wilder(values, period=14):
    value = fmean(values[:period])
    for item in values[period:]:
        value += (item - value) / period
    return value


def feature_vector(bars: list) -> tuple:
    """Require one contiguous stream. Fail on gaps, duplicates or float overflow."""
    canonical = [validate_finalized_bar(bar) for bar in bars[-WARMUP:]]
    if len(canonical) < WARMUP:
        raise ValueError('insufficient warmup: 60 finalized bars required')
    stream = tuple(canonical[0][k] for k in ('exchange', 'market', 'symbol', 'timeframe'))
    if stream[-1] != TIMEFRAME:
        raise ValueError('modeling timeframe must be 1m')
    for previous, current in zip(canonical, canonical[1:]):
        if tuple(current[k] for k in ('exchange', 'market', 'symbol', 'timeframe')) != stream:
            raise ValueError('mixed modeling streams')
        if current['open_time_ms'] != previous['end_time_ms']:
            raise ValueError('noncontiguous modeling bars')
    close = [float(bar['close']) for bar in canonical]
    high = [float(bar['high']) for bar in canonical]
    low = [float(bar['low']) for bar in canonical]
    changes = [b-a for a, b in zip(close, close[1:])]
    gain = _wilder([max(x, 0) for x in changes])
    loss = _wilder([max(-x, 0) for x in changes])
    rsi = 50 if gain == loss == 0 else (100 if loss == 0 else 100-100/(1+gain/loss))
    fast, slow = _ema(close, 12), _ema(close, 26)
    macd = [a-b for a, b in zip(fast[-len(slow):], slow)]
    histogram = macd[-1] - _ema(macd, 9)[-1]
    mean, spread = fmean(close[-20:]), 2*pstdev(close[-20:])
    ema50 = _ema(close, 50)[-1]
    tr = [max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
          for i in range(1, WARMUP)]
    result = (rsi, histogram, mean+spread, mean-spread,
              (close[-1]-ema50)/ema50*100, _wilder(tr), close[-1],
              float(canonical[-1]['volume']))
    if not all(math.isfinite(value) for value in result):
        raise ValueError('nonfinite model feature')
    return result


class FeatureStream:
    """Call only for storage-confirmed, contiguous accepted bars; never duplicates."""
    def __init__(self):
        self.window = deque(maxlen=WARMUP)
        self.stream = None
        self.end = None

    def add(self, event: dict):
        bar = validate_finalized_bar(event)
        stream = tuple(bar[k] for k in ('exchange', 'market', 'symbol', 'timeframe'))
        if stream[-1] != TIMEFRAME or (self.stream and stream != self.stream):
            raise ValueError('incompatible feature stream')
        if self.end is not None and bar['open_time_ms'] != self.end:
            raise ValueError('feature gap/duplicate; rebuild required')
        self.stream, self.end = stream, bar['end_time_ms']
        self.window.append(bar)
        return feature_vector(list(self.window)) if len(self.window) == WARMUP else None
