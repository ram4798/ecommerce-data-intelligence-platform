with lines as (
 select order_id, sum(line_value_cents) as total from {{ ref('fct_sales') }} group by 1
)
select coalesce(o.order_id,l.order_id) as order_id
from {{ ref('stg_orders') }} o full outer join lines l on o.order_id=l.order_id
where o.order_id is null or l.order_id is null or o.total_cents <> l.total
