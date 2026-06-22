select account_id, usage_month, sum(recognized_amount) as recognized_amount
from {{ ref('stg_billing__usage_events') }}
group by 1, 2
