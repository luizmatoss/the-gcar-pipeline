select
  initcap(manufacturer) as manufacturer,
  vehicle_range as "range",
  summary_key,
  summary_value
from {{ ref('bronze_summary') }}
