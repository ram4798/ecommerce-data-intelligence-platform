select customer_id, trim(region) as region from {{ source('lakehouse','customers') }}
