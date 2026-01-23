{{ config(materialized='table') }}

select
  manufacturer,
  vehicle_range as range,
  feature_name,
  feature_value
from {{ ref('silver_features') }}
