"""Kafka topic setup, event producer and at-least-once consumer."""
import argparse
import base64
import json
import os
import time
from pathlib import Path
from ecommerce.events import event, decode
from ecommerce.batch import psql, literal

TOPIC = "ecommerce.events.v1"
DLQ = "ecommerce.events.dlq.v1"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

def topics():
    from confluent_kafka.admin import AdminClient, NewTopic
    from confluent_kafka import KafkaException, KafkaError
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    futures = admin.create_topics([NewTopic(TOPIC, 3, 1), NewTopic(DLQ, 1, 1)], operation_timeout=20, request_timeout=30)
    for future in futures.values():
        try:
            future.result()
        except KafkaException as exc:
            if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise
    metadata = admin.list_topics(timeout=15)
    for name, partitions in ((TOPIC, 3), (DLQ, 1)):
        if name not in metadata.topics or len(metadata.topics[name].partitions) != partitions:
            raise RuntimeError(f"unexpected partition count: {name}")

def producer():
    from confluent_kafka import Producer
    return Producer({"bootstrap.servers": BOOTSTRAP, "enable.idempotence": True, "acks": "all", "delivery.timeout.ms": 30000})

def send(client, topic, key, value):
    errors = []
    def delivered(err, msg):
        if err:
            errors.append(str(err))
    client.produce(topic, key=key, value=value, on_delivery=delivered)
    if client.flush(35) or errors:
        raise RuntimeError(f"Kafka delivery failed: {errors}")

def publish(start, count, stream, delay, invalid=False):
    client = producer()
    for sequence in range(start, start + count):
        data = event(sequence, stream)
        send(client, TOPIC, str(data["customer_id"]), json.dumps(data))
        if delay:
            time.sleep(delay)
    if invalid:
        send(client, TOPIC, "invalid", b'{"bad":true}')
    print(f"Published {count + int(invalid)} records")

def insert_sql(data, topic, partition, offset):
    columns = ("event_id", "event_type", "event_time", "customer_id", "product_id", "session_id")
    values = [data[k] for k in columns] + [json.dumps(data), topic, partition, offset]
    return ("SET standard_conforming_strings=on; INSERT INTO ecommerce.raw_events "
            "(event_id,event_type,event_time,customer_id,product_id,session_id,payload,kafka_topic,kafka_partition,kafka_offset) VALUES ("
            + ",".join(map(literal, values)) + ") ON CONFLICT (event_id) DO NOTHING;")

def handle(msg, dead_producer):
    try:
        data = decode(msg.value())
    except ValueError as exc:
        envelope = {"source_topic": msg.topic(), "partition": msg.partition(), "offset": msg.offset(),
                    "reason": str(exc), "payload_base64": base64.b64encode(msg.value() or b"").decode("ascii")}
        send(dead_producer, DLQ, f"{msg.topic()}:{msg.partition()}:{msg.offset()}", json.dumps(envelope))
        return "rejected"
    psql(insert_sql(data, msg.topic(), msg.partition(), msg.offset()))
    return "accepted"

def consume(group, limit, idle_seconds):
    from confluent_kafka import Consumer, KafkaException
    psql((Path(__file__).resolve().parents[1] / "sql/stream.sql").read_text())
    client = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": group, "auto.offset.reset": "earliest",
                       "enable.auto.commit": False, "enable.auto.offset.store": False})
    dead = producer()
    counts = {"accepted": 0, "rejected": 0}
    deadline = time.monotonic() + idle_seconds
    client.subscribe([TOPIC])
    try:
        while sum(counts.values()) < limit and time.monotonic() < deadline:
            msg = client.poll(1)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            outcome = handle(msg, dead)
            offsets = client.commit(message=msg, asynchronous=False)
            if not offsets or any(p.error is not None for p in offsets):
                raise RuntimeError(f"Offset commit failed: {offsets}")
            counts[outcome] += 1
            deadline = time.monotonic() + idle_seconds
    finally:
        client.close()
    print(json.dumps(counts))
    return counts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("topics")
    pub = sub.add_parser("produce")
    pub.add_argument("--start", type=int, default=1)
    pub.add_argument("--count", type=int, default=100)
    pub.add_argument("--stream", default="demo")
    pub.add_argument("--delay", type=float, default=0.05)
    pub.add_argument("--invalid", action="store_true")
    con = sub.add_parser("consume")
    con.add_argument("--group", default="ecommerce-raw-v1")
    con.add_argument("--limit", type=int, default=100)
    con.add_argument("--idle-seconds", type=float, default=30)
    args = parser.parse_args()
    if args.command == "topics":
        topics()
    elif args.command == "produce":
        if args.start < 1 or args.count < 0 or args.delay < 0 or not args.stream:
            parser.error("invalid producer arguments")
        publish(args.start, args.count, args.stream, args.delay, args.invalid)
    else:
        if args.limit < 1 or args.idle_seconds <= 0:
            parser.error("invalid consumer arguments")
        consume(args.group, args.limit, args.idle_seconds)

if __name__ == "__main__":
    main()
