import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

@unittest.skipUnless(os.getenv("RUN_APP_TESTS")=="1","requires application dependencies")
class APITests(unittest.TestCase):
    def test_publish_and_queries(self):
        import duckdb
        import json
        from ecommerce.serving import publish
        from ecommerce.api import app
        from fastapi.testclient import TestClient
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"warehouse.duckdb"
            dst=root/"serving.duckdb"
            report=root/"quality_report.json"
            report.write_text(json.dumps({"success":True,"checks":[]}))
            with duckdb.connect(str(src)) as c:
                c.execute("create schema analytics")
                c.execute("create table analytics.dim_customers as select 1 customer_id,'West' region")
                c.execute("create table analytics.dim_products as select 1 product_id,'home' category")
                c.execute("create table analytics.dim_dates as select date '2025-01-01' date_day")
                c.execute("create table analytics.fct_sales as select 1 order_id,1 customer_id,1 product_id,date '2025-01-01' order_date,'paid' status,2 quantity,1000 line_value_cents,1000 paid_value_cents")
                c.execute("create table analytics.fct_payments as select 1 payment_id,1000 amount_cents")
                c.execute("create table analytics.fct_events as select 'a' event_id,'purchase' event_type,timestamp '2025-01-01' event_time,'s1' session_id")
                c.execute("create table analytics.mart_daily_sales as select 1 orders")
            publish(src,dst,report)
            with patch.dict(os.environ,{"SERVING_PATH":str(dst),"OBSERVABILITY_DIR":tmp}):
                client=TestClient(app)
                self.assertEqual(client.get("/health").status_code,200)
                self.assertEqual(client.get("/api/kpis").json()["gross_cents"],1000)
                self.assertEqual(client.get("/api/kpis",params={"region":"East"}).json()["orders"],0)
                self.assertEqual(client.get("/api/kpis",params={"region":"' OR 1=1 --"}).json()["orders"],0)
                self.assertEqual(client.get("/api/kpis?start=2025-02-01&end=2025-01-01").status_code,422)
                self.assertEqual(client.get("/api/events").json()["summary"]["events"],1)
                self.assertEqual(client.get("/api/payments").json()["amount_cents"],1000)
                self.assertIn("West",client.get("/api/export/sales.csv").text)
                self.assertTrue(client.get("/api/quality").json()["published"]["success"])
                report.write_text('{"success":false}')
                with self.assertRaises(RuntimeError):
                    publish(src,dst,report)
                self.assertEqual(client.get("/api/kpis").json()["orders"],1)
