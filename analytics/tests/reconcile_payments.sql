select o.order_id
from {{ ref('stg_orders') }} o left join {{ ref('fct_payments') }} p on o.order_id=p.order_id
where (o.status in ('paid','shipped') and (p.order_id is null or p.amount_cents <> o.total_cents))
   or (o.status not in ('paid','shipped') and p.order_id is not null)
union all
select p.order_id from {{ ref('fct_payments') }} p left join {{ ref('stg_orders') }} o on p.order_id=o.order_id
where o.order_id is null
