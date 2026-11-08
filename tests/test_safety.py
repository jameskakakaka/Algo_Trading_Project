import importlib
import unittest
from unittest.mock import patch


class SafetyTests(unittest.TestCase):
    def test_legacy_imports_have_no_network_or_dependencies(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            for name in ('ingestion.fetcher', 'ingestion.historical_downloader',
                         'ai_op.train_pipeline', 'ai_op.train_pipelinev2', 'ai_op.backtester',
                         'ai_op.feature_engineer', 'execution_engine.paper_trading_bot'):
                importlib.reload(importlib.import_module(name))

    def test_old_bot_cannot_activate_or_load_pickle(self):
        from execution_engine.paper_trading_bot import LiveTradingBot
        with self.assertRaisesRegex(RuntimeError, 'retired'):
            LiveTradingBot()

    def test_legacy_network_optin_required(self):
        from tools.legacy import require_network_opt_in
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(RuntimeError):
                require_network_opt_in()
