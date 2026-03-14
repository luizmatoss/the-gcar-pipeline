{{ config(materialized='table') }}

with normalized as (
  select
    upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,
    vehicle_range,
    feature_name,
    feature_value,
    section,
    scraped_at,
    page_url
  from {{ ref('bronze_features') }}
),
ranked as (
  select
    manufacturer,
    vehicle_range,
    feature_name,
    feature_value,
    section,
    row_number() over (
      partition by manufacturer, vehicle_range, feature_name
      order by scraped_at desc, page_url desc, feature_value desc, section desc
    ) as rn
  from normalized
)
select
  manufacturer,
  vehicle_range,
  feature_name,
  feature_value,
  section
from ranked
where rn = 1
