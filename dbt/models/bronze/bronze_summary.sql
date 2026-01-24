{{ config(materialized='view') }}

{% set raw_path = var('raw_summary_glob', '../data/raw/summary_*.jsonl') %}

with src as (
  select * from read_json_auto('{{ raw_path }}')
)

select
  scraped_at,
  page_url,
  manufacturer,
  vehicle_range,
  summary_key,
  summary_value
from src