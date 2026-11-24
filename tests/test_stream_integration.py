import os
import unittest
from ecommerce.batch import psql
from ecommerce.stream import topics, publish, consume, DLQ, BOOTSTRAP

@unittest.skipUnless(os.getenv("RUN_STREAM_TESTS") == "1", "requires disposable Kafka and PostgreSQL")
class StreamIntegration(unittest.TestCase):
    def test_replay_and_dlq(self):
        from confluent_kafka import Consumer
        topics()
        publish(1, 12, "ci", 0, True)
        self.assertEqual(consume("ci-raw", 13, 45), {"accepted": 12, "rejected": 1})
        publish(1, 12, "ci", 0)
        self.assertEqual(consume("ci-raw", 12, 45), {"accepted": 12, "rejected": 0})
        self.assertEqual(psql("SELECT count(*) FROM ecommerce.raw_events;"), "12")
        client = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": "ci-dlq", "auto.offset.reset": "earliest", "enable.auto.commit": False})
        try:
            client.subscribe([DLQ])
            msg = client.poll(30)
            self.assertIsNotNone(msg)
            self.assertIsNone(msg.error())
            self.assertIn(b"payload_base64", msg.value())
        finally:
            client.close()
