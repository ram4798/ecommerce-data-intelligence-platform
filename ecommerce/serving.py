"""Publish a small, immutable read-only serving snapshot after quality validation."""
import argparse
import json
import os
import tempfile
from pathlib import Path
from ecommerce.lakehouse import ROOT
from ecommerce.observability import directory, measured

TABLES = ("dim_customers", "dim_products", "dim_dates", "fct_sales", "fct_payments", "fct_events", "mart_daily_sales")
def serving_path():
    return Path(os.getenv("SERVING_PATH", str(ROOT / "data/serving.duckdb"))).resolve()

def publish(source, target, report_path):
    import duckdb
    report = json.loads(Path(report_path).read_text())
    if report.get("success") is not True:
        raise RuntimeError("Cannot publish a failed quality report")
    target = Path(target).resolve()
    if Path(source).resolve() == target:
        raise ValueError("Serving and warehouse paths must differ")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        candidate = Path(temp) / "snapshot.duckdb"
        with duckdb.connect(str(candidate)) as con:
            con.execute("SET threads=2")
            con.execute("SET memory_limit='1GB'")
            escaped = str(Path(source).resolve()).replace("'", "''")
            con.execute(f"ATTACH '{escaped}' AS warehouse (READ_ONLY)")
            con.execute("CREATE SCHEMA analytics")
            for table in TABLES:
                con.execute(f"CREATE TABLE analytics.{table} AS SELECT * FROM warehouse.analytics.{table}")
            con.execute("CREATE TABLE analytics.publication AS SELECT ?::DOUBLE AS published_at, ?::VARCHAR AS quality_report", [__import__("time").time(), json.dumps(report)])
            con.execute("DETACH warehouse")
            con.execute("CHECKPOINT")
        os.replace(candidate, target)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--warehouse", default=os.getenv("WAREHOUSE_PATH", str(ROOT / "data/warehouse.duckdb")))
    p.add_argument("--output", default=str(serving_path()))
    a = p.parse_args()
    with measured("publish_serving"):
        publish(a.warehouse, a.output, directory() / "quality_report.json")

if __name__ == "__main__":
    main()
