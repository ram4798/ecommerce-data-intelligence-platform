select s.order_date, c.region, count(distinct s.order_id) as orders,
 sum(s.line_value_cents) as gross_order_value_cents, sum(s.paid_value_cents) as paid_order_value_cents
from {{ ref('fct_sales') }} s join {{ ref('dim_customers') }} c on s.customer_id=c.customer_id
group by 1,2
