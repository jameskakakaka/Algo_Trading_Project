import contextlib
import io
import tempfile
import unittest
import sys
from collections import namedtuple
from types import SimpleNamespace
from unittest.mock import Mock, patch

from schemas.data_types import canonical_json
from storage_engine.lsm_core import LSMTreeEngine
from streaming.offline_pipeline import OfflineBarPipeline
from streaming.kafka_transport import (
    BarConsumerSession, BarPublisher, ConsumerFenced, DeliveryUncertain, TOPIC,
    decode_event, partition_key, _load_commit_types as load_commit_types,
)
from test_offline_pipeline import event, T, NOW

TopicPartition = namedtuple('TopicPartition', 'topic partition')
OffsetAndMetadata = namedtuple('OffsetAndMetadata', 'offset metadata leader_epoch')


class KafkaTests(unittest.TestCase):
    def setUp(self):
        commit_types = patch('streaming.kafka_transport._load_commit_types',
                             return_value=(TopicPartition, OffsetAndMetadata))
        commit_types.start()
        self.addCleanup(commit_types.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.open()

    def open(self):
        self.store = LSMTreeEngine(self.directory.name)
        self.addCleanup(self.store.wal.close)
        self.pipeline = OfflineBarPipeline(self.store)
        self.pipeline.register_stream(exchange='binance', symbol='BTCUSDT',
                                      timeframe='1m', start_time_ms=T)
        self.consumer = Mock()
        self.consumer.commit.side_effect = self.strict_commit
        self.session = BarConsumerSession(self.consumer, self.pipeline)

    def strict_commit(self, offsets):
        self.assertIs(type(offsets), dict)
        self.assertEqual(len(offsets), 1)
        for key, value in offsets.items():
            self.assertIs(type(key), TopicPartition)
            self.assertIs(type(value), OffsetAndMetadata)
            self.assertEqual(key, TopicPartition(TOPIC, 0))
            self.assertEqual(value.metadata, '')
            self.assertEqual(value.leader_epoch, -1)

    def record(self, index=0, offset=0):
        bar = event(index)
        return SimpleNamespace(topic=TOPIC, partition=0, offset=offset,
                               key=partition_key(bar), value=canonical_json(bar).encode())

    def test_publisher_observes_ack_and_stable_key(self):
        producer = Mock()
        self.assertIs(BarPublisher(producer).publish(event()), producer.send.return_value.get.return_value)
        producer.send.return_value.get.assert_called_once_with(timeout=10)
        self.assertEqual(partition_key(event()), partition_key(event(5)))
        self.assertNotEqual(partition_key(event()), partition_key(event(symbol='ETHUSDT')))

    def test_uncertain_delivery_is_not_success(self):
        producer = Mock()
        producer.send.return_value.get.side_effect = TimeoutError()
        with self.assertRaises(DeliveryUncertain):
            BarPublisher(producer).publish(event())

    def test_storage_precedes_commit_and_duplicate_is_idempotent(self):
        def commit(offsets):
            self.strict_commit(offsets)
            self.assertEqual(self.store.get('bar:v1:' + event()['event_id']), event())
            self.assertEqual(next(iter(offsets.values())).offset, self.consumer.commit.call_count)
        self.consumer.commit.side_effect = commit
        self.session.consume_one(self.record(), now_ms=NOW)
        before = self.store.wal.file.tell()
        self.session.consume_one(self.record(offset=1), now_ms=NOW)
        self.assertEqual(self.store.wal.file.tell(), before)

    def test_crash_after_store_before_commit_replays_without_write(self):
        self.consumer.commit.side_effect = TimeoutError('uncertain commit')
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(), now_ms=NOW)
        self.assertEqual(self.session.evidence['stage'], 'commit')
        self.store.wal.close()
        self.open()
        before = self.store.wal.file.tell()
        result = self.session.consume_one(self.record(), now_ms=NOW)
        self.assertEqual(result.persistence, 'already_stored')
        self.assertEqual(self.store.wal.file.tell(), before)

    def test_storage_failure_no_commit_and_fences(self):
        self.store.put = Mock(side_effect=OSError('storage failed'))
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(), now_ms=NOW)
        self.consumer.commit.assert_not_called()
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(), now_ms=NOW)

    def test_poison_and_retention_gap_never_commit(self):
        for kind in ('poison', 'gap', 'wrong_key', 'wrong_partition'):
            self.open()
            record = self.record(index=2 if kind == 'gap' else 0)
            if kind == 'poison':
                record.value = b'{bad'
            if kind == 'wrong_key':
                record.key = b'wrong'
            if kind == 'wrong_partition':
                record.partition = 1
            with self.assertRaises(ConsumerFenced):
                self.session.consume_one(record, now_ms=NOW)
            self.consumer.commit.assert_not_called()
            self.store.wal.close()

    def test_offset_hole_fences(self):
        self.session.consume_one(self.record(), now_ms=NOW)
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(1, 2), now_ms=NOW)
        self.assertEqual(self.consumer.commit.call_count, 1)

    def test_assignment_replays_and_rebalance_fences(self):
        self.session.on_partitions_revoked([])
        self.assertFalse(self.session.fenced)
        self.session.on_partitions_assigned([('market-bars-v1', 0)])
        self.consumer.seek_to_beginning.assert_called_once()
        self.session.on_partitions_revoked([('market-bars-v1', 0)])
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(), now_ms=NOW)

    def test_unknown_storage_outcome_reconciles_on_restart(self):
        real_put = self.store.put
        def uncertain(**kwargs):
            real_put(**kwargs)
            raise OSError('unknown outcome after durable write')
        self.store.put = uncertain
        with self.assertRaises(ConsumerFenced):
            self.session.consume_one(self.record(), now_ms=NOW)
        self.consumer.commit.assert_not_called()
        self.store.wal.close()
        self.open()
        self.assertEqual(self.session.consume_one(self.record(), now_ms=NOW).persistence, 'already_stored')

    def test_restart_after_committed_event_rebuilds(self):
        self.session.consume_one(self.record(), now_ms=NOW)
        self.store.wal.close()
        self.open()
        self.session.consume_one(self.record(), now_ms=NOW)
        self.session.consume_one(self.record(1, 1), now_ms=NOW)
        self.assertEqual(self.consumer.commit.call_count, 2)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            decode_event(b'{"x":1,"x":2}')

    def test_direct_native_record_gets_real_shaped_commit_types(self):
        record = self.record()
        record.topic_partition = ('untrusted-wrapper', 3)
        self.session.consume_one(record, now_ms=NOW)
        self.consumer.commit.assert_called_once_with({
            TopicPartition(TOPIC, 0): OffsetAndMetadata(1, '', -1)})

    def test_missing_or_incompatible_commit_types_rejected_before_processing(self):
        consumer, pipeline = Mock(), Mock()
        with patch('streaming.kafka_transport._load_commit_types', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                BarConsumerSession(consumer, pipeline)
        incompatible = namedtuple('BadOffset', 'unsupported_required_field')
        with patch('streaming.kafka_transport._load_commit_types',
                   return_value=(TopicPartition, incompatible)):
            with self.assertRaises(TypeError):
                BarConsumerSession(consumer, pipeline)
        consumer.assert_not_called()
        self.assertEqual(consumer.mock_calls, [])
        self.assertEqual(pipeline.mock_calls, [])

    def test_client_loader_rejects_missing_optional_package(self):
        import streaming.kafka_transport as transport
        with patch.object(transport, '_require_client', side_effect=ImportError('missing')):
            with self.assertRaisesRegex(RuntimeError, 'commit types unavailable'):
                load_commit_types()

    def test_cli_wrapper_uses_same_typed_direct_session(self):
        from tools import kafka_demo
        from tools.fixtures import bars
        bar = bars(1)[0]
        record = SimpleNamespace(topic=TOPIC, partition=0, offset=0,
                               key=partition_key(bar), value=canonical_json(bar).encode())
        consumer = Mock()
        consumer.commit.side_effect = self.strict_commit
        consumer.poll.return_value = {TopicPartition(TOPIC, 0): [record]}
        listener_module = SimpleNamespace(ConsumerRebalanceListener=object)
        with patch.dict(sys.modules, {'kafka.consumer.subscription_state': listener_module}), \
                patch.object(kafka_demo, '_require_client'), \
                patch.object(kafka_demo, 'make_consumer', return_value=consumer), \
                patch.dict('os.environ', {'KAFKA_BOOTSTRAP_SERVERS': '127.0.0.1:9092'}), \
                patch.object(sys, 'argv', ['kafka_demo', 'consume', '--allow-local-kafka', '--count', '1']):
            kafka_demo.main()
        consumer.commit.assert_called_once_with({
            TopicPartition(TOPIC, 0): OffsetAndMetadata(1, '', -1)})
        consumer.close.assert_called_once()
