"""Deterministic synthetic acquisition fixtures. No real market observations."""
from ingestion.finalized_bars import FinalizedBarFetcher, TimeEvidence

START = 1_800_000_000_000
MINUTE = 60_000


def rows(count=160):
    result = []
    for index in range(count):
        opening = START + index*MINUTE
        price = str(100 + (index*7 % 19)) + '.1234567890123456789'
        result.append([opening, '100', '130', '80', price, str(10+index%5),
                       opening+MINUTE-1, '1000', 5, '5', '500', '0'])
    return result


class FixtureHTTP:
    def __init__(self, data):
        self.data = data

    def get(self, url, *, params, timeout):
        selected = [row for row in self.data if params['startTime'] <= row[0] <= params['endTime']]
        class Response:
            status_code = 200
            headers = {}

            def json(self):
                return selected[:params['limit']]
        return Response()


def fetcher(count=160):
    data = rows(count)
    now = START + count*MINUTE + 5000
    return FinalizedBarFetcher(FixtureHTTP(data), lambda: TimeEvidence(now), lambda _: None), now


def bars(count=160):
    source, _ = fetcher(count)
    result = source.fetch(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                          start_time_ms=START, end_time_ms=START+count*MINUTE)
    if not result.complete:
        raise RuntimeError('synthetic fixture generation incomplete')
    return result.bars
