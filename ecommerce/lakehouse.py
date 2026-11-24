"""Local Delta Lake batch and available-now streaming pipelines."""
import argparse
import os
from pathlib import Path

TABLES = ("customers", "products", "inventory", "orders", "order_items", "payments", "returns")
ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ["org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5", "org.postgresql:postgresql:42.7.5"]

def session():
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip
    builder = (SparkSession.builder.appName("ecommerce-lakehouse")
        .master(os.getenv("SPARK_MASTER", "local[2]"))
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.default.parallelism", "4")
        .config("spark.databricks.delta.snapshotPartitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.ui.enabled", "false"))
    spark = configure_spark_with_delta_pip(builder, extra_packages=PACKAGES).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark

def path(root, layer, name):
    return str(Path(root).resolve() / layer / name)

def read(spark, root, layer, name):
    return spark.read.format("delta").load(path(root, layer, name))

def overwrite(df, root, layer, name):
    df.write.format("delta").mode("overwrite").save(path(root, layer, name))

def merge(spark, df, target, key):
    from delta.tables import DeltaTable
    if not DeltaTable.isDeltaTable(spark, target):
        df.limit(0).write.format("delta").mode("errorifexists").save(target)
    (DeltaTable.forPath(spark, target).alias("t")
        .merge(df.alias("s"), f"t.{key} = s.{key}")
        .whenNotMatchedInsertAll().execute())

def config():
    values = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return {**values, **os.environ}

def batch(spark, root):
    from pyspark.sql import functions as F
    env = config()
    if not env.get("POSTGRES_PASSWORD"):
        raise ValueError("POSTGRES_PASSWORD missing; configure .env")
    for table in TABLES:
        df = (spark.read.format("jdbc")
            .option("url", env.get("POSTGRES_JDBC_URL", "jdbc:postgresql://127.0.0.1:5432/" + env.get("POSTGRES_DB", "ecommerce")))
            .option("dbtable", "ecommerce." + table)
            .option("user", env.get("POSTGRES_USER", "ecommerce"))
            .option("password", env["POSTGRES_PASSWORD"])
            .option("driver", "org.postgresql.Driver").load())
        overwrite(df.withColumn("_ingested_at", F.current_timestamp()), root, "bronze", table)
    orders = read(spark, root, "bronze", "orders").drop("_ingested_at")
    customers = read(spark, root, "bronze", "customers").select("customer_id", "region")
    items = read(spark, root, "bronze", "order_items")
    totals = items.groupBy("order_id").agg(F.sum(F.col("quantity") * F.col("unit_price_cents")).alias("item_total"))
    silver = (orders.join(customers, "customer_id", "inner").join(totals, "order_id", "inner")
        .where((F.col("total_cents") == F.col("item_total")) & (F.col("total_cents") > 0)
               & F.col("status").isin("placed", "paid", "shipped", "cancelled"))
        .drop("item_total").dropDuplicates(["order_id"]))
    overwrite(silver, root, "silver", "orders")
    gold = (silver.withColumn("order_date", F.to_date("ordered_at"))
        .groupBy("order_date", "region")
        .agg(F.count("*").alias("orders"), F.sum("total_cents").alias("gross_order_value_cents"),
             F.sum(F.when(F.col("status").isin("paid", "shipped"), F.col("total_cents")).otherwise(0)).alias("paid_order_value_cents")))
    overwrite(gold, root, "gold", "daily_sales")

def kafka_bronze(spark, root):
    from pyspark.sql import functions as F
    source = (spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", os.getenv("SPARK_KAFKA_BOOTSTRAP", "127.0.0.1:9092"))
        .option("subscribe", "ecommerce.events.v1")
        .option("startingOffsets", "earliest").option("maxOffsetsPerTrigger", 1000).load())
    raw = source.select("topic", "partition", "offset", F.col("timestamp").alias("broker_time"),
                        F.col("value").cast("string").alias("payload"), F.current_timestamp().alias("ingested_at"))
    query = (raw.writeStream.format("delta").outputMode("append")
        .option("checkpointLocation", path(root, "checkpoints", "kafka_bronze"))
        .trigger(availableNow=True).start(path(root, "bronze", "events")))
    query.awaitTermination()

def parsed_events(raw):
    from pyspark.sql import functions as F
    schema = "schema_version INT, event_id STRING, event_type STRING, event_time STRING, customer_id INT, product_id INT, session_id STRING"
    df = raw.withColumn("event", F.from_json("payload", schema)).select("*", "event.*").drop("event")
    df = df.withColumn("event_time", F.expr("try_cast(event_time as timestamp)"))
    uuid = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    valid = ((F.col("schema_version") == 1) & F.col("event_id").rlike(uuid) & F.col("session_id").rlike(uuid)
             & F.col("event_type").isin("page_view", "product_view", "cart_add", "purchase")
             & F.col("event_time").isNotNull() & F.col("customer_id").between(1, 100) & F.col("product_id").between(1, 50))
    return df.withColumn("is_valid", F.coalesce(valid, F.lit(False)))

def silver_events(spark, root):
    from pyspark.sql import functions as F
    bronze_path = path(root, "bronze", "events")
    parsed = parsed_events(spark.readStream.format("delta").load(bronze_path))
    valid = (parsed.where("is_valid").drop("is_valid")
        .withWatermark("event_time", "10 minutes").dropDuplicatesWithinWatermark(["event_id"]))
    def upsert(df, batch_id):
        merge(spark, df.dropDuplicates(["event_id"]), path(root, "silver", "events"), "event_id")
    query = (valid.writeStream.foreachBatch(upsert).outputMode("append")
        .option("checkpointLocation", path(root, "checkpoints", "silver_events"))
        .trigger(availableNow=True).start())
    query.awaitTermination()
    # Recompute quarantine from retained Bronze; no destructive changes to source data.
    rejected = parsed_events(read(spark, root, "bronze", "events")).where("NOT is_valid")
    overwrite(rejected, root, "silver", "rejected_events")

def gold_events(spark, root):
    from pyspark.sql import functions as F
    events = read(spark, root, "silver", "events")
    gold = (events.groupBy(F.window("event_time", "5 minutes").alias("window"))
        .agg(F.count("*").alias("events"),
             F.countDistinct("session_id").alias("active_sessions"),
             F.sum(F.when(F.col("event_type") == "purchase", 1).otherwise(0)).alias("purchase_events"),
             F.sum(F.when(F.col("event_type") == "product_view", 1).otherwise(0)).alias("product_views"))
        .select("window.start", "window.end", "events", "active_sessions", "purchase_events", "product_views"))
    overwrite(gold, root, "gold", "event_metrics")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("batch", "stream", "report"))
    parser.add_argument("--root", default=str(ROOT / "data/lakehouse"))
    args = parser.parse_args()
    spark = session()
    try:
        if args.command == "batch":
            batch(spark, args.root)
        elif args.command == "stream":
            kafka_bronze(spark, args.root)
            silver_events(spark, args.root)
            gold_events(spark, args.root)
        else:
            for name in ("daily_sales", "event_metrics"):
                print(name)
                read(spark, args.root, "gold", name).orderBy(read(spark, args.root, "gold", name).columns[0]).show(20, truncate=False)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
