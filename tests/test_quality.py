import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ecommerce.observability import measured

class MetricsTests(unittest.TestCase):
    def test_failure_and_recovery(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {"OBSERVABILITY_DIR":root}):
            with self.assertRaises(ValueError):
                with measured("demo"):
                    raise ValueError("simulated")
            p = Path(root)/"metrics/demo.prom"
            self.assertIn('success{stage="demo"} 0', p.read_text())
            with measured("demo"):
                pass
            self.assertIn('success{stage="demo"} 1', p.read_text())
            self.assertEqual(len((Path(root)/"pipeline.jsonl").read_text().splitlines()),2)

@unittest.skipUnless(os.getenv("RUN_ORCHESTRATION_TESTS")=="1", "requires DuckDB")
class QualityTests(unittest.TestCase):
    def test_quality_failure_and_recovery(self):
        import duckdb
        from ecommerce.quality import evaluate
        rules = {"min_orders":1,"min_events":1,"max_snapshot_age_hours":2,"max_volume_change_fraction":0.5}
        with duckdb.connect(":memory:") as c:
            c.execute("create schema raw; create schema analytics")
            c.execute("create table raw.orders as select 1 order_id, 1 customer_id, now() ordered_at, 'paid' status, 100 total_cents")
            c.execute("create table raw.events as select 'a' event_id, now() event_time, 'purchase' event_type, now() ingested_at")
            c.execute("create table analytics.fct_sales as select 1 order_item_id, 1 order_id, 100 line_value_cents")
            c.execute("create table analytics.fct_events as select event_id,event_time from raw.events")
            c.execute("create table analytics.mart_daily_sales as select 1 orders,100 gross_order_value_cents")
            checks, counts = evaluate(c,rules,{},0)
            self.assertTrue(all(x["passed"] for x in checks))
            checks,_ = evaluate(c,rules,{"orders":10},0,True)
            self.assertTrue(any(not x["passed"] and x["severity"]=="warning" for x in checks))
            self.assertTrue(any(x["name"]=="simulated_failure" and not x["passed"] for x in checks))
            checks,_ = evaluate(c,rules,counts,99999)
            self.assertFalse(next(x for x in checks if x["name"]=="snapshot_freshness")["passed"])
            c.execute("alter table raw.orders drop column status")
            checks,_ = evaluate(c,rules,counts,0)
            self.assertFalse(next(x for x in checks if x["name"]=="schema_orders")["passed"])
