import unittest
from ecommerce.relational import generate_batch, validate
from ecommerce.batch import load_sql

class RelationalTests(unittest.TestCase):
    def test_valid(self):
        data = generate_batch(1, 1000)
        validate(data)
        self.assertEqual(len(data["orders"]), 1000)

    def test_overlap(self):
        a, b = generate_batch(1, 10), generate_batch(6, 10)
        self.assertEqual(a["orders"][5:], b["orders"][:5])

    def test_duplicate(self):
        data = generate_batch(1, 10)
        data["orders"].append(data["orders"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(data)

    def test_orphan(self):
        data = generate_batch(1, 10)
        data["customers"] = []
        with self.assertRaises(ValueError):
            validate(data)

    def test_total(self):
        data = generate_batch(1, 10)
        row = data["orders"][0]
        data["orders"][0] = (*row[:-1], row[-1] + 1)
        with self.assertRaisesRegex(ValueError, "total mismatch"):
            validate(data)

    def test_empty(self):
        validate(generate_batch(1, 0))

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            generate_batch(0, 1)

    def test_transaction_sql(self):
        sql = load_sql(generate_batch(1, 2), 1)
        self.assertTrue(sql.startswith("BEGIN;"))
        self.assertTrue(sql.endswith("COMMIT;"))
        self.assertIn("ON CONFLICT", sql)
