select account_id, sum(recognized_amount) as recognized_amount
from {{ ref('int_usage_revenue') }}
group by 1
