import os
import unittest
from unittest.mock import patch
from ecommerce.batch import psql, run, load_sql
from ecommerce.relational import generate_batch

@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requires dedicated test PostgreSQL")
class DatabaseTests(unittest.TestCase):
    def test_incremental_and_failure(self):
        # Use a fresh disposable CI database only.
        psql("DROP SCHEMA IF EXISTS ecommerce CASCADE;")
        run(1, 10)
        run(1, 10)
        run(6, 10)
        self.assertEqual(psql("SELECT count(*) FROM ecommerce.orders;"), "15")
        self.assertEqual(psql("SELECT count(*) FROM ecommerce.ingestion_runs WHERE status='success';"), "3")
        with patch("ecommerce.batch.validate", side_effect=ValueError("injected validation failure")):
            with self.assertRaises(ValueError):
                run(16, 5)
        self.assertEqual(psql("SELECT count(*) FROM ecommerce.orders;"), "15")
        self.assertEqual(psql("SELECT count(*) FROM ecommerce.ingestion_runs WHERE status='failed';"), "1")
