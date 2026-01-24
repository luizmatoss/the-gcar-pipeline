{{ config(materialized='view') }}

{% set raw_path = env_var('RAW_FEATURES_GLOB', '../data/raw/features_*.jsonl') }}

with src as (
  select * from read_json_auto('{{ raw_path }}')
)

select
  scraped_at,
  page_url,
  manufacturer,
  vehicle_range,
  feature_name,
  feature_value,
  section
from src
