select account_id, account_name, segment
from {{ ref('stg_salesforce__accounts') }}
