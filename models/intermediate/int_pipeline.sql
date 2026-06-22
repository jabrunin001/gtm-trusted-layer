select sum(net_new_arr) as open_pipeline_amount
from {{ ref('stg_salesforce__opportunities') }}
where is_open
