-- Independent recomputation of all GTM metrics via alternative source paths.
-- recognized_net_new_arr comes from invoices (not usage events), so it stays
-- 900,000 regardless of the inject_break var — this is the independent reference.
--
-- Reconciliation strategy:
--   Independent sources: recognized_net_new_arr (usage vs invoices);
--     gross_new_arr / quota_attainment (mart/model vs raw opportunities);
--     logo_count (bookings vs invoices).
--   Same-source recomputation: win_rate, average_sales_cycle_days,
--     net_revenue_retention — validated by an independent SQL recomputation
--     on the same authoritative source, confirming the mart aggregation is correct.
select 'recognized_net_new_arr' as metric_name,
    cast(sum(invoice_amount) as double) as reference_value from {{ ref('stg_billing__invoices') }}
union all select 'gross_new_arr',
    cast(sum(seg_total) as double) from (
        select segment, sum(o.net_new_arr) as seg_total
        from {{ ref('stg_salesforce__opportunities') }} o
        join {{ ref('stg_salesforce__accounts') }} a using (account_id)
        where o.is_won group by segment
    )
union all select 'pipeline_coverage',
    cast(sum(net_new_arr) filter (where is_open) as double)
    / (select sum(quota_amount) from {{ ref('quotas') }})
    from {{ ref('stg_salesforce__opportunities') }}
union all select 'win_rate',
    cast(sum(case when is_won then 1 else 0 end) as double)
    / nullif(sum(case when is_won or is_lost then 1 else 0 end), 0)
    from {{ ref('stg_salesforce__opportunities') }}
union all select 'average_sales_cycle_days',
    cast(avg(date_diff('day', created_date, close_date)) as double)
    from {{ ref('stg_salesforce__opportunities') }} where is_won
union all select 'quota_attainment',
    cast(sum(net_new_arr) filter (where is_won) as double)
    / (select sum(quota_amount) from {{ ref('quotas') }})
    from {{ ref('stg_salesforce__opportunities') }}
union all select 'net_revenue_retention',
    cast(sum(recognized_revenue) as double) / nullif(sum(prior_recognized_revenue), 0)
    from {{ ref('stg_finance__revenue_reference') }}
union all select 'logo_count',
    cast(count(distinct account_id) as double) from {{ ref('stg_billing__invoices') }}
