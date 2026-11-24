{{ config(materialized='incremental', unique_key='order_item_id', incremental_strategy='delete+insert') }}
select l.*, case when l.status in ('paid','shipped') then l.line_value_cents else 0 end as paid_value_cents
from {{ ref('int_order_lines') }} l
{% if is_incremental() %}
where not exists (select 1 from {{ this }} t where t.order_item_id = l.order_item_id)
{% endif %}
