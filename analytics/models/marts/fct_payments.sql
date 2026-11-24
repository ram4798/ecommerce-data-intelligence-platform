select payment_id, order_id, amount_cents from {{ ref('stg_payments') }}
