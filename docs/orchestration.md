# Phase 5: dbt and Dagster

Install requirements-orchestration.txt in the existing Python 3.11 virtual environment. Keep Java 17, PostgreSQL and Kafka available. Spark exports six Delta snapshots via Parquet into DuckDB raw tables in one DuckDB transaction. This avoids an extra database server and lets dbt work with logical snapshots rather than reading obsolete Delta parquet files. Export assumes no concurrent Delta writers. DuckDB uses two threads and a 1 GB memory limit; Spark jobs execute sequentially. No paid services.

From the repository root:

    python -m pip install -r requirements-orchestration.txt
    export WAREHOUSE_PATH="$PWD/data/warehouse.duckdb"
    python -m ecommerce.warehouse
    dbt build --project-dir analytics --profiles-dir analytics
    dbt docs generate --project-dir analytics --profiles-dir analytics
    mkdir -p data/dagster
    export DAGSTER_HOME="$PWD/data/dagster"
    dagster dev -m ecommerce.orchestration -h 127.0.0.1 -p 3000

Open http://127.0.0.1:3000. Launch refresh_analytics from Jobs. The hourly UTC schedule is defined but not enabled by default; enable it in UI only when desired. Keep the daemon running for schedules. Avoid overlapping refresh runs and manual dbt writes; DuckDB is a single-writer local database. Dagster assets track pipeline stages, while individual dbt model lineage is in dbt docs (not individual Dagster assets). The refresh consumes existing source data; it does not generate new orders/events. Existing synthetic records are immutable: incremental facts insert unseen IDs, not corrections/deletes; use dbt build --full-refresh for corrections. Gold sales is rebuilt; paid value is before returns. dbt tests stop the orchestration job on failure. No production scheduler or notifications yet.

The integration test builds and reruns dbt against an isolated DuckDB fixture. It validates the Dagster definitions; full UI/scheduled execution is a local verification step.
