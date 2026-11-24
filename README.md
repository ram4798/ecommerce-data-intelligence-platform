# E-Commerce Data Intelligence Platform

Local-first portfolio project using synthetic data. Phases 1–4 implement the local foundation, relational batch loader, Kafka streaming and Spark/Delta lakehouse. Phase 5 adds DuckDB-backed dbt marts and Dagster orchestration; Phase 6 adds observability and Phase 7 adds a read-only API and dashboard; AI remains planned.

## Run locally (Python 3.11, Docker Compose)
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m unittest discover -s tests -v
# First setup only: cp .env.example .env
docker compose up -d --wait postgres
python -m ecommerce.batch --start 1 --count 1000
python -m ecommerce.batch --start 1 --count 1000
python -m ecommerce.batch --start 1001 --count 500
docker compose exec postgres psql -U ecommerce -d ecommerce -c "SELECT count(*) FROM ecommerce.orders;"
docker compose exec postgres psql -U ecommerce -d ecommerce -c "SELECT run_id,status,row_counts FROM ecommerce.ingestion_runs ORDER BY run_id;"
```
Expected order count on an initially empty database: 1500. The loader uses deterministic IDs, insert-on-conflict-ignore semantics, validation and a transaction. Audit counts represent submitted rows, not newly inserted rows. Failed runs are recorded separately when the database is reachable. Interrupted runs may remain running. Inventory is a static synthetic snapshot, not a stock ledger. One payment per paid/shipped order and at most one return per item. All money is USD cents.

Phase 1 CSV remains available: `python -m ecommerce.generate --orders 1000`.

Integration tests run in CI using a disposable PostgreSQL container. **Do not set RUN_DB_TESTS=1 against a database you want to retain**: the integration test drops the ecommerce schema. Local credentials stay in ignored .env. No paid services required.

## Roadmap
1. Synthetic orders and local infrastructure.
2. Relational schema and incremental batch ingestion.
3. Kafka and Spark Structured Streaming.
4. Delta Lake layers, dbt and Dagster.
5. APIs and dashboards.
6. Read-only AI assistant (Ollama / optional OpenAI).
7. Observability, benchmarks and portfolio demo.

See [architecture notes](docs/architecture.md) and [batch design](docs/batch.md). Independent synthetic-data implementation; no employer data.

## Kafka streaming

See [Phase 3 streaming setup and replay demo](docs/streaming.md). Install the pinned streaming dependency and start Kafka using the additional Compose file. Existing batch commands remain unchanged.

## Spark and Delta Lake

See [Phase 4 lakehouse setup](docs/lakehouse.md) for Java 17, pinned Spark dependencies, JDBC batch, checkpointed Kafka streaming and Gold metrics.

## dbt and Dagster

See [Phase 5 orchestration guide](docs/orchestration.md) for snapshot export, dbt models and the local Dagster UI.

## Data quality and monitoring

See [Phase 6 monitoring guide](docs/monitoring.md) for quality gate, structured stage metrics, Prometheus alerts, Grafana and controlled failure recovery.

## Analytics application

See [Phase 7 application guide](docs/application.md) for FastAPI, Streamlit and serving snapshots.
