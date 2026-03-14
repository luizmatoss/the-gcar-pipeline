select *
from {{ ref('data_quality_report') }}
where total_rows <= 0
