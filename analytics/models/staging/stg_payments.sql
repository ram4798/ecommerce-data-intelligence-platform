select payment_id, order_id, amount_cents from {{ source('lakehouse','payments') }}
