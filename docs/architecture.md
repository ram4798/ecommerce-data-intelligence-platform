# Architecture

## Implemented in Phase 1
Deterministic Python order generator -> CSV raw data -> unit tests. Optional local PostgreSQL container with persistent storage and health check.

## Target architecture (planned)
Batch sources -> scheduled ingestion -> Bronze Delta tables.
Simulated clickstream -> Kafka -> Spark Structured Streaming -> Bronze.
Bronze -> Silver (schema checks, deduplication, quarantine) -> Gold (facts and dimensions).
Gold -> analytics API and dashboard -> optional read-only LLM query assistant.

Dagster will orchestrate batch jobs; dbt will model business metrics using a compatible SQL adapter chosen during integration. Streaming will use checkpoints and event-time processing. All generated records are synthetic.

Local development targets a 16 GB Apple Silicon Mac. Start services incrementally. No cloud account or paid AI provider is required. OpenAI usage, if enabled later, may incur charges.
