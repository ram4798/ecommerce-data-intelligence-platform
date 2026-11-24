select product_id, category, unit_price_cents from {{ source('lakehouse','products') }}
