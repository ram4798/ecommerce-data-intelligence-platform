"""Generate deterministic synthetic order records without external dependencies."""
import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIELDS = ("order_id", "customer_id", "product_id", "ordered_at", "quantity", "unit_price_cents", "total_cents", "currency", "status")

def generate_orders(count: int, seed: int = 42):
    if count < 0:
        raise ValueError("count must be nonnegative")
    rng = random.Random(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        quantity = rng.randint(1, 5)
        product = rng.randint(1, 1000)
        price = 500 + product * 17
        yield {
            "order_id": f"ORD-{i + 1:09d}",
            "customer_id": f"C-{rng.randint(1, 10000):05d}",
            "product_id": f"P-{product:04d}",
            "ordered_at": (start + timedelta(seconds=rng.randrange(86400 * 365))).isoformat(),
            "quantity": quantity,
            "unit_price_cents": price,
            "total_cents": quantity * price,
            "currency": "USD",
            "status": rng.choice(("placed", "paid", "shipped", "cancelled")),
        }

def write_orders(path: Path, count: int, seed: int = 42) -> None:
    if count < 0:
        raise ValueError("count must be nonnegative")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(generate_orders(count, seed))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/raw/orders.csv"))
    args = parser.parse_args()
    if args.orders < 0:
        parser.error("--orders must be nonnegative")
    write_orders(args.output, args.orders, args.seed)
    print(f"Wrote {args.orders} synthetic orders to {args.output}")

if __name__ == "__main__":
    main()
