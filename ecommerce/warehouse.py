"""Export consistent per-table Delta snapshots to a local dbt input catalog."""
import argparse
import json
import time
from ecommerce.observability import atomic
import os
from pathlib import Path
from ecommerce.lakehouse import ROOT, read, session

SOURCES = {
    "customers": ("bronze", "customers"),
    "products": ("bronze", "products"),
    "order_items": ("bronze", "order_items"),
    "payments": ("bronze", "payments"),
    "orders": ("silver", "orders"),
    "events": ("silver", "events"),
}

def export(spark, lake_root, output):
    import duckdb
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    parquet = output.parent / "warehouse_inputs"
    for name, (layer, table) in SOURCES.items():
        read(spark, lake_root, layer, table).write.mode("overwrite").parquet(str(parquet / name))
    with duckdb.connect(str(output)) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='1GB'")
        con.execute("BEGIN")
        try:
            con.execute("CREATE SCHEMA IF NOT EXISTS raw")
            for name in SOURCES:
                glob = str(parquet / name / "*.parquet")
                con.execute(f"CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM read_parquet(?)", [glob])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
    atomic(output.parent / "warehouse_export.json", json.dumps({"exported_at": time.time()}))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=str(ROOT / "data/lakehouse"))
    p.add_argument("--output", default=os.getenv("WAREHOUSE_PATH", str(ROOT / "data/warehouse.duckdb")))
    args = p.parse_args()
    spark = session()
    try:
        export(spark, args.root, args.output)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
