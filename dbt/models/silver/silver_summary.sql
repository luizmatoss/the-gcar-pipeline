with normalized as (
  select
    upper(substr(manufacturer, 1, 1)) || lower(substr(manufacturer, 2)) as manufacturer,
    vehicle_range,
    summary_key,
    summary_value,
    scraped_at,
    page_url
  from {{ ref('bronze_summary') }}
),
ranked as (
  select
    manufacturer,
    vehicle_range,
    summary_key,
    summary_value,
    row_number() over (
      partition by manufacturer, vehicle_range, summary_key
      order by scraped_at desc, page_url desc, summary_value desc
    ) as rn
  from normalized
)
select
  manufacturer,
  vehicle_range,
  summary_key,
  summary_value
from ranked
where rn = 1
