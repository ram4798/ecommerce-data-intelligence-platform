import os
import unittest
from unittest.mock import patch

class BenchmarkTests(unittest.TestCase):
    def test_percentiles(self):
        from ecommerce.benchmark import summarize
        self.assertEqual(summarize([1,2,3,4,100])["p95_ms"],100)
        self.assertEqual(summarize([]),{"samples":0})
    def test_external_service_not_stopped(self):
        from ecommerce.service_manager import stop
        with patch("ecommerce.service_manager.owned",return_value=None),patch("ecommerce.service_manager.os.killpg") as kill:
            stop("api")
            kill.assert_not_called()

    def test_macos_framework_identity(self):
        from ecommerce.service_manager import identity_matches,ROOT
        stamp="Tue Nov 24 16:48:20 2026     "
        args=" -m uvicorn ecommerce.api:app --host 127.0.0.1 --port 8000"
        original=stamp+str(ROOT/".venv/bin/python")+args
        actual=stamp+"/opt/homebrew/Cellar/python@3.11/3.11.18/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python"+args
        with patch("ecommerce.service_manager.sys.platform","darwin"):
            self.assertTrue(identity_matches("api",original,actual))
            self.assertFalse(identity_matches("api",original,actual.replace("16:48:20","16:48:21")))
            self.assertFalse(identity_matches("api",original,actual.replace("8000","8001")))
            self.assertFalse(identity_matches("dashboard",original,actual))
            self.assertFalse(identity_matches("api",original,actual.replace("/opt/homebrew/","/tmp/")))
        self.assertTrue(identity_matches("api",actual,actual))

@unittest.skipUnless(os.getenv("RUN_APP_TESTS")=="1","requires application dependencies")
class Phase9Tests(unittest.TestCase):
    def test_scale(self):
        from ecommerce.benchmark import scale
        self.assertTrue(scale([100])[0]["validated"])
    def test_currency(self):
        from ecommerce.dashboard_format import assistant_frame
        result={"plan":{"metric":"paid_cents","group":"customer"},"rows":[{"label":68,"value":92990}]}
        frame=assistant_frame(result)
        self.assertAlmostEqual(frame.iloc[0]["Paid order value ($)"],929.9)
        self.assertEqual(result["rows"][0]["value"],92990)
    def test_failed_publication_recovery(self):
        import tempfile,json,duckdb
        from pathlib import Path
        from ecommerce.serving import publish,TABLES
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src,dst,report=(root/"warehouse.duckdb",root/"serving.duckdb",root/"quality.json")
            with duckdb.connect(str(src)) as c:
                c.execute("CREATE SCHEMA analytics")
                for table in TABLES:
                    c.execute(f"CREATE TABLE analytics.{table} AS SELECT 1 AS marker")
            report.write_text(json.dumps({"success":True,"checks":[]}))
            publish(src,dst,report)
            before=dst.read_bytes()
            report.write_text(json.dumps({"success":False}))
            with self.assertRaises(RuntimeError): publish(src,dst,report)
            self.assertEqual(dst.read_bytes(),before)
            with duckdb.connect(str(src)) as c:
                c.execute("DROP TABLE analytics.fct_sales")
            report.write_text(json.dumps({"success":True,"checks":[]}))
            with self.assertRaises(duckdb.Error): publish(src,dst,report)
            self.assertEqual(dst.read_bytes(),before)
            with duckdb.connect(str(src)) as c:
                c.execute("CREATE TABLE analytics.fct_sales AS SELECT 2 AS marker")
            publish(src,dst,report)
            with duckdb.connect(str(dst),read_only=True) as c:
                self.assertEqual(c.execute("SELECT marker FROM analytics.fct_sales").fetchone()[0],2)
