# Phase 9: operations and performance

## One terminal

From repository root with .venv active, use `python -m ecommerce.service_manager status all`. The manager starts detached local services with logs under data/services, records PID and process identity, and refuses to kill external/manual listeners. Use commands sequentially, not concurrently. If port occupied by a manual service, stop it in its original terminal first. No PID adoption. No force kill.

    python -m ecommerce.service_manager start app
    python -m ecommerce.service_manager status all
    python -m ecommerce.service_manager stop app
    python -m ecommerce.service_manager start infra
    python -m ecommerce.service_manager start dagster

app = Ollama, FastAPI, Streamlit. infra = five Compose containers. all = app + infra + Dagster. Stop infra uses compose stop, never down -v. Initial setup and valid serving snapshot must already exist. Startup is not transactional; inspect logs if a service fails. Restart only managed local services; manual listeners are untouched. To check logs: tail -n 50 data/services/api.log. Avoid starting two managers simultaneously.

## Benchmarks

    python -m ecommerce.benchmark http --requests 20 --workers 2 --ai 3
    python -m ecommerce.benchmark pipeline
    python -m ecommerce.benchmark scale --sizes 1500 10000 50000

Reports saved as JSON in ignored data/benchmarks. HTTP reports successful latency mean/p50/p95/max, throughput including failures in elapsed time, counts and errors. One warm-up per HTTP endpoint excluded; AI runs serially, includes model startup and no warm-up. Compare actual accuracy against current KPI snapshot, do not refresh during measurement. AI rule and LLM paths distinguished. Pipeline history aggregates recorded stage attempts (not end-to-end run latency; retries included). Read Dagster run duration separately. Scale generates/validates real synthetic relational batches and bulk loads just orders into temporary DuckDB, checks counts and sum, reports times and file size. It does NOT measure full PostgreSQL/Kafka/Spark scalability. No writes to existing serving or warehouse. Maximum 100000 orders per isolated case; 50000 recommended first. Stop app before scale if memory pressure high.

## 8 GB Mac operating profiles

Analytics: use existing serving snapshot, app only; Dagster/Spark not required. Infra may be stopped if no run active; keep volumes. Refresh: stop app (including Ollama), start infra and Dagster, run refresh_analytics in UI, then stop Dagster and start app. Spark defaults local[2], 2g driver, four shuffle partitions; environment overrides SPARK_MASTER, SPARK_DRIVER_MEMORY, SPARK_SHUFFLE_PARTITIONS before starting Dagster. DuckDB API 1GB per connection configuration, two threads, not a process-wide RAM guarantee. Kafka heap 512MB. Local Qwen 3B, one request at a time, 4096 context and unload per request. Check Activity Monitor memory pressure and swap; do not benchmark concurrent Spark/LLM on this machine.

## Failure recovery

    RUN_APP_TESTS=1 python -m unittest discover -s tests -p test_phase9.py -v

Isolated temporary-file test rejects failed quality, simulates missing source table during publication, verifies old snapshot byte-for-byte and successful subsequent publication. Existing CI covers transactional ingestion rollback and replay, Kafka DLQ/dedup, Spark and dbt integration. No destructive tests against local retained PostgreSQL. For manual service recovery, stop app, verify stopped, start app and check /health and KPI totals. Do not stop an active pipeline.

## Observed baseline (Nov 24, 2026)

User verified 1500 orders, 3026 order lines, 100 unique events, 17 quality checks, 7-asset Dagster run 98 seconds, publication 135 ms. Standalone Ollama generation 36.51 tokens/s and model startup 4.89 s (not API latency). Local Phase 8 tests 6/6; 12 business scenarios eventually passed after fixes, 4 security requests rejected. New benchmark results pending; no claimed speedup or production SLA.
