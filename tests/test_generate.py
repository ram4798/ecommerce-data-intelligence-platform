import csv
import tempfile
import unittest
from pathlib import Path
from ecommerce.generate import generate_orders, write_orders, FIELDS

class GeneratorTests(unittest.TestCase):
    def test_reproducibility(self):
        self.assertEqual(list(generate_orders(100, 42)), list(generate_orders(100, 42)))

    def test_unique_ids_and_count(self):
        rows = list(generate_orders(1000))
        self.assertEqual(len(rows), 1000)
        self.assertEqual(len({r["order_id"] for r in rows}), 1000)

    def test_money(self):
        for row in generate_orders(100):
            self.assertEqual(row["quantity"] * row["unit_price_cents"], row["total_cents"])
            self.assertGreater(row["total_cents"], 0)
            self.assertEqual(row["currency"], "USD")

    def test_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw" / "orders.csv"
            write_orders(path, 10)
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames), FIELDS)
                self.assertEqual(len(list(reader)), 10)

    def test_negative_count(self):
        with self.assertRaises(ValueError):
            list(generate_orders(-1))

    def test_zero_count(self):
        self.assertEqual(list(generate_orders(0)), [])
