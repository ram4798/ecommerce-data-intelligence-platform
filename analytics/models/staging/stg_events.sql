select event_id, event_type, cast(event_time as timestamp) as event_time, customer_id, product_id, session_id from {{ source('lakehouse','events') }}
