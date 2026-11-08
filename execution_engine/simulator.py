"""Explicit, isolated paper account. No broker/exchange order API exists here."""
from decimal import Decimal
from ai_op.research import infer
from schemas.data_types import validate_finalized_bar


class PaperAccount:
    def __init__(self, *, enabled=False, cash='10000', fee_bps='2', slippage_bps='1'):
        self.enabled = enabled
        self.cash, self.fee, self.slippage = map(Decimal, (cash, fee_bps, slippage_bps))
        if (not all(v.is_finite() for v in (self.cash, self.fee, self.slippage))
                or self.cash < 0 or not 0 <= self.fee < 10000
                or not 0 <= self.slippage < 10000 or type(enabled) is not bool):
            raise ValueError('invalid account configuration')
        self.quantity = Decimal(0)
        self.seen = set()
        self.fills = []
        self.last_end = None

    def process(self, artifact, vector, event, *, now_ms, replay=True, healthy=False):
        if not self.enabled:
            raise ValueError('paper execution disabled')
        bar = validate_finalized_bar(event)
        confidence = infer(artifact, vector, bar, now_ms=now_ms, replay=replay, healthy=healthy)
        if bar['event_id'] in self.seen:
            return None
        if self.last_end is not None and bar['end_time_ms'] <= self.last_end:
            raise ValueError('out-of-order simulation signal')
        self.seen.add(bar['event_id'])
        self.last_end = bar['end_time_ms']
        buy = confidence >= .5 and self.quantity == 0 and self.cash > 0
        sell = confidence < .5 and self.quantity > 0
        if not buy and not sell:
            return None
        price = Decimal(bar['close']) * (1 + (self.slippage if buy else -self.slippage)/10000)
        # At most one base unit; no borrowing, shorts or leverage.
        quantity = min(Decimal(1), self.cash/(price*(1+self.fee/10000))) if buy else self.quantity
        gross = price*quantity
        fee = gross*self.fee/10000
        self.cash += -gross-fee if buy else gross-fee
        self.quantity += quantity if buy else -quantity
        fill = dict(event_id=bar['event_id'], side='buy' if buy else 'sell',
                    price=str(price), quantity=str(quantity), fee=str(fee))
        self.fills.append(fill)
        return dict(fill)

    def snapshot(self):
        """Caller persists atomically if opting into restartable simulation."""
        return dict(version=1, cash=str(self.cash), quantity=str(self.quantity),
                    fee_bps=str(self.fee), slippage_bps=str(self.slippage),
                    seen=sorted(self.seen), fills=[dict(f) for f in self.fills], last_end=self.last_end)

    @classmethod
    def restore(cls, state, *, enabled=False):
        if state['version'] != 1:
            raise ValueError('unsupported simulation snapshot')
        account = cls(enabled=enabled, cash=state['cash'], fee_bps=state['fee_bps'],
                      slippage_bps=state['slippage_bps'])
        account.quantity = Decimal(state['quantity'])
        if not account.quantity.is_finite() or account.quantity < 0 or account.quantity > 1:
            raise ValueError('invalid restored quantity')
        account.seen = set(state['seen'])
        account.fills = [dict(f) for f in state['fills']]
        account.last_end = state['last_end']
        return account
