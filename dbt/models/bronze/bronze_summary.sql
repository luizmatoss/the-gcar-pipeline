{{ config(materialized='view') }}

select
  *
from read_json_auto('../data/raw/summary_*.jsonl')
