{{ config(materialized='table') }}

select
  upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,
  vehicle_range,
  feature_name,
  feature_value,
  section
from {{ ref('bronze_features') }}
