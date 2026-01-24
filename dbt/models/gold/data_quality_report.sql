{{ config(materialized='table') }}

with vf as (
  select
    'gold.vehicle_features' as table_name,
    count(*) as total_rows,
    sum(case when manufacturer is null then 1 else 0 end) as null_manufacturer,
    sum(case when range is null then 1 else 0 end) as null_range,
    sum(case when feature_name is null then 1 else 0 end) as null_feature_name,
    sum(case when section is null then 1 else 0 end) as null_section
  from {{ ref('vehicle_features') }}
),
vs as (
  select
    'gold.vehicle_summary' as table_name,
    count(*) as total_rows,
    sum(case when manufacturer is null then 1 else 0 end) as null_manufacturer,
    sum(case when range is null then 1 else 0 end) as null_range,
    sum(case when summary_key is null then 1 else 0 end) as null_key,
    sum(case when summary_value is null then 1 else 0 end) as null_value
  from {{ ref('vehicle_summary') }}
)

select * from vf
union all
select * from vs