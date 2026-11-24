import json
import unittest
from unittest.mock import Mock, patch
from ecommerce.events import event, decode
from ecommerce.stream import handle, DLQ

class EventTests(unittest.TestCase):
    def test_roundtrip(self):
        data = event(1, "test")
        self.assertEqual(decode(json.dumps(data)), data)

    def test_stable_identity(self):
        self.assertEqual(event(1, "test")["event_id"], event(1, "test")["event_id"])
        self.assertNotEqual(event(1, "test")["event_id"], event(2, "test")["event_id"])

    def test_bad_json(self):
        for raw in (b"bad", b"null", None, b"[]"):
            with self.assertRaises(ValueError):
                decode(raw)

    def test_invalid_id(self):
        data = event(1, "test")
        data["customer_id"] = True
        with self.assertRaises(ValueError):
            decode(json.dumps(data))

    def test_invalid_version(self):
        data = event(1, "test")
        data["schema_version"] = 2
        with self.assertRaises(ValueError):
            decode(json.dumps(data))

    @patch("ecommerce.stream.send")
    def test_dead_letter(self, send):
        msg = Mock()
        msg.value.return_value = b"bad"
        msg.topic.return_value = "source"
        msg.partition.return_value = 0
        msg.offset.return_value = 2
        self.assertEqual(handle(msg, Mock()), "rejected")
        self.assertEqual(send.call_args.args[1], DLQ)

    @patch("ecommerce.stream.psql", side_effect=RuntimeError("database unavailable"))
    def test_sink_failure_propagates(self, sink):
        msg = Mock()
        msg.value.return_value = json.dumps(event(1, "test")).encode()
        msg.topic.return_value = "source"
        msg.partition.return_value = 0
        msg.offset.return_value = 2
        with self.assertRaises(RuntimeError):
            handle(msg, Mock())
