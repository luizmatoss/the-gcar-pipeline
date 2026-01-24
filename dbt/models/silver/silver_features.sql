{{ config(materialized='view') }}

with src as (
  select * from {{ ref('bronze_features') }}
)

select
  -- normaliza manufacturer
  upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,

  -- fallback: se vehicle_range vier null, tenta inferir por page_url (ajuste conforme seu scraper)
  coalesce(
    vehicle_range,
    nullif(regexp_extract(page_url, '/([^/]+)$', 1), '')
  ) as vehicle_range,

  feature_name,
  feature_value,

  -- padroniza para section (mesmo que bronze já seja section)
  lower(section) as section

from src;
