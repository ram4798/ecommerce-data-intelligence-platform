CREATE SCHEMA IF NOT EXISTS ecommerce;
CREATE TABLE IF NOT EXISTS ecommerce.customers (
 customer_id bigint PRIMARY KEY, region text NOT NULL
);
CREATE TABLE IF NOT EXISTS ecommerce.products (
 product_id bigint PRIMARY KEY, category text NOT NULL, unit_price_cents bigint NOT NULL CHECK (unit_price_cents > 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.inventory (
 product_id bigint PRIMARY KEY REFERENCES ecommerce.products, available_units integer NOT NULL CHECK (available_units >= 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.orders (
 order_id bigint PRIMARY KEY, customer_id bigint NOT NULL REFERENCES ecommerce.customers,
 ordered_at timestamptz NOT NULL, status text NOT NULL CHECK (status IN ('placed','paid','shipped','cancelled')),
 total_cents bigint NOT NULL CHECK (total_cents > 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.order_items (
 order_item_id bigint PRIMARY KEY, order_id bigint NOT NULL REFERENCES ecommerce.orders,
 product_id bigint NOT NULL REFERENCES ecommerce.products, quantity integer NOT NULL CHECK (quantity > 0),
 unit_price_cents bigint NOT NULL CHECK (unit_price_cents > 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.payments (
 payment_id bigint PRIMARY KEY, order_id bigint UNIQUE NOT NULL REFERENCES ecommerce.orders,
 amount_cents bigint NOT NULL CHECK (amount_cents > 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.returns (
 return_id bigint PRIMARY KEY, order_item_id bigint UNIQUE NOT NULL REFERENCES ecommerce.order_items,
 quantity integer NOT NULL CHECK (quantity > 0)
);
CREATE TABLE IF NOT EXISTS ecommerce.ingestion_runs (
 run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz,
 start_id bigint NOT NULL, requested_orders integer NOT NULL,
 status text NOT NULL CHECK (status IN ('running','success','failed')),
 row_counts jsonb, error_message text
);
CREATE INDEX IF NOT EXISTS orders_ordered_at_idx ON ecommerce.orders(ordered_at);
CREATE INDEX IF NOT EXISTS items_order_id_idx ON ecommerce.order_items(order_id);
