import os
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.getenv("RUN_APP_TESTS")=="1","requires app dependencies")
class AssistantTests(unittest.TestCase):
    def test_validation_and_sql(self):
        from ecommerce.assistant import Plan,compile_plan
        from pydantic import ValidationError
        for fields in ({"sql":"DROP TABLE x"},{"group":"read_csv"},{"limit":1000},{"operation":"events","region":"West"},{"operation":"payments","start":"2025-01-01"}):
            with self.assertRaises(ValidationError):
                Plan.model_validate({"operation":"sales",**fields})
        p=Plan(operation="sales",region="' OR 1=1 --")
        sql,params=compile_plan(p)
        self.assertNotIn(p.region,sql)
        self.assertEqual(params,[p.region])

    def test_grounded_evaluation(self):
        import duckdb
        from ecommerce.assistant import Plan,answer,context_for,propose
        with duckdb.connect(":memory:") as c:
            c.execute("create schema analytics")
            c.execute("create table analytics.dim_customers as select 1 customer_id,'West' region")
            c.execute("create table analytics.dim_products as select 1 product_id,'home' category")
            c.execute("create table analytics.fct_sales as select 1 order_id,1 customer_id,1 product_id,date '2025-01-01' order_date,'paid' status,2 quantity,1000 line_value_cents,1000 paid_value_cents")
            c.execute("create table analytics.fct_events as select 'purchase' event_type, timestamp '2025-01-01' event_time,'s1' session_id")
            c.execute("create table analytics.fct_payments as select 1000 amount_cents")
            c.execute("create table analytics.publication as select 1.0 published_at, ? quality_report",['{"checks":[{"name":"test","passed":true,"severity":"error"}]}'])
            context=context_for(c)
            cases=[({"operation":"sales","metric":"gross_cents"},1000),({"operation":"sales","status":"cancelled"},0),({"operation":"sales","group":"region","metric":"paid_cents","limit":1},1000),({"operation":"customers","group":"customer","metric":"paid_cents"},1000),({"operation":"events","metric":"events","group":"event_type"},1),({"operation":"payments","metric":"amount_cents"},1000)]
            for fields,expected in cases:
                with self.subTest(fields=fields):
                    self.assertEqual(answer(c,Plan(**fields),context)["rows"][0]["value"],expected)
            self.assertIn("1/1",answer(c,Plan(operation="quality"),context)["answer"])
            self.assertIsNone(answer(c,Plan(operation="unsupported"),context)["sql"])
            with self.assertRaises(ValueError):
                answer(c,Plan(operation="sales",region="unknown"),context)
        with patch.dict(os.environ,{"ENABLE_OPENAI_ASSISTANT":"0"}):
            with self.assertRaises(ValueError):
                propose("sales","openai",{})

    def test_mock_provider(self):
        from ecommerce.assistant import propose
        import httpx
        with patch("ecommerce.assistant.httpx.post") as post:
            post.return_value=httpx.Response(200,request=httpx.Request("POST","http://127.0.0.1:11434"),json={"message":{"content":'{"operation":"sales","metric":"orders"}'}})
            self.assertEqual(propose("how many orders","ollama",{}).metric,"orders")
            self.assertEqual(post.call_args.args[0],"http://127.0.0.1:11434/api/chat")
            post.return_value=httpx.Response(200,request=httpx.Request("POST","http://127.0.0.1:11434"),json={"message":{"content":'{"operation":"sales","sql":"DROP TABLE x"}'}})
            with self.assertRaises(ValueError):
                propose("malicious","ollama",{})

    def test_region_ranking_regression(self):
        import duckdb
        from ecommerce.assistant import Plan, align_plan, answer
        # Reproduce the actual bad plan: model invented US-Central and limit 10.
        bad=Plan(operation="sales",metric="gross_cents",group="region",region="US-Central",limit=10)
        corrected=align_plan("Which region has the highest gross sales?",bad)
        self.assertIsNone(corrected.region)
        self.assertEqual(corrected.limit,1)
        self.assertTrue(corrected.descending)
        with duckdb.connect(":memory:") as c:
            c.execute("create schema analytics")
            c.execute("create table analytics.dim_customers as select * from (values (1,'US-East'),(2,'US-Central'),(3,'US-West')) t(customer_id,region)")
            c.execute("create table analytics.dim_products as select 1 product_id")
            c.execute("create table analytics.fct_sales as select * from (values (1,1,3071966),(2,1,2998639),(3,1,2545513)) t(customer_id,product_id,line_value_cents)")
            c.execute("create table analytics.publication as select 1.0 published_at, '{}' quality_report")
            ctx={"regions":["US-East","US-Central","US-West"],"categories":[]}
            self.assertEqual(answer(c,corrected,ctx)["rows"],[{"label":"US-East","value":3071966}])
            lowest=align_plan("Which region has the lowest gross sales?",bad)
            self.assertEqual(answer(c,lowest,ctx)["rows"],[{"label":"US-West","value":2545513}])
        self.assertEqual(align_plan("What is gross sales in US-Central?",bad).region,"US-Central")
        with self.assertRaises(ValueError):
            align_plan("What is the total gross order value?",bad)
        with self.assertRaises(ValueError):
            align_plan("How many orders?",Plan(operation="sales",start="2025-01-01"))
        with self.assertRaises(ValueError):
            align_plan("Top 5 customers by paid value",Plan(operation="customers",group="customer",metric="paid_cents",limit=10))
        with self.assertRaises(ValueError):
            align_plan("How many orders?",Plan(operation="sales",status="paid"))
        self.assertEqual(align_plan("How many canceled orders?",Plan(operation="sales",status="cancelled")).status,"cancelled")

    def test_ranking_mock_provider_regression(self):
        import httpx
        from ecommerce.assistant import propose
        with patch("ecommerce.assistant.httpx.post") as post:
            post.return_value=httpx.Response(200,request=httpx.Request("POST","http://127.0.0.1:11434"),json={"message":{"content":'{"operation":"sales","metric":"gross_cents","group":"region","region":"US-Central","limit":10}'}})
            plan=propose("Which region has the highest gross sales?","ollama",{})
            self.assertEqual((plan.region,plan.limit,plan.descending),(None,1,True))
