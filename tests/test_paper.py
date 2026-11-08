import copy
import unittest
from ai_op.features import feature_vector
from ai_op.research import train
from execution_engine.simulator import PaperAccount
from tools.fixtures import bars


class PaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars = bars()
        cls.artifact, _ = train(cls.bars, provenance='synthetic-test')
        cls.artifact['model']['weights'] = [0.0]*8 + [10.0]
        cls.vector = feature_vector(cls.bars)
        cls.event = cls.bars[-1]

    def execute(self, account, **options):
        args = dict(now_ms=self.event['published_at_ms'], replay=False, healthy=True)
        args.update(options)
        return account.process(self.artifact, self.vector, self.event, **args)

    def test_default_disabled(self):
        with self.assertRaisesRegex(ValueError, 'disabled'):
            self.execute(PaperAccount())

    def test_replay_stale_and_incomplete_rejected_without_mutation(self):
        account = PaperAccount(enabled=True)
        for options in ({'replay': True}, {'healthy': False},
                        {'now_ms': self.event['published_at_ms']+300_000}):
            before = account.snapshot()
            with self.assertRaises(ValueError):
                self.execute(account, **options)
            self.assertEqual(account.snapshot(), before)

    def test_fees_slippage_dedup_and_explicit_restore(self):
        account = PaperAccount(enabled=True)
        fill = self.execute(account)
        self.assertEqual(fill['side'], 'buy')
        self.assertGreater(float(fill['price']), float(self.event['close']))
        self.assertGreater(float(fill['fee']), 0)
        state = copy.deepcopy(account.snapshot())
        self.assertIsNone(self.execute(account))
        self.assertEqual(account.snapshot(), state)
        restored = PaperAccount.restore(state, enabled=True)
        self.assertIsNone(self.execute(restored))
        self.assertEqual(restored.snapshot(), state)
