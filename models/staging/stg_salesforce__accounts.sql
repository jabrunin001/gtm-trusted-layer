select
    account_id,
    account_name,
    segment,
    loaded_at
from {{ ref('salesforce_accounts') }}
