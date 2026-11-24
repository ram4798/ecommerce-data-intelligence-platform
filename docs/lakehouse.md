# Phase 4: local Spark and Delta Lake

Python 3.11, Java 17, Spark 3.5.5 and Delta 3.3.0. On Apple Silicon use native Java and local Spark (two worker threads, 2 GiB driver heap, four shuffle partitions). Maven downloads on the first run require internet. Docker continues hosting PostgreSQL and Kafka; no Spark container or paid Databricks account is required.

    brew install openjdk@17
    export JAVA_HOME="$(brew --prefix openjdk@17)/libexec/openjdk.jdk/Contents/Home"
    export PATH="$JAVA_HOME/bin:$PATH"
    export SPARK_LOCAL_IP=127.0.0.1
    python -m pip install -r requirements-lakehouse.txt
    docker compose -f compose.yaml -f compose.kafka.yaml up -d --wait postgres kafka
    python -m ecommerce.lakehouse batch
    python -m ecommerce.lakehouse stream
    python -m ecommerce.lakehouse report

Batch reads seven PostgreSQL tables via JDBC, overwrites Bronze snapshots, validates and joins orders to customer and item totals in Silver, and rebuilds daily regional sales Gold. Gross includes all statuses; paid value includes paid/shipped, before returns, not recognized revenue. Snapshots are sequential rather than a single cross-table transaction; run while batch writers are idle.

Streaming uses an independent Spark Kafka reader, not the Python consumer group. Available-now triggers drain currently available records then exit; rerun to catch up. Bronze retains source topic/partition/offset, timestamps and payload. Silver parses versioned JSON, validates essential fields, uses a ten-minute event-time watermark with bounded-state ID deduplication and insert-only Delta MERGE for retained history. Events older than the watermark can be dropped from Silver while remaining in Bronze. Quarantine contains schema-invalid records, not late records; Spark validation is not identical to the stricter Python validator. Gold rebuilds five-minute counts and distinct sessions, not a causal purchase conversion metric. Invalid events also reach the Phase 3 DLQ when its separate consumer runs.

All tables/checkpoints live under ignored data/lakehouse. Preserve checkpoints and corresponding Delta tables together; deleting only one can cause replay or data loss. Use a fresh --root for independent demos. Do not run concurrent writers against the same root. No production HA, CDC, or cross-table atomicity. Gold is rebuilt, not incrementally maintained. A completely empty valid stream may not create a Silver table until a nonempty microbatch arrives; publish events first.

Integration test is opt-in in CI on disposable services. Do not run it against your existing local database.
