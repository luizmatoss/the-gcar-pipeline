select
  manufacturer,
  vehicle_range,
  summary_key,
  count(*) as duplicate_count
from {{ ref('silver_summary') }}
group by 1, 2, 3
having count(*) > 1
