select distinct cast(ordered_at as date) as date_day from {{ ref('stg_orders') }}
union
select distinct cast(event_time as date) as date_day from {{ ref('stg_events') }}
