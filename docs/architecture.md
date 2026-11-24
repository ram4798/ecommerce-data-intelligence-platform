# Architecture

Implemented: synthetic CSV and relational generator -> PostgreSQL batch loader; simulated clickstream -> Kafka -> Python consumer -> PostgreSQL raw events / DLQ. Independent Spark Structured Streaming reads Kafka into Bronze Delta with checkpoints, validates and deduplicates into Silver using watermark and MERGE, then rebuilds Gold event windows. PostgreSQL JDBC snapshots feed Bronze, reconciled orders in Silver, daily regional sales in Gold.

Planned: Dagster orchestration, dbt transformations, monitoring, FastAPI, dashboards and optional read-only LLM assistant. All data is synthetic. Local development targets a 16 GB Apple Silicon Mac; no paid cloud account required.
