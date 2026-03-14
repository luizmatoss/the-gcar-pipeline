select
  manufacturer,
  range,
  feature_name,
  count(*) as duplicate_count
from {{ ref('vehicle_features') }}
group by 1, 2, 3
having count(*) > 1
