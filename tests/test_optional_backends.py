"""Optional API/backend checks; unavailable dependencies are explicit skips."""
import importlib.util
import unittest


class OptionalBackendTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('kafka'), 'kafka-python unavailable; broker not exercised')
    def test_kafka_client_api_shape_without_connections(self):
        from kafka import KafkaConsumer, KafkaProducer
        from kafka.consumer.subscription_state import ConsumerRebalanceListener
        from kafka.structs import OffsetAndMetadata
        from streaming.kafka_transport import _require_client
        _require_client()
        self.assertTrue(callable(KafkaConsumer.commit))
        self.assertTrue(callable(KafkaProducer.send))
        self.assertIn('offset', OffsetAndMetadata._fields)
        self.assertTrue(callable(ConsumerRebalanceListener.on_partitions_assigned))

    @unittest.skipUnless(importlib.util.find_spec('xgboost'), 'XGBoost unavailable; optional training not exercised')
    def test_xgboost_native_json_round_trip(self):
        from ai_op.features import feature_vector
        from ai_op.research import probability, train
        from tools.fixtures import bars
        events = bars()
        artifact, _ = train(events, provenance='synthetic backend verification', kind='xgboost')
        value = probability(artifact['model'], feature_vector(events))
        self.assertTrue(0 <= value <= 1)
