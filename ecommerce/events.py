"""Versioned synthetic events with stable identities for replay."""
import json
import random
import uuid
from datetime import datetime, timezone

TYPES = ("page_view", "product_view", "cart_add", "purchase")
FIELDS = {"schema_version", "event_id", "event_type", "event_time", "customer_id", "product_id", "session_id"}
NAMESPACE = uuid.UUID("780e74f4-2291-42af-bfc2-a1fbbcc56c13")

def event(sequence, stream, timestamp=None):
    if sequence < 1 or not stream:
        raise ValueError("positive sequence and stream required")
    rng = random.Random(sequence)
    customer = rng.randint(1, 100)
    return {
        "schema_version": 1,
        "event_id": str(uuid.uuid5(NAMESPACE, f"{stream}:{sequence}")),
        "event_type": TYPES[(sequence - 1) % len(TYPES)],
        "event_time": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "customer_id": customer,
        "product_id": rng.randint(1, 50),
        "session_id": str(uuid.uuid5(NAMESPACE, f"{stream}:session:{customer}")),
    }

def decode(raw):
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != FIELDS:
            raise ValueError("invalid fields")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ValueError("unsupported schema version")
        if data["event_type"] not in TYPES:
            raise ValueError("invalid event type")
        for name in ("event_id", "session_id"):
            if str(uuid.UUID(data[name])) != data[name]:
                raise ValueError(f"invalid {name}")
        for name, maximum in (("customer_id", 100), ("product_id", 50)):
            if type(data[name]) is not int or not 1 <= data[name] <= maximum:
                raise ValueError(f"invalid {name}")
        if datetime.fromisoformat(data["event_time"]).utcoffset() is None:
            raise ValueError("timezone required")
        return data
    except (TypeError, ValueError, AttributeError, UnicodeError, OverflowError) as exc:
        raise ValueError(f"invalid event: {exc}") from exc
