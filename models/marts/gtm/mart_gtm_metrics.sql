-- Published, certified GTM metric values (the trusted business data layer).
with recognized_net_new_arr as (
    {% if var('inject_break', false) %}
    select cast(sum(net_new_arr) as double) as v from {{ ref('fct_bookings') }}
    {% else %}
    select cast(sum(recognized_amount) as double) as v from {{ ref('fct_revenue') }}
    {% endif %}
)
select 'recognized_net_new_arr' as metric_name, v as metric_value from recognized_net_new_arr
union all select 'gross_new_arr', cast(sum(net_new_arr) as double) from {{ ref('fct_bookings') }}
union all select 'pipeline_coverage',
    cast((select open_pipeline_amount from {{ ref('int_pipeline') }})
         / (select sum(quota_amount) from {{ ref('quotas') }}) as double)
union all select 'win_rate',
    cast(count(*) filter (where is_won) as double)
    / nullif(count(*) filter (where is_won or is_lost), 0)
    from {{ ref('stg_salesforce__opportunities') }}
union all select 'average_sales_cycle_days', cast(avg(cycle_days) as double) from {{ ref('fct_bookings') }}
union all select 'quota_attainment',
    cast((select sum(net_new_arr) from {{ ref('fct_bookings') }})
         / (select sum(quota_amount) from {{ ref('quotas') }}) as double)
union all select 'net_revenue_retention',
    cast(sum(recognized_revenue) as double) / nullif(sum(prior_recognized_revenue), 0)
    from {{ ref('stg_finance__revenue_reference') }}
union all select 'logo_count', cast(count(distinct account_id) as double) from {{ ref('fct_bookings') }}
