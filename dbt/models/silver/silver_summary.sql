{{ config(materialized='view') }}

with src as (
  select * from {{ ref('bronze_summary') }}
)
select
  upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,
  vehicle_range,
  summary_key,
  summary_value
from src
