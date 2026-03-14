select
  manufacturer,
  vehicle_range,
  feature_name,
  count(*) as duplicate_count
from {{ ref('silver_features') }}
group by 1, 2, 3
having count(*) > 1
