CREATE SCHEMA IF NOT EXISTS ecommerce;
CREATE TABLE IF NOT EXISTS ecommerce.raw_events (
 event_id uuid PRIMARY KEY,
 event_type text NOT NULL CHECK (event_type IN ('page_view','product_view','cart_add','purchase')),
 event_time timestamptz NOT NULL,
 customer_id bigint NOT NULL,
 product_id bigint NOT NULL,
 session_id uuid NOT NULL,
 payload jsonb NOT NULL,
 kafka_topic text NOT NULL,
 kafka_partition integer NOT NULL,
 kafka_offset bigint NOT NULL,
 ingested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(kafka_topic,kafka_partition,kafka_offset)
);
CREATE INDEX IF NOT EXISTS raw_events_time_idx ON ecommerce.raw_events(event_time);
