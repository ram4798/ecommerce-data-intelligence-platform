"""Dagster assets for sequential local pipeline execution."""
import os
import subprocess
import sys
from pathlib import Path
from dagster import asset, Definitions, RetryPolicy, define_asset_job, ScheduleDefinition, AssetSelection, in_process_executor
from ecommerce.lakehouse import ROOT
from ecommerce.observability import measured

def warehouse_path():
    return str(Path(os.getenv("WAREHOUSE_PATH", str(ROOT / "data/warehouse.duckdb"))).resolve())

def command(*args):
    env = dict(os.environ, WAREHOUSE_PATH=warehouse_path())
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, env=env, check=True)

def dbt(*args):
    command("dbt.cli.main", *args, "--project-dir", str(ROOT / "analytics"), "--profiles-dir", str(ROOT / "analytics"))

retry = RetryPolicy(max_retries=2, delay=10)

@asset(retry_policy=retry, group_name="lakehouse")
def batch_delta():
    with measured("batch_delta"):
        command("ecommerce.lakehouse", "batch")

@asset(deps=[batch_delta], retry_policy=retry, group_name="lakehouse")
def streaming_delta():
    with measured("streaming_delta"):
        command("ecommerce.lakehouse", "stream")

@asset(deps=[streaming_delta], retry_policy=retry, group_name="warehouse")
def warehouse_sources():
    with measured("warehouse_sources"):
        command("ecommerce.warehouse")

@asset(deps=[warehouse_sources], retry_policy=retry, group_name="analytics")
def dbt_marts():
    with measured("dbt_marts"):
        dbt("build")

@asset(deps=[dbt_marts], group_name="quality")
def quality_gate():
    command("ecommerce.quality")

@asset(deps=[quality_gate], group_name="analytics")
def dbt_documentation():
    with measured("dbt_documentation"):
        dbt("docs", "generate")

@asset(deps=[quality_gate], group_name="serving")
def publish_serving():
    command("ecommerce.serving")

refresh = define_asset_job("refresh_analytics", selection=AssetSelection.all(), executor_def=in_process_executor)
schedule = ScheduleDefinition(job=refresh, cron_schedule="0 * * * *", execution_timezone="UTC")
defs = Definitions(assets=[batch_delta, streaming_delta, warehouse_sources, dbt_marts, quality_gate, dbt_documentation, publish_serving],
                   jobs=[refresh], schedules=[schedule])
