"""Read-only warehouse checks with persistent reports and safe failure simulation."""
import argparse
import json
import os
import time
from pathlib import Path
from ecommerce.lakehouse import ROOT
from ecommerce.observability import directory, atomic, measured

REQUIRED = {
    "raw.orders": {"order_id", "customer_id", "ordered_at", "status", "total_cents"},
    "raw.events": {"event_id", "event_time", "event_type", "ingested_at"},
    "analytics.fct_sales": {"order_item_id", "order_id", "line_value_cents"},
    "analytics.fct_events": {"event_id", "event_time"},
    "analytics.mart_daily_sales": {"orders", "gross_order_value_cents"},
}

def evaluate(con, rules, previous, snapshot_age, simulate=False):
    checks = []
    counts = {}
    def check(name, passed, detail, severity="error"):
        checks.append({"name": name, "passed": bool(passed), "detail": detail, "severity": severity})
    for table, expected in REQUIRED.items():
        schema, name = table.split(".")
        actual = {r[0] for r in con.execute("select column_name from information_schema.columns where table_schema=? and table_name=?", [schema, name]).fetchall()}
        check("schema_" + name, expected <= actual, "missing: " + ",".join(sorted(expected - actual)))
    if all(c["passed"] for c in checks):
        def scalar(sql):
            return con.execute(sql).fetchone()[0]
        counts["orders"] = scalar("select count(*) from raw.orders")
        counts["events"] = scalar("select count(*) from raw.events")
        counts["sales_lines"] = scalar("select count(*) from analytics.fct_sales")
        check("orders_minimum", counts["orders"] >= rules["min_orders"], counts["orders"])
        check("events_minimum", counts["events"] >= rules["min_events"], counts["events"])
        check("order_nulls", scalar("select count(*) from raw.orders where order_id is null or customer_id is null or ordered_at is null or total_cents is null or status is null")==0, "required fields")
        check("event_nulls", scalar("select count(*) from raw.events where event_id is null or event_time is null or event_type is null")==0, "required fields")
        check("event_duplicates", scalar("select count(*)-count(distinct event_id) from analytics.fct_events")==0, "unique event IDs")
        check("event_completeness", scalar("select count(*) from (select event_id from raw.events except select event_id from analytics.fct_events)")==0 and scalar("select count(*) from analytics.fct_events")==counts["events"], "raw vs fact")
        check("order_completeness", scalar("select coalesce(sum(orders),0) from analytics.mart_daily_sales")==counts["orders"], "raw vs mart")
        check("sales_reconciliation", scalar("select coalesce(sum(total_cents),0) from raw.orders")==scalar("select coalesce(sum(line_value_cents),0) from analytics.fct_sales"), "integer cents")
        for name, count in counts.items():
            old = previous.get(name)
            if old is not None and old > 0:
                change = abs(count-old)/old
                check("volume_"+name, change <= rules["max_volume_change_fraction"], round(change,4), "warning")
    check("snapshot_freshness", 0 <= snapshot_age <= rules["max_snapshot_age_hours"]*3600, round(snapshot_age,2))
    if simulate:
        check("simulated_failure", False, "intentional test; no business data changed")
    return checks, counts

def run(warehouse, rules_path, simulate=False):
    import duckdb
    root = directory()
    baseline = root / "baseline.json"
    previous = json.loads(baseline.read_text()) if baseline.exists() else {}
    rules = json.loads(Path(rules_path).read_text())
    warehouse = Path(warehouse)
    marker = warehouse.parent / "warehouse_export.json"
    age = time.time() - json.loads(marker.read_text())["exported_at"] if marker.exists() else 1e12
    with measured("quality_gate"):
        with duckdb.connect(str(warehouse), read_only=True) as con:
            checks, counts = evaluate(con, rules, previous, age, simulate)
        success = all(c["passed"] or c["severity"]=="warning" for c in checks)
        report = {"timestamp": time.time(), "success": success, "checks": checks, "counts": counts}
        atomic(root / "quality_report.json", json.dumps(report, indent=2))
        lines = [f"ecommerce_quality_success {int(success)}", f"ecommerce_snapshot_age_seconds {age:.3f}"]
        for c in checks:
            lines.append(f'ecommerce_quality_check_success{{check="{c["name"]}",severity="{c["severity"]}"}} {int(c["passed"])}')
        for name, count in counts.items():
            lines.append(f'ecommerce_dataset_rows{{dataset="{name}"}} {count}')
        atomic(root / "metrics" / "quality.prom", "\n".join(lines)+"\n")
        print(json.dumps(report, indent=2))
        if not success:
            raise RuntimeError("quality gate failed")
        if not any(not c["passed"] for c in checks):
            atomic(baseline, json.dumps(counts))
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--warehouse", default=os.getenv("WAREHOUSE_PATH", str(ROOT / "data/warehouse.duckdb")))
    p.add_argument("--rules", default=str(ROOT / "config/quality.json"))
    p.add_argument("--simulate-failure", action="store_true")
    a = p.parse_args()
    run(a.warehouse, a.rules, a.simulate_failure)

if __name__ == "__main__":
    main()
