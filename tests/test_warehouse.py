import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

@unittest.skipUnless(os.getenv("RUN_ORCHESTRATION_TESTS") == "1", "requires dbt and Dagster")
class OrchestrationTests(unittest.TestCase):
    def test_asset_graph(self):
        from ecommerce.orchestration import defs
        from dagster import Definitions
        Definitions.validate_loadable(defs)

    def test_dbt_incremental(self):
        import duckdb
        from ecommerce.orchestration import dbt
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "test.duckdb")
            with duckdb.connect(path) as c:
                c.execute("create schema raw")
                c.execute("create table raw.customers as select 1 customer_id, 'West' region")
                c.execute("create table raw.products as select 1 product_id, 'home' category, 500 unit_price_cents")
                c.execute("create table raw.orders as select 1 order_id, 1 customer_id, timestamp '2025-01-01' ordered_at, 'paid' status, 1000 total_cents")
                c.execute("create table raw.order_items as select 11 order_item_id, 1 order_id, 1 product_id, 2 quantity, 500 unit_price_cents")
                c.execute("create table raw.payments as select 1 payment_id, 1 order_id, 1000 amount_cents")
                c.execute("create table raw.events as select 'e1' event_id, 'purchase' event_type, timestamp '2025-01-01' event_time, 1 customer_id, 1 product_id, 's1' session_id")
            with patch.dict(os.environ, {"WAREHOUSE_PATH": path}):
                dbt("build")
                with duckdb.connect(path) as c:
                    c.execute("insert into raw.events select 'e2', 'page_view', timestamp '2025-01-01', 1, 1, 's1'")
                dbt("build")
                with duckdb.connect(path) as c:
                    self.assertEqual(c.execute("select count(*) from analytics.fct_events").fetchone()[0], 2)
                    self.assertEqual(c.execute("select sum(gross_order_value_cents) from analytics.mart_daily_sales").fetchone()[0], 1000)
