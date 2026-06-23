# gtm-trusted-layer

A runnable dbt + DuckDB **business data layer** for GTM/sales metrics. Every metric is
**certified** only when it is **governed** (one definition, one owning org), **fresh**, and
**reconciled** against an independent recomputation. Clone and run free — no warehouse, no
credentials, no network.

## The proof

`recognized_net_new_arr` is governed to come from **billing usage** (what customers actually
consumed). Run `gtm certify --inject-break` and the metric is silently re-sourced from
**Salesforce bookings**. Every dbt test stays green — but reconciliation against the
independent billing reference catches the **$300K overstatement** (1,200,000 booked vs
900,000 recognized) and CI fails. That gap between *passes tests* and *is actually correct*
is the entire point.

## Requirements

**Python 3.11 or 3.12 is required.** dbt-core 1.8 does not run on Python 3.13+ (the project
caps `requires-python = ">=3.11,<3.13"`).

## Quickstart

```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/dbt deps --profiles-dir .
.venv/bin/gtm certify                        # builds + certifies; 8/8 metrics certified
.venv/bin/gtm certify --inject-break         # reconciliation FAILS, exit 1 (7/8; $300K gap)
.venv/bin/gtm reconcile recognized_net_new_arr   # root-cause detail
.venv/bin/gtm anomaly                        # local anomaly scan on monthly recognized revenue
```

Optional Snowflake target: `gtm certify --target prod` with `SNOWFLAKE_*` env vars set.

## Capability map (Twilio Staff Analytics Engineer JD → where it lives)

| JD requirement | Where in this repo |
|---|---|
| Business data layer in dbt centralizing multiple sources | `models/staging` + `models/marts/gtm` (SFDC + billing + finance → `mart_gtm_metrics`) |
| Reconcile sources into a single trusted source | `models/reference/ref_metric_values.sql` + `gtm/reconcile.py` |
| Align GTM Ops & Finance on metric definitions | `metrics/registry.yml` (`owning_org` per metric) |
| Automated reconciliation & quality checks | `gtm certify`, `gtm/certify.py`, dbt tests + contracts |
| dbt tests, CI/CD, data observability | `.github/workflows/ci.yml`, freshness checks in `certify`, `gtm anomaly` |
| Root-cause analysis & stakeholder communication | `gtm reconcile <metric>` (`gtm/report.py`) |
| Mentorship on modeling/testing/review standards | `docs/standards/`, `.github/pull_request_template.md`, model contracts |

## Architecture

`seeds → staging → intermediate → marts/gtm (trusted) → reference (independent)`.
The Python `gtm` CLI loads the registry, queries DuckDB, reconciles each metric against its
reference, checks freshness, and renders a certification table. See
`docs/superpowers/specs/2026-06-22-gtm-trusted-layer-design.md` for the full design.
