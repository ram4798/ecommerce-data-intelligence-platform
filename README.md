# E-Commerce Data Intelligence Platform

A local-first portfolio project for batch and streaming e-commerce analytics. **Phase 1: synthetic data and reproducible development foundation.** Streaming, lakehouse, dashboards and AI are planned, not implemented.

## Quick start (macOS Apple Silicon / Python 3.11)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m ecommerce.generate --orders 1000 --seed 42 --output data/raw/orders.csv
```

The generator produces deterministic synthetic order records; money is stored in integer USD cents. Output is ignored by Git. No credentials or paid services required.

Optional PostgreSQL foundation:
```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
docker compose down
```
Use a local-only password in .env; never commit it. PostgreSQL is infrastructure only in this phase.

## Roadmap
1. Synthetic data, tests and local infrastructure (this phase).
2. PostgreSQL batch ingestion with idempotency and validation.
3. Kafka and Spark Structured Streaming.
4. Delta Lake layers, dbt models and Dagster orchestration.
5. Analytics and FastAPI.
6. Read-only AI analytics with Ollama and optional OpenAI API.
7. Observability, benchmarks and portfolio demo.

See [architecture notes](docs/architecture.md). This is an independent implementation using synthetic data, not employer data or a completed course fork.
