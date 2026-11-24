"""Load synthetic relational batches transactionally into local PostgreSQL via psql."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from ecommerce.relational import TABLES, generate_batch, validate

ROOT = Path(__file__).resolve().parents[1]

def psql(sql):
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c",
         'exec psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'],
        input=sql, text=True, capture_output=True, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "psql failed")
    return result.stdout.strip()

def literal(value):
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"

def load_sql(data, run_id):
    statements = ["BEGIN;", "SET LOCAL standard_conforming_strings = on;"]
    for table, columns in TABLES.items():
        rows = data[table]
        for offset in range(0, len(rows), 500):
            values = ",".join("(" + ",".join(map(literal, row)) + ")" for row in rows[offset:offset+500])
            statements.append(f"INSERT INTO ecommerce.{table} ({','.join(columns)}) VALUES {values} ON CONFLICT ({columns[0]}) DO NOTHING;")
    counts = json.dumps({table: len(rows) for table, rows in data.items()})
    statements.append(f"UPDATE ecommerce.ingestion_runs SET status='success', finished_at=clock_timestamp(), row_counts={literal(counts)}::jsonb WHERE run_id={int(run_id)};")
    return "\n".join(statements + ["COMMIT;"])

def run(start, count):
    if start < 1 or count < 0:
        raise ValueError("invalid batch range")
    psql((ROOT / "sql/schema.sql").read_text())
    run_id = int(psql(f"INSERT INTO ecommerce.ingestion_runs(start_id,requested_orders,status) VALUES ({start},{count},'running') RETURNING run_id;"))
    try:
        data = generate_batch(start, count)
        validate(data)
        psql(load_sql(data, run_id))
    except Exception as exc:
        # Record failure in a separate transaction; business writes roll back.
        psql(f"SET standard_conforming_strings=on; UPDATE ecommerce.ingestion_runs SET status='failed', finished_at=clock_timestamp(), error_message={literal(str(exc)[:1000])} WHERE run_id={run_id} AND status='running';")
        raise
    return run_id, {table: len(rows) for table, rows in data.items()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args()
    if args.start < 1 or args.count < 0:
        parser.error("start must be positive and count nonnegative")
    run_id, counts = run(args.start, args.count)
    print(json.dumps({"run_id": run_id, "submitted_rows": counts}, indent=2))

if __name__ == "__main__":
    main()
