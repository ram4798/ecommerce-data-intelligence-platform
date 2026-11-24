# E-Commerce Data Intelligence Platform

Local-first, reproducible data engineering and AI analytics portfolio using synthetic commerce data. Built with Python, PostgreSQL, Kafka, PySpark, Delta Lake, dbt, DuckDB, Dagster, Prometheus, Grafana, FastAPI, Streamlit and Ollama.

## Architecture

```mermaid
flowchart LR
  A[Synthetic orders] --> P[(PostgreSQL)]
  B[Clickstream] --> K[Kafka]
  P --> L[Delta Lake]
  K --> L
  L --> W[dbt / DuckDB]
  W --> Q[Quality gate]
  Q --> S[(Serving snapshot)]
  S --> F[FastAPI]
  F --> U[Streamlit]
  F --> AI[Guarded AI planner]
  AI --> F
  D[Dagster] -.-> L
  D -.-> W
  Q --> M[Prometheus / Grafana]
```

[Detailed architecture and limitations](docs/architecture.md).

## What it demonstrates

- Transactional and replay-safe relational ingestion; Kafka manual offset commit and dead-letter handling.
- Independent Spark batch and available-now streaming, Delta Bronze/Silver/Gold, watermark deduplication.
- dbt dimensions, facts, marts and tests; seven-asset Dagster orchestration.
- Quality gates, metrics, alert rules and last-good atomic serving snapshot.
- Read-only REST API and interactive sales, customer, events, quality and AI dashboard.
- Local LLM structured plans and deterministic intent rules, allowlisted parameterized SQL, evidence.
- Service lifecycle commands, reproducible benchmarks and isolated failure-recovery tests.

## Setup and demo

Prerequisites: Python 3.11, Java 17, Docker Desktop with Compose, Ollama for AI. Tested locally on Apple M2 with 8 GB RAM; no paid cloud required. Optional OpenAI incurs API fees.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-stream.txt -r requirements-lakehouse.txt -r requirements-orchestration.txt -r requirements-app.txt
cp .env.example .env  # first setup only; configure local password
python -m ecommerce.service_manager start infra
python -m ecommerce.batch --start 1 --count 1000
python -m ecommerce.batch --start 1001 --count 500
```

Follow [streaming setup](docs/streaming.md) to create topics and populate events, then [lakehouse](docs/lakehouse.md) and [orchestration](docs/orchestration.md) to refresh the seven assets and publish a snapshot. Start Ollama temporarily to download `qwen2.5:3b` (see assistant guide), then stop the manual server before using the manager.

```bash
python -m ecommerce.service_manager start app
python -m ecommerce.service_manager status all
```

Dashboard: http://127.0.0.1:8501 · API: http://127.0.0.1:8000/docs · Dagster: http://127.0.0.1:3000 (start separately) · Grafana: http://127.0.0.1:3001 · Prometheus: http://127.0.0.1:9090.

Try "How many total orders do we have?" or "Who are the top 5 customers by paid value?" Inspect query evidence. To stop managed app services without deleting data: `python -m ecommerce.service_manager stop app`.

## Verified local baseline

1500 orders, 3026 order lines, 100 customers, 100 events, 17 quality checks passed, seven-asset refresh 98 s (Nov 24, 2026). Phase 8 local automated tests 6/6. These are observed demo results, not production-scale claims. New Phase 9 benchmarks must be run on target hardware.

## Documentation

| Topic | Guide |
|---|---|
| Architecture / data contracts | [Architecture](docs/architecture.md) |
| Batch generation / ingestion | [Batch](docs/batch.md) |
| Kafka and replay | [Streaming](docs/streaming.md) |
| Spark / Delta | [Lakehouse](docs/lakehouse.md) |
| dbt / Dagster | [Orchestration](docs/orchestration.md) |
| Quality / alerts | [Monitoring](docs/monitoring.md) |
| REST / dashboard | [Application](docs/application.md) |
| AI / evaluation | [Assistant](docs/assistant.md) |
| Operations / benchmarking / recovery | [Performance](docs/performance.md) |

## Tests and constraints

`python -m unittest discover -s tests -v` runs dependency-light tests; opt-in integration suites run in GitHub Actions. **Never set RUN_DB_TESTS=1 against retained data:** that suite drops its test schema. Use disposable infrastructure. Local .env, generated data, logs and model weights are not committed. No authentication, distributed HA or production SLA; no real customer data. Inventory is a static snapshot, returns are not subtracted from paid value, clickstream is independent of batch orders. Model intent is not guaranteed correct; evidence is inspectable. See architecture for boundaries.
