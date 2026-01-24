{{ config(materialized='table') }}

select
  manufacturer,
  vehicle_range as range,
  summary_key,
  summary_value
from {{ ref('silver_summary') }}