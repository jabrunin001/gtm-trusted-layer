select
    account_id,
    net_new_arr,
    date_diff('day', created_date, close_date) as cycle_days
from {{ ref('stg_salesforce__opportunities') }}
where is_won
