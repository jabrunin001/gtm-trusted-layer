select
    opportunity_id,
    account_id,
    stage,
    net_new_arr,
    created_date,
    close_date,
    stage = 'Closed Won'  as is_won,
    stage = 'Closed Lost' as is_lost,
    stage in ('Negotiation', 'Proposal') as is_open,
    loaded_at
from {{ ref('salesforce_opportunities') }}
