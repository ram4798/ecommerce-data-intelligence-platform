select i.order_item_id, i.order_id, o.customer_id, i.product_id,
 cast(o.ordered_at as date) as order_date, o.status, i.quantity,
 i.quantity * i.unit_price_cents as line_value_cents
from {{ ref('stg_order_items') }} i
join {{ ref('stg_orders') }} o on i.order_id = o.order_id
