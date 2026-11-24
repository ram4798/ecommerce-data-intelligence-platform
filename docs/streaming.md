# Phase 3: Kafka streaming

Start PostgreSQL and Kafka with the base and streaming Compose files. Kafka uses one KRaft broker, three source partitions keyed by customer ID and one dead-letter partition. Host clients use localhost:9092. No authentication or TLS is configured: local development only.

    pip install -r requirements-stream.txt
    docker compose -f compose.yaml -f compose.kafka.yaml up -d --wait postgres kafka
    python -m ecommerce.stream topics
    python -m ecommerce.stream produce --count 100 --stream demo --invalid
    python -m ecommerce.stream consume --limit 101
    python -m ecommerce.stream produce --count 100 --stream demo --delay 0
    python -m ecommerce.stream consume --limit 100

On a fresh topic/database expect 100 distinct raw events, one rejected message and 100 accepted replay deliveries. Accepted means processed, not inserted. Replays reuse event IDs but generate new timestamps; the first persisted payload wins. Purchases are simulated independent clickstream events, not reconciled with batch orders. Source offsets are committed synchronously only after SQL persistence or acknowledged DLQ delivery. A crash between those operations can replay a record; the SQL primary key deduplicates valid events, while DLQ messages can repeat (keyed by source coordinates). This is at-least-once delivery, not end-to-end exactly-once. Single broker replication factor one is not highly available. The synchronous per-event producer and psql subprocess sink favor clarity, not throughput. Consumer exits on limit or idle timeout. CI integration tests require a disposable database and fresh Kafka topics.

Stop Kafka without deleting data:
    docker compose -f compose.yaml -f compose.kafka.yaml stop kafka

Do not use down -v on the local project unless you intend to delete both databases and Kafka logs.
