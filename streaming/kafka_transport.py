"""At-least-once transport. No Kafka import, network or account access on import.

One topic partition per local demonstration. Every consumer session rebuilds
from retained beginning and trusted stream starts; committed offsets are audit
progress, not sufficient processor/feature checkpoints. Never reuse after fence.
"""
import json

from schemas.data_types import IDENTITY_FIELDS, canonical_json, validate_finalized_bar

TOPIC = 'market-bars-v1'
GROUP = 'market-bars-lsm-v1'


class DeliveryUncertain(RuntimeError):
    """Publication may have reached Kafka; replay the same event identity."""


class ConsumerFenced(RuntimeError):
    """Stop, close, reconcile storage and rebuild/replay with a new session."""


def partition_key(event: dict) -> bytes:
    bar = validate_finalized_bar(event)
    return ':'.join(bar[k] for k in IDENTITY_FIELDS[:4]).encode('ascii')


def decode_event(payload: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    if type(payload) is not bytes or len(payload) > 64_000:
        raise ValueError('event must be bytes within 64000 byte budget')
    return validate_finalized_bar(json.loads(payload.decode('utf-8'), object_pairs_hook=unique))


class BarPublisher:
    def __init__(self, producer, *, topic=TOPIC, timeout_s=10):
        self.producer, self.topic, self.timeout_s = producer, topic, timeout_s

    def publish(self, event: dict):
        """Only a resolved broker acknowledgement is reported as published."""
        bar = validate_finalized_bar(event)
        try:
            return self.producer.send(self.topic, key=partition_key(bar),
                                      value=canonical_json(bar).encode('utf-8')).get(
                                          timeout=self.timeout_s)
        except Exception as error:
            raise DeliveryUncertain('broker delivery uncertain; replay identical identity') from error


def _load_commit_types():
    """Resolve real client types before a session can mutate application state."""
    try:
        _require_client()
        from kafka import TopicPartition
        from kafka.structs import OffsetAndMetadata
    except ImportError as error:
        raise RuntimeError('Kafka commit types unavailable; install the reviewed optional client') from error
    return TopicPartition, OffsetAndMetadata


class BarConsumerSession:
    """Stop-on-poison policy: no skip, no commit, retained payload is broker evidence.

    Persist before commit. Commit errors and gaps fence the whole session. This
    intentionally sacrifices availability rather than advancing across a gap.
    Rebalances invalidate state; a new session must replay retained history.
    """
    def __init__(self, consumer, pipeline, *, topic=TOPIC):
        self._partition_type, self._offset_type = _load_commit_types()
        if not all(isinstance(cls, type) for cls in (self._partition_type, self._offset_type)):
            raise TypeError('Kafka commit types must be concrete client classes')
        # Fail incompatible client shapes before accepting/persisting any event.
        self._commit_arguments(topic, 0, 0)
        self.consumer, self.pipeline = consumer, pipeline
        self.topic = topic
        self.fenced = False
        self.evidence = None
        self._last = {}
        self._assigned = False

    def _commit_arguments(self, topic, partition, next_offset):
        fields = dict(offset=next_offset, metadata='')
        if 'leader_epoch' in getattr(self._offset_type, '_fields', ()):
            fields['leader_epoch'] = -1
        key = self._partition_type(topic, partition)
        value = self._offset_type(**fields)
        if type(key) is not self._partition_type or type(value) is not self._offset_type:
            raise TypeError('incompatible Kafka commit argument types')
        return {key: value}

    def on_partitions_revoked(self, partitions):
        # Kafka may announce an empty revoke before the initial assignment.
        if self._assigned or partitions:
            self.fenced = True

    def on_partitions_assigned(self, partitions):
        if self._assigned or len(partitions) != 1:
            self.fenced = True
            return
        self._assigned = True
        self.consumer.seek_to_beginning(*partitions)

    def consume_one(self, record, *, now_ms):
        if self.fenced:
            raise ConsumerFenced('session fenced; rebuild/replay required')
        # Evidence deliberately excludes payloads and exception messages.
        self.evidence = dict(topic=record.topic, partition=record.partition,
                             offset=record.offset, stage='validation')
        try:
            if (record.topic != self.topic or type(record.partition) is not int
                    or record.partition != 0 or type(record.offset) is not int or record.offset < 0):
                raise ValueError('unexpected topic/partition; local contract requires partition 0')
            offsets = self._commit_arguments(record.topic, record.partition, record.offset + 1)
            identity = (record.topic, record.partition)
            previous = self._last.get(identity)
            if previous is not None and record.offset != previous + 1:
                raise ValueError('offset discontinuity; possible retention gap')
            bar = decode_event(record.value)
            if record.key != partition_key(bar):
                raise ValueError('partition key does not match stream')
            self.evidence['stage'] = 'storage'
            delivery = self.pipeline.deliver(bar, now_ms=now_ms)
            duplicate = (delivery.processing is not None and
                         delivery.processing.outcome == 'duplicate')
            if delivery.fenced or not (delivery.storage_confirmed or duplicate):
                raise ValueError('unresolved bar: gap/conflict/invalid/recovery required')
            if self.fenced:
                raise ConsumerFenced('rebalance during persistence')
            self.evidence['stage'] = 'commit'
            # Always build from validated record fields; never trust a tuple or
            # caller-supplied record.topic_partition wrapper attribute.
            self.consumer.commit(offsets)
            self._last[identity] = record.offset
            return delivery
        except BaseException as error:
            self.fenced = True
            if not isinstance(error, Exception):
                raise
            raise ConsumerFenced('processing failed; no safe continuation') from error

    def close(self):
        self.consumer.close()


def make_producer(bootstrap_servers):
    """Optional kafka-python boundary; version/runtime validation remains separate."""
    _require_client()
    from kafka import KafkaProducer
    return KafkaProducer(bootstrap_servers=bootstrap_servers, acks='all', retries=3,
                         max_in_flight_requests_per_connection=1,
                         request_timeout_ms=5000, max_block_ms=5000)


def make_consumer(bootstrap_servers, group_id=GROUP):
    _require_client()
    from kafka import KafkaConsumer
    return KafkaConsumer(bootstrap_servers=bootstrap_servers, group_id=group_id,
                         enable_auto_commit=False, auto_offset_reset='none',
                         max_poll_records=1, consumer_timeout_ms=1000,
                         request_timeout_ms=10000, session_timeout_ms=6000,
                         heartbeat_interval_ms=2000, allow_auto_create_topics=False)


def _require_client():
    from importlib.metadata import version
    if version('kafka-python') != '2.3.3':
        raise RuntimeError('optional Kafka demo requires kafka-python==2.3.3')
