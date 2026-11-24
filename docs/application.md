# Phase 7: analytics API and dashboard

From repository root with the existing virtual environment, stop active Dagster runs and use:
    python -m pip install -r requirements-app.txt
    python -m ecommerce.warehouse
    export WAREHOUSE_PATH="$PWD/data/warehouse.duckdb"
    dbt build --project-dir analytics --profiles-dir analytics
    python -m ecommerce.quality
    python -m ecommerce.serving

Start API:
    python -m uvicorn ecommerce.api:app --host 127.0.0.1 --port 8000
In another activated terminal:
    python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

Swagger: http://localhost:8000/docs. Dashboard: http://localhost:8501. API uses parameterized read-only queries and a separate serving DuckDB file, atomically replaced after quality passes. Dagster publishes it after the quality gate. Manual publication must follow a successful quality run on the same warehouse, with no concurrent writes; the report is not cryptographically bound to the snapshot. Readers open and close connections per request; a refresh can briefly cause different requests to see different snapshot versions. Failed quality runs leave the previous snapshot available. Latest quality status is separate from published quality. No public deployment/authentication; loopback only. Money is integer cents. Sales date/region/category/status filters apply to matching order lines; distinct order counts are not additive across categories. Payment KPIs are all-time and independent event data uses separate dates. No causal conversion rates. CSV uses filtered aggregate values in cents.

Tests: RUN_APP_TESTS=1 python -m unittest discover -s tests -p test_api.py -v. Test fixture is isolated. UI is verified manually.
