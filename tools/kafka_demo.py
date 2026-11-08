"""Opt-in loopback Kafka demo using synthetic fixtures only. No exchange calls."""
import argparse
import os
import tempfile
import time

from storage_engine.lsm_core import LSMTreeEngine
from streaming.kafka_transport import (
    BarConsumerSession, BarPublisher, TOPIC, make_consumer, make_producer, _require_client,
)
from streaming.offline_pipeline import OfflineBarPipeline
from tools.fixtures import START, bars


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create-topic', 'publish', 'consume'])
    parser.add_argument('--allow-local-kafka', action='store_true', required=True)
    parser.add_argument('--count', type=int, default=160)
    args = parser.parse_args()
    servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', '127.0.0.1:9092')
    if servers not in ('127.0.0.1:9092', 'localhost:9092'):
        raise ValueError('demo permits loopback broker only')
    _require_client()
    if args.action == 'create-topic':
        from kafka.admin import KafkaAdminClient, NewTopic
        admin = KafkaAdminClient(bootstrap_servers=servers)
        try:
            admin.create_topics([NewTopic(TOPIC, num_partitions=1, replication_factor=1,
                                         topic_configs={'cleanup.policy': 'delete',
                                                        'retention.ms': '604800000'})])
        finally:
            admin.close()
        print('Created single-partition fixture topic')
    elif args.action == 'publish':
        producer = make_producer(servers)
        try:
            publisher = BarPublisher(producer)
            for bar in bars(args.count):
                publisher.publish(bar)
        finally:
            producer.close(timeout=10)
        print(f'Acknowledged {args.count} synthetic events')
    else:
        from kafka.consumer.subscription_state import ConsumerRebalanceListener
        consumer = make_consumer(servers)
        with tempfile.TemporaryDirectory() as directory:
            try:
                engine = LSMTreeEngine(directory)
                try:
                    pipeline = OfflineBarPipeline(engine)
                    stream = pipeline.register_stream(exchange='binance', symbol='BTCUSDT', timeframe='1m',
                                                      start_time_ms=START)
                    session = BarConsumerSession(consumer, pipeline)

                    class Listener(ConsumerRebalanceListener):
                        def on_partitions_revoked(self, partitions):
                            session.on_partitions_revoked(partitions)

                        def on_partitions_assigned(self, partitions):
                            session.on_partitions_assigned(partitions)

                    consumer.subscribe([TOPIC], listener=Listener())
                    count = 0
                    target = START + args.count*60_000
                    deadline = time.monotonic()+30
                    while (pipeline.snapshot(stream)['confirmed_next_cursor_ms'] < target
                           and time.monotonic() < deadline):
                        if session.fenced:
                            raise RuntimeError('rebalance fenced consumer; restart/replay required')
                        for records in consumer.poll(timeout_ms=1000).values():
                            for record in records:
                                session.consume_one(record, now_ms=target+5000)
                                count += 1
                    if pipeline.snapshot(stream)['confirmed_next_cursor_ms'] != target:
                        raise RuntimeError(f'incomplete history after {count} deliveries; retention/replay review required')
                    print(f'Reconciled {args.count} contiguous bars across {count} committed deliveries')
                finally:
                    engine.wal.close()
            finally:
                consumer.close()


if __name__ == '__main__':
    main()
