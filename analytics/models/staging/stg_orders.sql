select order_id, customer_id, cast(ordered_at as timestamp) as ordered_at, status, total_cents from {{ source('lakehouse','orders') }}
