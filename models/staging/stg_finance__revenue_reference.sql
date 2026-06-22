select account_id, period, recognized_revenue, prior_recognized_revenue, loaded_at
from {{ ref('finance_revenue_reference') }}
