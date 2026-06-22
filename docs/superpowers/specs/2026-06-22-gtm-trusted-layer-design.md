# gtm-trusted-layer — Design

**Status:** Approved (design phase)
**Date:** 2026-06-22
**Target role:** Staff, Analytics Engineer — GTM Data Science & Analytics (Twilio)

## Why this exists

Twilio's posting asks for someone who can build "a formal business data layer in
dbt that centralizes and reconciles data from multiple sources into a single
trusted source," align GTM Ops and Finance on metric definitions, build automated
reconciliation and quality checks, and mentor on modeling/testing/documentation
standards.

`gtm-trusted-layer` is a small, **runnable** repo (clone → run, no warehouse, no
credentials, no network) that demonstrates exactly that capability on a
GTM/sales-metrics domain, with one memorable proof that shows real engineering
judgment.

## Thesis

A GTM metric is **trusted** only when it is all three of:

1. **Governed** — exactly one definition in a registry, with a declared
   source-of-truth and an owning org (GTM Ops vs Finance).
2. **Fresh** — its underlying sources are within an allowed staleness window.
3. **Reconciled** — the published mart value matches an **independently computed**
   golden reference, within a declared tolerance.

The point the repo makes: **reconciliation across independent sources — not schema
tests — is what catches a metric that is quietly wrong.**

## The proof (the memorable bug)

The headline metric is `recognized_net_new_arr`. Its governed definition declares
the source-of-truth to be **billing usage** — what customers actually consumed.
This is the usage-based-billing reality of Twilio: bookings are a promise; usage
is the money.

The injected break (`gtm certify --inject-break`, implemented via a dbt var
`inject_break: true`) "optimizes" the metric to source from **Salesforce
bookings** instead — cleaner, faster, more complete data. The change is plausible
and the kind of thing that ships in a real org.

- Every dbt schema test and unit test stays **green** — the CRM numbers are
  internally valid (not null, unique keys, accepted values, referential
  integrity all hold).
- Only **reconciliation** against the independent billing-derived golden
  reference catches it:
  - CRM bookings path → Net New ARR = **$1.2M**
  - Billing usage path (golden) → Recognized = **$0.9M**
  - delta = **$300K** overstatement → **FAIL**

Clean run: every metric certified. Broken run: reconciliation fails loudly and
the CLI exits nonzero. CI asserts **both** states — that the clean build
certifies, and that the injected break is actually caught.

## Architecture

Engine: **dbt + DuckDB** locally so it clones-and-runs free. The cloud warehouse
(Snowflake) is an **optional** dbt target selected by env vars (`--target prod`);
no credentials are needed for the default local path.

No MetricFlow / dbt semantic layer. We use plain dbt models plus a YAML metric
registry and a Python reconciliation engine. This is a deliberate choice: it is
more robust (no version-pinning fragility), lets us use modern **Pydantic v2**,
and keeps the "business data layer" legible as ordinary dbt.

### dbt layers

| Layer | Path | Contents |
|---|---|---|
| Seeds | `seeds/` | Deterministic synthetic CSVs: `salesforce_opportunities`, `salesforce_accounts`, `billing_usage_events`, `billing_invoices`, `finance_revenue_reference`, `quotas`, `product_catalog` |
| Staging | `models/staging/` | `stg_salesforce__opportunities`, `stg_salesforce__accounts`, `stg_billing__usage_events`, `stg_billing__invoices`, `stg_finance__revenue_reference` — clean/cast/rename, one model per source table |
| Intermediate | `models/intermediate/` | `int_bookings` (CRM path), `int_usage_revenue` (billing path), `int_pipeline` |
| Marts (the trusted layer) | `models/marts/gtm/` | `fct_bookings`, `fct_revenue`, `dim_account`, `mart_gtm_metrics` (the published certified metric values) |
| Reference | `models/reference/` | `ref_metric_values.sql` — golden values recomputed by an **independent path**; the reconciliation target |

### Metric registry

`metrics/registry.yml` — one governed definition per metric. Fields per metric:

- `name`, `description`, `grain`
- `source_of_truth` — which model/path is authoritative
- `owning_org` — `gtm_ops` or `finance`
- `tolerance` — absolute and/or relative tolerance for reconciliation
- `reference` — the column in `ref_metric_values` to reconcile against
- `freshness_sources` — source tables whose freshness gates the metric

Certified metric set (target ~8 metrics), e.g.: `recognized_net_new_arr`,
`gross_new_arr`, `pipeline_coverage`, `win_rate`, `average_sales_cycle_days`,
`quota_attainment`, `net_revenue_retention`, `logo_count`.

## CLI (`gtm`)

Typer + **Pydantic v2**. Rich for table output.

- `gtm build` — `dbt seed` + `dbt run` (optionally passing `inject_break`).
- `gtm certify [--inject-break] [--target local|prod]` — for every metric in the
  registry: check governance (definition present, source matches), freshness, and
  reconciliation (mart value vs reference within tolerance). Prints a Rich table
  and an `N/N certified` summary. Exit nonzero if any metric fails.
- `gtm reconcile <metric>` — root-cause detail for one metric: both source
  values, the delta, the owning org for each source, and a plain-language
  explanation. Maps to the JD line "investigate anomalies, perform root cause
  analysis, communicate to technical and non-technical stakeholders."
- `gtm anomaly [--metric <name>]` — **local-only** deterministic anomaly
  classifier over each metric's history (z-score / IQR rules), with an
  **optional** Ollama-generated natural-language explanation if a local model is
  present. Never calls a cloud API; never requires a key.

## CI (GitHub Actions)

One workflow, `ci.yml`:

1. Install deps, `gtm build`.
2. `dbt build` + dbt tests (schema + unit) — all green.
3. `gtm certify` — asserts clean run = **all metrics certified** (exit 0).
4. `gtm certify --inject-break` — asserts reconciliation **FAILS** (nonzero
   exit), proving the control actually catches the bug.

The third and fourth steps are the heart: CI verifies both that good data
certifies and that the planted bad metric is caught.

## Staff-level / mentorship dimension

A named JD responsibility is mentoring on "modeling best practices, testing,
documentation, and code review standards." Concrete artifacts:

- `docs/standards/` — modeling conventions (naming, layering, grain
  discipline), testing standards, and a code-review checklist.
- `.github/pull_request_template.md` — encodes the review checklist.
- dbt **model contracts** on the mart models + a documentation-coverage gate
  (every mart column documented) enforced in CI.

## README capability map

The README ends with a table mapping each JD requirement to the exact file/dir
where it is demonstrated, so a reviewer can verify coverage at a glance.

## Deliberate differentiators from `certified-metrics-framework`

- Plain dbt + YAML registry instead of MetricFlow → more robust, modern
  Pydantic v2, no semantic-layer version pinning.
- GTM/sales domain with **usage-vs-bookings** as the central tension (Twilio's
  usage-based billing), instead of generic finance MRR.
- Cross-org **ownership** is modeled in the registry (GTM Ops vs Finance), making
  the "align orgs on definitions" responsibility concrete.

## Out of scope (YAGNI)

- No real warehouse connection required to run or grade the repo.
- No cloud AI, no API keys, no network calls in the default path.
- No web UI / dashboard — the CLI table and the reconciliation report are the
  interface.
- No streaming / incremental-load machinery; seeds are small and static.

## Success criteria

- `git clone && <setup> && gtm build && gtm certify` runs free on a clean
  machine and reports all metrics certified.
- `gtm certify --inject-break` fails reconciliation on `recognized_net_new_arr`
  while all dbt tests still pass.
- CI is green on the asserted clean + asserted-caught-break sequence.
- README capability map covers every JD requirement.
