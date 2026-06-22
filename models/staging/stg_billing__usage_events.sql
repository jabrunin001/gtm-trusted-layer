select
    event_id,
    account_id,
    product_code,
    recognized_amount,
    usage_date,
    date_trunc('month', usage_date) as usage_month,
    loaded_at
from {{ ref('billing_usage_events') }}
