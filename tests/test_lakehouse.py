import os
import tempfile
import unittest
from ecommerce.lakehouse import path, session, merge, read, batch, kafka_bronze, silver_events, gold_events, parsed_events
from ecommerce.events import event
import json

class LakehouseUnit(unittest.TestCase):
    def test_path(self):
        self.assertTrue(path("data/lakehouse", "bronze", "orders").endswith("/bronze/orders"))

@unittest.skipUnless(os.getenv("RUN_LAKEHOUSE_TESTS") == "1", "requires Java, Spark, Kafka and disposable PostgreSQL")
class LakehouseIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = session()

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def test_pipeline(self):
        from ecommerce.batch import run
        from ecommerce.stream import topics, publish
        run(1, 15)
        topics()
        publish(1, 12, "lakehouse", 0, True)
        with tempfile.TemporaryDirectory() as root:
            batch(self.spark, root)
            self.assertEqual(read(self.spark, root, "silver", "orders").count(), 15)
            self.assertEqual(read(self.spark, root, "gold", "daily_sales").groupBy().sum("orders").first()[0], 15)
            kafka_bronze(self.spark, root)
            silver_events(self.spark, root)
            gold_events(self.spark, root)
            count = read(self.spark, root, "silver", "events").count()
            self.assertGreaterEqual(count, 12)
            self.assertGreaterEqual(read(self.spark, root, "silver", "rejected_events").count(), 1)
            self.assertEqual(read(self.spark, root, "gold", "event_metrics").groupBy().sum("events").first()[0], count)
            bronze_count = read(self.spark, root, "bronze", "events").count()
            kafka_bronze(self.spark, root)
            self.assertEqual(read(self.spark, root, "bronze", "events").count(), bronze_count)
            publish(1, 12, "lakehouse", 0)
            kafka_bronze(self.spark, root)
            silver_events(self.spark, root)
            self.assertEqual(read(self.spark, root, "silver", "events").count(), count)
            df = read(self.spark, root, "silver", "events")
            merge(self.spark, df, path(root, "silver", "events"), "event_id")
            self.assertEqual(read(self.spark, root, "silver", "events").count(), count)
