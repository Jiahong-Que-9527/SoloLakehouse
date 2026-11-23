{{ config(materialized='view') }}

select
    settlement_id,
    session_id,
    roaming_partner,
    roaming_fee_local,
    currency_code,
    settled_at
from {{ source('raw', 'raw_roaming_settlements') }}
