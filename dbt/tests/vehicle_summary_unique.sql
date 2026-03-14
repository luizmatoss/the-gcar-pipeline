select
  manufacturer,
  range,
  summary_key,
  count(*) as duplicate_count
from {{ ref('vehicle_summary') }}
group by 1, 2, 3
having count(*) > 1
