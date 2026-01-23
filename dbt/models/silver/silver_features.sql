select
  initcap(manufacturer) as manufacturer,
  vehicle_range as "range",
  feature_name,
  feature_value,
  case
    when lower(section) like 'interior%' then 'interior'
    when lower(section) like 'entertainment%' then 'entertainment'
    else lower(section)
  end as category
from {{ ref('bronze_features') }}
