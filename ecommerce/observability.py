"""Persistent local stage metrics and Prometheus textfile output."""
import json
import os
import time
import tempfile
from pathlib import Path
from contextlib import contextmanager
from ecommerce.lakehouse import ROOT

def directory():
    return Path(os.getenv("OBSERVABILITY_DIR", str(ROOT / "data/observability")))

def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        f.write(content)
        temp = f.name
    os.replace(temp, path)

def record(stage, success, elapsed):
    root = directory()
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    entry = {"timestamp": now, "stage": stage, "success": success, "duration_seconds": elapsed}
    with (root / "pipeline.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")
    atomic(root / "metrics" / (stage + ".prom"),
           f'ecommerce_stage_success{{stage="{stage}"}} {int(success)}\n'
           f'ecommerce_stage_duration_seconds{{stage="{stage}"}} {elapsed:.6f}\n'
           f'ecommerce_stage_last_attempt_timestamp_seconds{{stage="{stage}"}} {now:.3f}\n')

@contextmanager
def measured(stage):
    start = time.monotonic()
    try:
        yield
    except Exception:
        record(stage, False, time.monotonic() - start)
        raise
    else:
        record(stage, True, time.monotonic() - start)
