{{ config(materialized='incremental', unique_key='event_id', incremental_strategy='delete+insert') }}
select e.* from {{ ref('stg_events') }} e
{% if is_incremental() %}
where not exists (select 1 from {{ this }} t where t.event_id = e.event_id)
{% endif %}
