"""Deterministic relational batches; IDs and values remain stable across overlapping ranges."""
import random
from datetime import datetime, timedelta, timezone

TABLES = {
    "customers": ("customer_id", "region"),
    "products": ("product_id", "category", "unit_price_cents"),
    "inventory": ("product_id", "available_units"),
    "orders": ("order_id", "customer_id", "ordered_at", "status", "total_cents"),
    "order_items": ("order_item_id", "order_id", "product_id", "quantity", "unit_price_cents"),
    "payments": ("payment_id", "order_id", "amount_cents"),
    "returns": ("return_id", "order_item_id", "quantity"),
}

def generate_batch(start=1, count=1000):
    if start < 1 or count < 0:
        raise ValueError("start must be positive and count nonnegative")
    data = {table: [] for table in TABLES}
    data["customers"] = [(i, ("US-West", "US-East", "US-Central")[i % 3]) for i in range(1, 101)]
    data["products"] = [(i, ("electronics", "home", "apparel")[i % 3], 500 + i * 17) for i in range(1, 51)]
    data["inventory"] = [(i, 100 + i * 3) for i in range(1, 51)]
    epoch = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(start, start + count):
        rng = random.Random(i)
        customer = rng.randint(1, 100)
        status = rng.choice(("placed", "paid", "shipped", "cancelled"))
        items = []
        for j, product in enumerate(rng.sample(range(1, 51), rng.randint(1, 3)), 1):
            items.append((i * 10 + j, i, product, rng.randint(1, 5), 500 + product * 17))
        total = sum(row[3] * row[4] for row in items)
        data["orders"].append((i, customer, epoch + timedelta(minutes=i), status, total))
        data["order_items"].extend(items)
        if status in ("paid", "shipped"):
            data["payments"].append((i, i, total))
        if status == "shipped" and i % 7 == 0:
            data["returns"].append((i, items[0][0], 1))
    return data

def validate(data):
    """Reject malformed batches before writing any business records."""
    if set(data) != set(TABLES):
        raise ValueError("unexpected table set")
    for table, columns in TABLES.items():
        rows = data[table]
        if any(len(row) != len(columns) or any(v is None for v in row) for row in rows):
            raise ValueError(f"{table}: missing or malformed values")
        if len({row[0] for row in rows}) != len(rows):
            raise ValueError(f"{table}: duplicate primary keys")
    customers = {r[0] for r in data["customers"]}
    products = {r[0]: r[2] for r in data["products"]}
    orders = {r[0]: r for r in data["orders"]}
    items = {r[0]: r for r in data["order_items"]}
    totals = dict.fromkeys(orders, 0)
    for product, units in data["inventory"]:
        if product not in products or units < 0:
            raise ValueError("invalid inventory")
    for row in orders.values():
        if row[1] not in customers or row[3] not in ("placed", "paid", "shipped", "cancelled") or row[4] <= 0:
            raise ValueError("invalid order")
    for _, order, product, quantity, price in items.values():
        if order not in orders or product not in products or quantity <= 0 or price <= 0 or price != products[product]:
            raise ValueError("invalid order item")
        totals[order] += quantity * price
    if any(totals[k] != row[4] for k, row in orders.items()):
        raise ValueError("order total mismatch")
    paid = set()
    for _, order, amount in data["payments"]:
        if order not in orders or order in paid or orders[order][3] not in ("paid", "shipped") or amount != totals[order]:
            raise ValueError("invalid payment")
        paid.add(order)
    if paid != {k for k, row in orders.items() if row[3] in ("paid", "shipped")}:
        raise ValueError("missing payment")
    returned = set()
    for _, item, quantity in data["returns"]:
        if item not in items or item in returned or not 0 < quantity <= items[item][3] or orders[items[item][1]][3] != "shipped":
            raise ValueError("invalid return")
        returned.add(item)
