{{ config(materialized='view') }}

with src as (
  select * from {{ ref('bronze_features') }}
)
select
  upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,
  -- se você não tem range no bronze_features, mantemos null por enquanto
  null::varchar as vehicle_range,
  feature_name,
  feature_value,
  lower(section) as category
from src
where lower(section) in ('interior features', 'entertainment')
