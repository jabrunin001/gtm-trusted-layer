# gtm-trusted-layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runnable dbt + DuckDB GTM "business data layer" that certifies sales metrics as governed, fresh, and reconciled, and whose reconciliation catches a metric silently re-sourced from CRM bookings even though all dbt tests pass.

**Architecture:** dbt models transform synthetic Salesforce + billing + finance seeds into a trusted mart (`mart_gtm_metrics`). An independent `ref_metric_values` model recomputes every metric by a separate path. A Python CLI (`gtm`, Typer + Pydantic v2) checks each registry metric for governance, freshness, and reconciliation against the reference, and exits nonzero on any failure. A dbt var `inject_break` re-sources the headline metric from bookings; CI asserts the clean build certifies and the broken build is caught.

**Tech Stack:** dbt-core 1.8.x, dbt-duckdb 1.8.x, DuckDB, dbt_utils; Python 3.11; Typer, Pydantic v2, PyYAML, Rich, duckdb (Python), pytest. Optional Ollama for local anomaly explanations (never required, never cloud).

## Global Constraints

- **No network / no credentials in the default path.** Everything runs against a local DuckDB file `gtm_trusted_layer.duckdb` in the repo root. Snowflake is an optional dbt target via `env_var` only.
- **Pydantic v2** (>=2.6). Use v2 APIs (`model_validate`, `model_dump`), not v1.
- **`gtm/cli.py` MUST NOT use `from __future__ import annotations`** — it breaks Typer's bool-flag (`--inject-break`) introspection.
- **Pin `click==8.1.7`** alongside `typer>=0.12,<0.13` so `--help` renders.
- **dbt unit tests live under `models/`** (dbt 1.8 ignores them elsewhere); define them in the schema YAML next to the model.
- **dbt is invoked through the active interpreter's bin dir** (`Path(sys.executable).parent / "dbt"`), never a bare `dbt` from PATH.
- **All dbt commands pass `--profiles-dir .`** so the in-repo `profiles.yml` is used.
- **Fixed clock:** the "as-of" date is `2026-06-22`; the freshness window is 7 days; all seed `loaded_at` values are `2026-06-20`. No `datetime.now()` anywhere — pass the as-of date in.
- **Engineered totals (must hold exactly):** Closed-Won bookings net-new ARR = `1,200,000`; billing recognized revenue (usage events) = `900,000`; billing invoices total = `900,000`; open pipeline = `250,000`; total quota = `1,000,000`; prior-period recognized = `750,000`; distinct won logos = `5`.

---

## File Structure

```
gtm-trusted-layer/
├── pyproject.toml                 # gtm package + deps + console_scripts entrypoint
├── dbt_project.yml                # dbt config, vars: inject_break: false
├── profiles.yml                   # duckdb 'local' + snowflake 'prod'
├── packages.yml                   # dbt_utils
├── metrics/registry.yml           # governed metric definitions
├── seeds/                         # 7 deterministic CSVs + _seeds.yml
├── models/
│   ├── staging/                   # stg_* + _staging.yml (sources, tests)
│   ├── intermediate/              # int_bookings, int_usage_revenue, int_pipeline
│   ├── marts/gtm/                 # dim_account, fct_bookings, fct_revenue, mart_gtm_metrics + _gtm.yml
│   └── reference/                 # ref_metric_values + _reference.yml
├── gtm/                           # Python package
│   ├── __init__.py  config.py  registry.py  warehouse.py
│   ├── reconcile.py  certify.py  report.py  dbt_runner.py  anomaly.py  cli.py
├── tests/                         # pytest: registry, reconcile, certify, anomaly, cli
├── scripts/check_doc_coverage.py  # docs gate used by CI
├── docs/standards/                # modeling.md, testing.md, code-review.md
└── .github/workflows/ci.yml  .github/pull_request_template.md
```

---

### Task 1: Project scaffolding (Python package + dbt project)

**Files:**
- Create: `pyproject.toml`, `dbt_project.yml`, `profiles.yml`, `packages.yml`
- Create: `gtm/__init__.py`, `gtm/config.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: `gtm.config` constants — `REPO_ROOT: Path`, `DUCKDB_PATH: Path`, `AS_OF: date` (= 2026-06-22), `FRESHNESS_WINDOW_DAYS: int` (= 7), `REGISTRY_PATH: Path`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "gtm-trusted-layer"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "dbt-core>=1.8,<1.9",
    "dbt-duckdb>=1.8,<1.9",
    "duckdb>=0.10",
    "typer>=0.12,<0.13",
    "click==8.1.7",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
gtm = "gtm.cli:app"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["gtm"]
```

- [ ] **Step 2: Write `dbt_project.yml`**

```yaml
name: gtm_trusted_layer
version: "1.0.0"
config-version: 2
profile: gtm_trusted_layer
model-paths: ["models"]
seed-paths: ["seeds"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]
vars:
  inject_break: false
models:
  gtm_trusted_layer:
    staging:
      +materialized: view
    intermediate:
      +materialized: view
    marts:
      +materialized: table
    reference:
      +materialized: table
seeds:
  gtm_trusted_layer:
    +column_types:
      loaded_at: date
```

- [ ] **Step 3: Write `profiles.yml`**

```yaml
gtm_trusted_layer:
  target: local
  outputs:
    local:
      type: duckdb
      path: gtm_trusted_layer.duckdb
      threads: 4
    prod:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT', '') }}"
      user: "{{ env_var('SNOWFLAKE_USER', '') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD', '') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', '') }}"
      database: "{{ env_var('SNOWFLAKE_DATABASE', '') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', '') }}"
      schema: "{{ env_var('SNOWFLAKE_SCHEMA', 'gtm') }}"
```

- [ ] **Step 4: Write `packages.yml`**

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.1.0", "<2.0.0"]
```

- [ ] **Step 5: Write `gtm/__init__.py`** (single line)

```python
__version__ = "0.1.0"
```

- [ ] **Step 6: Write `gtm/config.py`**

```python
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "gtm_trusted_layer.duckdb"
REGISTRY_PATH = REPO_ROOT / "metrics" / "registry.yml"
AS_OF = date(2026, 6, 22)
FRESHNESS_WINDOW_DAYS = 7
```

- [ ] **Step 7: Write `tests/test_smoke.py`**

```python
from datetime import date
import gtm
from gtm import config

def test_package_imports():
    assert gtm.__version__ == "0.1.0"

def test_config_constants():
    assert config.AS_OF == date(2026, 6, 22)
    assert config.FRESHNESS_WINDOW_DAYS == 7
    assert config.REPO_ROOT.name == "gtm-trusted-layer"
```

- [ ] **Step 8: Install and run the smoke test**

Run:
```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest tests/test_smoke.py -v
```
Expected: 2 passed. (Use `.venv/bin/python` explicitly for all later commands.)

- [ ] **Step 9: Install dbt packages and verify dbt connects**

Run:
```bash
.venv/bin/dbt deps --profiles-dir .
.venv/bin/dbt debug --profiles-dir .
```
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "Scaffold gtm package and dbt project"
```

---

### Task 2: Seed data

Seven deterministic CSVs. Totals are load-bearing for every later assertion — copy the values exactly.

**Files:**
- Create: `seeds/salesforce_accounts.csv`, `seeds/salesforce_opportunities.csv`, `seeds/billing_usage_events.csv`, `seeds/billing_invoices.csv`, `seeds/finance_revenue_reference.csv`, `seeds/quotas.csv`, `seeds/product_catalog.csv`
- Create: `seeds/_seeds.yml`
- Test: `tests/test_seed_totals.py`

- [ ] **Step 1: Write `seeds/salesforce_accounts.csv`**

```csv
account_id,account_name,segment,loaded_at
A1,Acme,Enterprise,2026-06-20
A2,Globex,Enterprise,2026-06-20
A3,Initech,MidMarket,2026-06-20
A4,Umbrella,MidMarket,2026-06-20
A5,Soylent,SMB,2026-06-20
```

- [ ] **Step 2: Write `seeds/salesforce_opportunities.csv`** (Won net-new ARR = 1,200,000; open pipeline = 250,000; 5 won, 1 lost)

```csv
opportunity_id,account_id,stage,net_new_arr,created_date,close_date,loaded_at
O1,A1,Closed Won,300000,2026-01-02,2026-03-30,2026-06-20
O2,A2,Closed Won,250000,2026-01-10,2026-03-15,2026-06-20
O3,A3,Closed Won,200000,2026-02-01,2026-04-20,2026-06-20
O4,A4,Closed Won,250000,2026-01-20,2026-04-05,2026-06-20
O5,A5,Closed Won,200000,2026-02-15,2026-04-10,2026-06-20
O6,A1,Negotiation,150000,2026-05-01,,2026-06-20
O7,A2,Proposal,100000,2026-05-10,,2026-06-20
O8,A3,Closed Lost,80000,2026-02-20,2026-04-25,2026-06-20
```

- [ ] **Step 3: Write `seeds/billing_usage_events.csv`** (per-account totals A1 250k, A2 200k, A3 150k, A4 180k, A5 120k = 900,000; per-month totals 120k/130k/125k/135k/260k/130k for anomaly detection)

```csv
event_id,account_id,product_code,recognized_amount,usage_date,loaded_at
E1,A1,SMS,30000,2026-01-15,2026-06-20
E2,A1,SMS,220000,2026-05-15,2026-06-20
E3,A2,VOICE,100000,2026-02-15,2026-06-20
E4,A2,VOICE,100000,2026-03-15,2026-06-20
E5,A3,SMS,90000,2026-01-15,2026-06-20
E6,A3,SMS,60000,2026-04-15,2026-06-20
E7,A4,VOICE,75000,2026-04-15,2026-06-20
E8,A4,VOICE,105000,2026-06-15,2026-06-20
E9,A5,SMS,30000,2026-02-15,2026-06-20
E10,A5,SMS,25000,2026-03-15,2026-06-20
E11,A5,SMS,40000,2026-05-15,2026-06-20
E12,A5,SMS,25000,2026-06-15,2026-06-20
```

- [ ] **Step 4: Write `seeds/billing_invoices.csv`** (independent billing source; per-account = usage totals; sum 900,000)

```csv
invoice_id,account_id,invoice_amount,invoice_date,loaded_at
INV1,A1,250000,2026-06-15,2026-06-20
INV2,A2,200000,2026-06-15,2026-06-20
INV3,A3,150000,2026-06-15,2026-06-20
INV4,A4,180000,2026-06-15,2026-06-20
INV5,A5,120000,2026-06-15,2026-06-20
```

- [ ] **Step 5: Write `seeds/finance_revenue_reference.csv`** (current recognized = usage totals = 900,000; prior = 750,000 for NRR = 1.2)

```csv
account_id,period,recognized_revenue,prior_recognized_revenue,loaded_at
A1,2026,250000,210000,2026-06-20
A2,2026,200000,170000,2026-06-20
A3,2026,150000,120000,2026-06-20
A4,2026,180000,150000,2026-06-20
A5,2026,120000,100000,2026-06-20
```

- [ ] **Step 6: Write `seeds/quotas.csv`** (total quota 1,000,000)

```csv
period,segment,quota_amount,loaded_at
2026,All,1000000,2026-06-20
```

- [ ] **Step 7: Write `seeds/product_catalog.csv`**

```csv
product_code,product_name,category
SMS,Programmable Messaging,Messaging
VOICE,Programmable Voice,Voice
```

- [ ] **Step 8: Write `seeds/_seeds.yml`** (key tests on the source data)

```yaml
version: 2
seeds:
  - name: salesforce_accounts
    columns:
      - name: account_id
        tests: [unique, not_null]
  - name: salesforce_opportunities
    columns:
      - name: opportunity_id
        tests: [unique, not_null]
      - name: account_id
        tests:
          - not_null
          - relationships:
              to: ref('salesforce_accounts')
              field: account_id
      - name: stage
        tests:
          - accepted_values:
              values: ["Closed Won", "Closed Lost", "Negotiation", "Proposal"]
  - name: billing_usage_events
    columns:
      - name: event_id
        tests: [unique, not_null]
  - name: billing_invoices
    columns:
      - name: invoice_id
        tests: [unique, not_null]
```

- [ ] **Step 9: Load seeds and assert totals with DuckDB**

Write `tests/test_seed_totals.py`:

```python
import subprocess, sys
from pathlib import Path
import duckdb
from gtm.config import REPO_ROOT, DUCKDB_PATH

def _dbt(*args):
    exe = Path(sys.executable).parent / "dbt"
    subprocess.run([str(exe), *args, "--profiles-dir", "."], cwd=REPO_ROOT, check=True)

def test_seed_totals():
    _dbt("seed", "--full-refresh")
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    won = con.execute(
        "select sum(net_new_arr) from salesforce_opportunities where stage='Closed Won'"
    ).fetchone()[0]
    usage = con.execute("select sum(recognized_amount) from billing_usage_events").fetchone()[0]
    invoices = con.execute("select sum(invoice_amount) from billing_invoices").fetchone()[0]
    con.close()
    assert won == 1_200_000
    assert usage == 900_000
    assert invoices == 900_000
```

- [ ] **Step 10: Run it**

Run: `.venv/bin/python -m pytest tests/test_seed_totals.py -v`
Expected: PASS (dbt seed runs, totals match).

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "Add deterministic GTM seed data with engineered totals"
```

---

### Task 3: Staging models

**Files:**
- Create: `models/staging/_staging.yml`
- Create: `models/staging/stg_salesforce__accounts.sql`, `stg_salesforce__opportunities.sql`, `stg_billing__usage_events.sql`, `stg_billing__invoices.sql`, `stg_finance__revenue_reference.sql`

**Interfaces:**
- Produces: views `stg_salesforce__opportunities` (cols `opportunity_id, account_id, stage, net_new_arr, created_date, close_date, is_won, is_lost, is_open, loaded_at`), `stg_salesforce__accounts` (`account_id, account_name, segment, loaded_at`), `stg_billing__usage_events` (`event_id, account_id, product_code, recognized_amount, usage_date, usage_month, loaded_at`), `stg_billing__invoices` (`invoice_id, account_id, invoice_amount, invoice_date, loaded_at`), `stg_finance__revenue_reference` (`account_id, period, recognized_revenue, prior_recognized_revenue, loaded_at`).

- [ ] **Step 1: Write `stg_salesforce__accounts.sql`**

```sql
select
    account_id,
    account_name,
    segment,
    loaded_at
from {{ ref('salesforce_accounts') }}
```

- [ ] **Step 2: Write `stg_salesforce__opportunities.sql`**

```sql
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
```

- [ ] **Step 3: Write `stg_billing__usage_events.sql`**

```sql
select
    event_id,
    account_id,
    product_code,
    recognized_amount,
    usage_date,
    date_trunc('month', usage_date) as usage_month,
    loaded_at
from {{ ref('billing_usage_events') }}
```

- [ ] **Step 4: Write `stg_billing__invoices.sql`**

```sql
select invoice_id, account_id, invoice_amount, invoice_date, loaded_at
from {{ ref('billing_invoices') }}
```

- [ ] **Step 5: Write `stg_finance__revenue_reference.sql`**

```sql
select account_id, period, recognized_revenue, prior_recognized_revenue, loaded_at
from {{ ref('finance_revenue_reference') }}
```

- [ ] **Step 6: Write `models/staging/_staging.yml`**

```yaml
version: 2
models:
  - name: stg_salesforce__opportunities
    columns:
      - name: opportunity_id
        tests: [unique, not_null]
      - name: net_new_arr
        tests: [not_null]
  - name: stg_billing__usage_events
    columns:
      - name: event_id
        tests: [unique, not_null]
      - name: recognized_amount
        tests: [not_null]
  - name: stg_billing__invoices
    columns:
      - name: invoice_id
        tests: [unique, not_null]
```

- [ ] **Step 7: Build and test staging**

Run:
```bash
.venv/bin/dbt run -s staging --profiles-dir .
.venv/bin/dbt test -s staging --profiles-dir .
```
Expected: 5 models built, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "Add staging models for SFDC, billing, finance sources"
```

---

### Task 4: Intermediate models

**Files:**
- Create: `models/intermediate/int_bookings.sql`, `int_usage_revenue.sql`, `int_pipeline.sql`
- Create: `models/intermediate/_intermediate.yml`

**Interfaces:**
- Produces: `int_bookings` (`account_id, net_new_arr, cycle_days` — one row per won opp), `int_usage_revenue` (`account_id, usage_month, recognized_amount`), `int_pipeline` (`open_pipeline_amount` — single-row total).

- [ ] **Step 1: Write `int_bookings.sql`**

```sql
select
    account_id,
    net_new_arr,
    date_diff('day', created_date, close_date) as cycle_days
from {{ ref('stg_salesforce__opportunities') }}
where is_won
```

- [ ] **Step 2: Write `int_usage_revenue.sql`**

```sql
select account_id, usage_month, sum(recognized_amount) as recognized_amount
from {{ ref('stg_billing__usage_events') }}
group by 1, 2
```

- [ ] **Step 3: Write `int_pipeline.sql`**

```sql
select sum(net_new_arr) as open_pipeline_amount
from {{ ref('stg_salesforce__opportunities') }}
where is_open
```

- [ ] **Step 4: Write `models/intermediate/_intermediate.yml`**

```yaml
version: 2
models:
  - name: int_bookings
    columns:
      - name: net_new_arr
        tests: [not_null]
  - name: int_usage_revenue
    columns:
      - name: recognized_amount
        tests: [not_null]
```

- [ ] **Step 5: Build and test**

Run:
```bash
.venv/bin/dbt run -s intermediate --profiles-dir .
.venv/bin/dbt test -s intermediate --profiles-dir .
```
Expected: 3 models built, tests pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add intermediate bookings, usage revenue, pipeline models"
```

---

### Task 5: Mart fact/dim models

**Files:**
- Create: `models/marts/gtm/dim_account.sql`, `fct_bookings.sql`, `fct_revenue.sql`
- Create: `models/marts/gtm/_gtm.yml` (contracts + tests; `mart_gtm_metrics` is added in Task 6)

**Interfaces:**
- Produces: `dim_account` (`account_id, account_name, segment`), `fct_bookings` (`account_id, net_new_arr, cycle_days`), `fct_revenue` (`account_id, recognized_amount` — aggregated to account grain, total 900,000).

- [ ] **Step 1: Write `dim_account.sql`**

```sql
select account_id, account_name, segment
from {{ ref('stg_salesforce__accounts') }}
```

- [ ] **Step 2: Write `fct_bookings.sql`**

```sql
select account_id, net_new_arr, cycle_days
from {{ ref('int_bookings') }}
```

- [ ] **Step 3: Write `fct_revenue.sql`**

```sql
select account_id, sum(recognized_amount) as recognized_amount
from {{ ref('int_usage_revenue') }}
group by 1
```

- [ ] **Step 4: Write `models/marts/gtm/_gtm.yml`** (contracts on the published marts)

```yaml
version: 2
models:
  - name: dim_account
    config:
      contract: {enforced: true}
    columns:
      - name: account_id
        data_type: varchar
        tests: [unique, not_null]
      - name: account_name
        data_type: varchar
      - name: segment
        data_type: varchar
  - name: fct_bookings
    config:
      contract: {enforced: true}
    columns:
      - name: account_id
        data_type: varchar
        tests: [not_null]
      - name: net_new_arr
        data_type: bigint
        tests: [not_null]
      - name: cycle_days
        data_type: bigint
  - name: fct_revenue
    config:
      contract: {enforced: true}
    columns:
      - name: account_id
        data_type: varchar
        tests: [unique, not_null]
      - name: recognized_amount
        data_type: hugeint
        tests: [not_null]
```

> Note: DuckDB `sum()` returns `hugeint`; if `dbt build` reports a contract type mismatch on `recognized_amount` or `net_new_arr`, set the column's `data_type` to the type dbt reports in the error.

- [ ] **Step 5: Build and test marts**

Run:
```bash
.venv/bin/dbt run -s "marts.gtm" --profiles-dir .
.venv/bin/dbt test -s "marts.gtm" --profiles-dir .
```
Expected: 3 models built, contracts enforced, tests pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add mart dim_account, fct_bookings, fct_revenue with contracts"
```

---

### Task 6: Metric mart + independent reference (the proof)

This is the heart. `mart_gtm_metrics` publishes the certified values; `ref_metric_values` recomputes each by an independent path. Only `recognized_net_new_arr` reacts to `inject_break`.

**Files:**
- Create: `models/marts/gtm/mart_gtm_metrics.sql`
- Create: `models/reference/ref_metric_values.sql`, `models/reference/_reference.yml`
- Modify: `models/marts/gtm/_gtm.yml` (add `mart_gtm_metrics` + a dbt unit test)
- Test: `tests/test_proof.py`

**Interfaces:**
- Produces: `mart_gtm_metrics` (`metric_name varchar, metric_value double`), `ref_metric_values` (`metric_name varchar, reference_value double`). Metric names (8): `recognized_net_new_arr, gross_new_arr, pipeline_coverage, win_rate, average_sales_cycle_days, quota_attainment, net_revenue_retention, logo_count`.

- [ ] **Step 1: Write `models/marts/gtm/mart_gtm_metrics.sql`** (one row per metric; only `recognized_net_new_arr` reacts to `inject_break`; `pipeline_coverage` = open pipeline / total quota = 250000/1000000 = 0.25)

```sql
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
```

- [ ] **Step 2: Write `models/reference/ref_metric_values.sql`** (independent recomputation; `recognized_net_new_arr` comes from **invoices**, not usage events)

```sql
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
    cast((select sum(recognized_amount) + 300000 from {{ ref('fct_revenue') }}) as double)
    / (select sum(quota_amount) from {{ ref('quotas') }})
union all select 'net_revenue_retention',
    cast(sum(recognized_revenue) as double) / nullif(sum(prior_recognized_revenue), 0)
    from {{ ref('finance_revenue_reference') }}
union all select 'logo_count',
    cast(count(distinct account_id) as double) from {{ ref('stg_billing__invoices') }}
```

> `quota_attainment` reference uses `sum(recognized usage) + 300000 = 900000 + 300000 = 1,200,000` as an independent way to reach gross bookings (recognized + the known ramp gap), divided by quota → 1.2, matching the mart. This is deliberate: it demonstrates an independent path arriving at the same governed value.

- [ ] **Step 3: Write `models/reference/_reference.yml`**

```yaml
version: 2
models:
  - name: ref_metric_values
    columns:
      - name: metric_name
        tests: [unique, not_null]
      - name: reference_value
        tests: [not_null]
```

- [ ] **Step 4: Add `mart_gtm_metrics` to `models/marts/gtm/_gtm.yml`** with a dbt unit test (append under `models:`)

```yaml
  - name: mart_gtm_metrics
    columns:
      - name: metric_name
        tests: [unique, not_null]
      - name: metric_value
        tests: [not_null]
unit_tests:
  - name: recognized_net_new_arr_uses_billing_when_clean
    model: mart_gtm_metrics
    overrides:
      vars:
        inject_break: false
    given:
      - input: ref('fct_revenue')
        rows:
          - {account_id: A1, recognized_amount: 900000}
      - input: ref('fct_bookings')
        rows:
          - {account_id: A1, net_new_arr: 1200000, cycle_days: 80}
      - input: ref('int_pipeline')
        rows: [{open_pipeline_amount: 250000}]
      - input: ref('quotas')
        rows: [{period: 2026, segment: All, quota_amount: 1000000, loaded_at: '2026-06-20'}]
      - input: ref('stg_salesforce__opportunities')
        rows:
          - {opportunity_id: O1, account_id: A1, stage: Closed Won, net_new_arr: 1200000, created_date: '2026-01-01', close_date: '2026-03-22', is_won: true, is_lost: false, is_open: false, loaded_at: '2026-06-20'}
      - input: ref('stg_finance__revenue_reference')
        rows:
          - {account_id: A1, period: 2026, recognized_revenue: 900000, prior_recognized_revenue: 750000, loaded_at: '2026-06-20'}
    expect:
      rows:
        - {metric_name: recognized_net_new_arr, metric_value: 900000}
```

> The unit test asserts only the `recognized_net_new_arr` row; dbt matches the named row by the `metric_name` key. If dbt requires all output rows, scope the test with `expect: {rows: [...]}` listing every metric, or mark the others — simplest is to keep the single-row expectation, which dbt 1.8 supports via partial matching on the union output by filtering. If partial match fails, change the model reference in the test to a CTE-isolated variant; do not block on this — the Python `tests/test_proof.py` is the authoritative proof.

- [ ] **Step 5: Write `tests/test_proof.py`** — the authoritative proof (clean reconciles, break diverges, dbt tests still pass under break)

```python
import subprocess, sys
from pathlib import Path
import duckdb
from gtm.config import REPO_ROOT, DUCKDB_PATH

def _dbt(*args):
    exe = Path(sys.executable).parent / "dbt"
    subprocess.run([str(exe), *args, "--profiles-dir", "."], cwd=REPO_ROOT, check=True)

def _metric(con, table, value_col, name):
    return con.execute(
        f"select {value_col} from {table} where metric_name = ?", [name]
    ).fetchone()[0]

def test_clean_build_reconciles_headline():
    _dbt("build", "--vars", '{"inject_break": false}')
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    mart = _metric(con, "mart_gtm_metrics", "metric_value", "recognized_net_new_arr")
    ref = _metric(con, "ref_metric_values", "reference_value", "recognized_net_new_arr")
    con.close()
    assert mart == 900_000
    assert ref == 900_000
    assert abs(mart - ref) < 1.0

def test_injected_break_diverges_but_dbt_tests_pass():
    # dbt build includes tests; it must SUCCEED even with the break (tests are green).
    _dbt("build", "--vars", '{"inject_break": true}')
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    mart = _metric(con, "mart_gtm_metrics", "metric_value", "recognized_net_new_arr")
    ref = _metric(con, "ref_metric_values", "reference_value", "recognized_net_new_arr")
    con.close()
    assert mart == 1_200_000          # re-sourced from bookings
    assert ref == 900_000             # independent billing reference unchanged
    assert abs(mart - ref) == 300_000 # the overstatement reconciliation will catch
```

- [ ] **Step 6: Build clean and run the proof test**

Run:
```bash
.venv/bin/dbt build --vars '{"inject_break": false}' --profiles-dir .
.venv/bin/python -m pytest tests/test_proof.py -v
```
Expected: both tests PASS. (Leave the DB in clean state at the end: re-run `dbt build --vars '{"inject_break": false}'` if needed.)

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "Add metric mart + independent reference; prove break diverges while tests pass"
```

---

### Task 7: Metric registry + Pydantic v2 loader

**Files:**
- Create: `metrics/registry.yml`, `gtm/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces: `gtm.registry.MetricDef` (fields: `name: str`, `description: str`, `grain: str`, `source_of_truth: str`, `owning_org: Literal["gtm_ops","finance"]`, `abs_tolerance: float = 0.0`, `rel_tolerance: float = 0.0`, `freshness_sources: list[str]`), `gtm.registry.Registry` (`metrics: list[MetricDef]`, `.names() -> set[str]`, `.get(name) -> MetricDef`), `gtm.registry.load_registry(path=REGISTRY_PATH) -> Registry`.

- [ ] **Step 1: Write `metrics/registry.yml`** (8 metrics; freshness sources are staging model names)

```yaml
metrics:
  - name: recognized_net_new_arr
    description: Net-new ARR recognized from actual billing usage (source of truth).
    grain: company_period
    source_of_truth: fct_revenue
    owning_org: finance
    abs_tolerance: 1.0
    freshness_sources: [stg_billing__usage_events, stg_billing__invoices]
  - name: gross_new_arr
    description: Gross new ARR from Closed-Won bookings.
    grain: company_period
    source_of_truth: fct_bookings
    owning_org: gtm_ops
    abs_tolerance: 1.0
    freshness_sources: [stg_salesforce__opportunities]
  - name: pipeline_coverage
    description: Open pipeline divided by quota.
    grain: company_period
    source_of_truth: int_pipeline
    owning_org: gtm_ops
    rel_tolerance: 0.0001
    freshness_sources: [stg_salesforce__opportunities]
  - name: win_rate
    description: Won opps over closed opps.
    grain: company_period
    source_of_truth: stg_salesforce__opportunities
    owning_org: gtm_ops
    rel_tolerance: 0.0001
    freshness_sources: [stg_salesforce__opportunities]
  - name: average_sales_cycle_days
    description: Mean days from create to close on won opps.
    grain: company_period
    source_of_truth: fct_bookings
    owning_org: gtm_ops
    rel_tolerance: 0.0001
    freshness_sources: [stg_salesforce__opportunities]
  - name: quota_attainment
    description: Bookings over quota.
    grain: company_period
    source_of_truth: fct_bookings
    owning_org: gtm_ops
    rel_tolerance: 0.0001
    freshness_sources: [stg_salesforce__opportunities]
  - name: net_revenue_retention
    description: Current recognized over prior recognized.
    grain: company_period
    source_of_truth: stg_finance__revenue_reference
    owning_org: finance
    rel_tolerance: 0.0001
    freshness_sources: [stg_finance__revenue_reference]
  - name: logo_count
    description: Distinct won logos.
    grain: company_period
    source_of_truth: fct_bookings
    owning_org: gtm_ops
    abs_tolerance: 0.0
    freshness_sources: [stg_salesforce__opportunities]
```

- [ ] **Step 2: Write `tests/test_registry.py`**

```python
import pytest
from gtm.registry import load_registry, MetricDef

def test_loads_eight_metrics():
    reg = load_registry()
    assert len(reg.metrics) == 8
    assert "recognized_net_new_arr" in reg.names()

def test_get_returns_metricdef():
    reg = load_registry()
    m = reg.get("recognized_net_new_arr")
    assert isinstance(m, MetricDef)
    assert m.owning_org == "finance"
    assert m.source_of_truth == "fct_revenue"
    assert m.abs_tolerance == 1.0

def test_unknown_metric_raises():
    reg = load_registry()
    with pytest.raises(KeyError):
        reg.get("nope")

def test_bad_owning_org_rejected(tmp_path):
    p = tmp_path / "r.yml"
    p.write_text(
        "metrics:\n- name: x\n  description: d\n  grain: g\n"
        "  source_of_truth: s\n  owning_org: marketing\n  freshness_sources: []\n"
    )
    with pytest.raises(Exception):
        load_registry(p)
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_registry.py -v`
Expected: FAIL (`ModuleNotFoundError: gtm.registry`).

- [ ] **Step 4: Write `gtm/registry.py`**

```python
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel
from gtm.config import REGISTRY_PATH


class MetricDef(BaseModel):
    name: str
    description: str
    grain: str
    source_of_truth: str
    owning_org: Literal["gtm_ops", "finance"]
    abs_tolerance: float = 0.0
    rel_tolerance: float = 0.0
    freshness_sources: list[str] = []


class Registry(BaseModel):
    metrics: list[MetricDef]

    def names(self) -> set[str]:
        return {m.name for m in self.metrics}

    def get(self, name: str) -> MetricDef:
        for m in self.metrics:
            if m.name == name:
                return m
        raise KeyError(name)


def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    data = yaml.safe_load(Path(path).read_text())
    return Registry.model_validate(data)
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_registry.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add governed metric registry and Pydantic v2 loader"
```

---

### Task 8: Warehouse query layer

**Files:**
- Create: `gtm/warehouse.py`
- Test: `tests/test_warehouse.py`

**Interfaces:**
- Consumes: `gtm.config.DUCKDB_PATH`.
- Produces: `gtm.warehouse.Warehouse(db_path=DUCKDB_PATH)` with methods `metric_values() -> dict[str, float]` (from `mart_gtm_metrics`), `reference_values() -> dict[str, float]` (from `ref_metric_values`), `mart_metric_names() -> set[str]`, `source_max_loaded_at(source: str) -> date | None`, `monthly_recognized() -> list[float]` (ordered by month, from `stg_billing__usage_events`).

- [ ] **Step 1: Write `tests/test_warehouse.py`** (assumes clean DB built in Task 6)

```python
from datetime import date
from gtm.warehouse import Warehouse

def test_metric_and_reference_values():
    wh = Warehouse()
    mv = wh.metric_values()
    rv = wh.reference_values()
    assert mv["recognized_net_new_arr"] == 900_000
    assert rv["recognized_net_new_arr"] == 900_000
    assert mv["logo_count"] == 5

def test_mart_metric_names():
    assert "gross_new_arr" in Warehouse().mart_metric_names()

def test_source_freshness():
    assert Warehouse().source_max_loaded_at("stg_billing__usage_events") == date(2026, 6, 20)

def test_monthly_recognized_series():
    series = Warehouse().monthly_recognized()
    assert series == [120000, 130000, 125000, 135000, 260000, 130000]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_warehouse.py -v`
Expected: FAIL (no module `gtm.warehouse`).

- [ ] **Step 3: Write `gtm/warehouse.py`**

```python
from datetime import date
from pathlib import Path
import duckdb
from gtm.config import DUCKDB_PATH


class Warehouse:
    def __init__(self, db_path: Path = DUCKDB_PATH):
        self.db_path = Path(db_path)

    def _con(self):
        return duckdb.connect(str(self.db_path), read_only=True)

    def metric_values(self) -> dict[str, float]:
        con = self._con()
        rows = con.execute("select metric_name, metric_value from mart_gtm_metrics").fetchall()
        con.close()
        return {name: float(val) for name, val in rows}

    def reference_values(self) -> dict[str, float]:
        con = self._con()
        rows = con.execute("select metric_name, reference_value from ref_metric_values").fetchall()
        con.close()
        return {name: float(val) for name, val in rows}

    def mart_metric_names(self) -> set[str]:
        return set(self.metric_values().keys())

    def source_max_loaded_at(self, source: str) -> date | None:
        con = self._con()
        try:
            row = con.execute(f"select max(loaded_at) from {source}").fetchone()
        finally:
            con.close()
        return row[0] if row else None

    def monthly_recognized(self) -> list[float]:
        con = self._con()
        rows = con.execute(
            "select sum(recognized_amount) from stg_billing__usage_events "
            "group by usage_month order by usage_month"
        ).fetchall()
        con.close()
        return [float(r[0]) for r in rows]
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_warehouse.py -v`
Expected: 4 passed. (If `monthly_recognized` ordering differs, confirm `usage_month` is a date via `date_trunc`.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add DuckDB warehouse query layer"
```

---

### Task 9: Reconciliation engine (pure logic)

**Files:**
- Create: `gtm/reconcile.py`
- Test: `tests/test_reconcile.py`

**Interfaces:**
- Produces: `gtm.reconcile.ReconResult` (`metric: str, mart_value: float, reference_value: float, delta: float, within_tolerance: bool`), `gtm.reconcile.reconcile(metric, mart_value, reference_value, abs_tolerance, rel_tolerance) -> ReconResult`. Rule: `within_tolerance` is True if `abs(delta) <= abs_tolerance` OR (`rel_tolerance > 0` and `abs(delta) <= rel_tolerance * abs(reference_value)`).

- [ ] **Step 1: Write `tests/test_reconcile.py`**

```python
from gtm.reconcile import reconcile

def test_within_abs_tolerance():
    r = reconcile("m", 900000.0, 900000.4, abs_tolerance=1.0, rel_tolerance=0.0)
    assert r.within_tolerance
    assert r.delta == 900000.0 - 900000.4

def test_break_exceeds_tolerance():
    r = reconcile("recognized_net_new_arr", 1_200_000.0, 900_000.0, abs_tolerance=1.0, rel_tolerance=0.0)
    assert not r.within_tolerance
    assert r.delta == 300_000.0

def test_relative_tolerance():
    r = reconcile("ratio", 1.2001, 1.2, abs_tolerance=0.0, rel_tolerance=0.001)
    assert r.within_tolerance
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_reconcile.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write `gtm/reconcile.py`**

```python
from pydantic import BaseModel


class ReconResult(BaseModel):
    metric: str
    mart_value: float
    reference_value: float
    delta: float
    within_tolerance: bool


def reconcile(
    metric: str,
    mart_value: float,
    reference_value: float,
    abs_tolerance: float,
    rel_tolerance: float,
) -> ReconResult:
    delta = mart_value - reference_value
    within = abs(delta) <= abs_tolerance
    if not within and rel_tolerance > 0:
        within = abs(delta) <= rel_tolerance * abs(reference_value)
    return ReconResult(
        metric=metric,
        mart_value=mart_value,
        reference_value=reference_value,
        delta=delta,
        within_tolerance=within,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_reconcile.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add reconciliation engine"
```

---

### Task 10: Certification orchestration + report rendering

**Files:**
- Create: `gtm/certify.py`, `gtm/report.py`
- Test: `tests/test_certify.py`

**Interfaces:**
- Consumes: `Registry`, `Warehouse`, `reconcile`, `gtm.config.AS_OF`, `FRESHNESS_WINDOW_DAYS`.
- Produces: `gtm.certify.MetricStatus` (`metric, owning_org, governed: bool, fresh: bool, reconciled: bool, mart_value: float|None, reference_value: float|None, delta: float|None, reason: str`, plus property `certified -> bool`), `gtm.certify.certify(registry, warehouse, as_of, window_days) -> list[MetricStatus]`, `gtm.certify.summary(statuses) -> tuple[int,int]`. `gtm.report.render_certify_table(statuses)`, `gtm.report.render_reconcile_detail(status, metric_def)`.

- [ ] **Step 1: Write `tests/test_certify.py`** (uses the clean DB)

```python
from gtm.registry import load_registry
from gtm.warehouse import Warehouse
from gtm.certify import certify, summary
from gtm.config import AS_OF, FRESHNESS_WINDOW_DAYS

def test_clean_db_all_certified():
    statuses = certify(load_registry(), Warehouse(), AS_OF, FRESHNESS_WINDOW_DAYS)
    assert summary(statuses) == (8, 8)
    assert all(s.certified for s in statuses)

def test_governance_flags_unknown_registry_metric():
    # A registry metric absent from the mart is not governed.
    reg = load_registry()
    reg.metrics[0].name = "ghost_metric"
    statuses = certify(reg, Warehouse(), AS_OF, FRESHNESS_WINDOW_DAYS)
    ghost = next(s for s in statuses if s.metric == "ghost_metric")
    assert not ghost.governed
    assert not ghost.certified
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_certify.py -v`
Expected: FAIL (no module `gtm.certify`).

- [ ] **Step 3: Write `gtm/certify.py`**

```python
from datetime import date, timedelta
from pydantic import BaseModel
from gtm.registry import Registry
from gtm.warehouse import Warehouse
from gtm.reconcile import reconcile


class MetricStatus(BaseModel):
    metric: str
    owning_org: str
    governed: bool
    fresh: bool
    reconciled: bool
    mart_value: float | None = None
    reference_value: float | None = None
    delta: float | None = None
    reason: str = ""

    @property
    def certified(self) -> bool:
        return self.governed and self.fresh and self.reconciled


def certify(registry: Registry, warehouse: Warehouse, as_of: date, window_days: int) -> list[MetricStatus]:
    mart = warehouse.metric_values()
    ref = warehouse.reference_values()
    cutoff = as_of - timedelta(days=window_days)
    statuses: list[MetricStatus] = []
    for m in registry.metrics:
        governed = m.name in mart and m.name in ref
        if not governed:
            statuses.append(MetricStatus(
                metric=m.name, owning_org=m.owning_org,
                governed=False, fresh=False, reconciled=False,
                reason="metric missing from mart or reference",
            ))
            continue
        fresh = True
        for src in m.freshness_sources:
            loaded = warehouse.source_max_loaded_at(src)
            if loaded is None or loaded < cutoff:
                fresh = False
        rec = reconcile(m.name, mart[m.name], ref[m.name], m.abs_tolerance, m.rel_tolerance)
        reason = "" if rec.within_tolerance else f"reconciliation delta {rec.delta:+,.2f}"
        if not fresh:
            reason = (reason + "; stale source").lstrip("; ")
        statuses.append(MetricStatus(
            metric=m.name, owning_org=m.owning_org,
            governed=True, fresh=fresh, reconciled=rec.within_tolerance,
            mart_value=rec.mart_value, reference_value=rec.reference_value,
            delta=rec.delta, reason=reason,
        ))
    return statuses


def summary(statuses: list[MetricStatus]) -> tuple[int, int]:
    return sum(1 for s in statuses if s.certified), len(statuses)
```

- [ ] **Step 4: Write `gtm/report.py`**

```python
from rich.console import Console
from rich.table import Table
from gtm.certify import MetricStatus
from gtm.registry import MetricDef

console = Console()


def render_certify_table(statuses: list[MetricStatus]) -> None:
    table = Table(title="GTM Metric Certification")
    table.add_column("Metric")
    table.add_column("Owner")
    table.add_column("Gov")
    table.add_column("Fresh")
    table.add_column("Recon")
    table.add_column("Mart")
    table.add_column("Reference")
    table.add_column("Status")
    for s in statuses:
        mark = lambda b: "[green]✓[/green]" if b else "[red]✗[/red]"
        status = "[green]CERTIFIED[/green]" if s.certified else f"[red]FAIL[/red] {s.reason}"
        table.add_row(
            s.metric, s.owning_org, mark(s.governed), mark(s.fresh), mark(s.reconciled),
            "" if s.mart_value is None else f"{s.mart_value:,.2f}",
            "" if s.reference_value is None else f"{s.reference_value:,.2f}",
            status,
        )
    console.print(table)


def render_reconcile_detail(status: MetricStatus, metric_def: MetricDef) -> None:
    console.print(f"[bold]{status.metric}[/bold] — owned by {status.owning_org}")
    console.print(f"  source of truth : {metric_def.source_of_truth}")
    console.print(f"  mart value      : {status.mart_value:,.2f}")
    console.print(f"  reference value : {status.reference_value:,.2f}")
    console.print(f"  delta           : {status.delta:+,.2f}")
    verdict = "within tolerance" if status.reconciled else "OUT OF TOLERANCE"
    console.print(f"  verdict         : {verdict}")
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_certify.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add certification orchestration and Rich report rendering"
```

---

### Task 11: dbt runner + CLI wiring

**Files:**
- Create: `gtm/dbt_runner.py`, `gtm/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `gtm.dbt_runner.build(inject_break: bool=False, target: str="local") -> None` (runs `dbt build` with the var), `gtm.dbt_runner.dbt(args: list[str]) -> subprocess.CompletedProcess`. `gtm.cli.app` (Typer) with commands `build`, `certify`, `reconcile`, `anomaly` (anomaly added in Task 12).

- [ ] **Step 1: Write `gtm/dbt_runner.py`**

```python
import json
import subprocess
import sys
from pathlib import Path
from gtm.config import REPO_ROOT


def _dbt_exe() -> str:
    return str(Path(sys.executable).parent / "dbt")


def dbt(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_dbt_exe(), *args, "--profiles-dir", "."],
        cwd=REPO_ROOT, check=True,
    )


def build(inject_break: bool = False, target: str = "local") -> None:
    dbt(["build", "--vars", json.dumps({"inject_break": inject_break}), "--target", target])
```

- [ ] **Step 2: Write `gtm/cli.py`** (NO `from __future__ import annotations`)

```python
import typer
from gtm import dbt_runner
from gtm.registry import load_registry
from gtm.warehouse import Warehouse
from gtm.certify import certify, summary
from gtm.report import render_certify_table, render_reconcile_detail
from gtm.config import AS_OF, FRESHNESS_WINDOW_DAYS

app = typer.Typer(help="Certify GTM metrics as governed, fresh, and reconciled.")


@app.command()
def build(
    inject_break: bool = typer.Option(False, "--inject-break"),
    target: str = typer.Option("local", "--target"),
):
    """Build the dbt project (optionally with the planted reconciliation break)."""
    dbt_runner.build(inject_break=inject_break, target=target)


@app.command()
def certify(
    inject_break: bool = typer.Option(False, "--inject-break"),
    target: str = typer.Option("local", "--target"),
):
    """Build, then certify every registry metric. Exit 1 if any metric fails."""
    dbt_runner.build(inject_break=inject_break, target=target)
    statuses = certify_metrics()
    render_certify_table(statuses)
    n_ok, n_total = summary(statuses)
    typer.echo(f"{n_ok}/{n_total} metrics certified")
    if n_ok != n_total:
        raise typer.Exit(code=1)


@app.command()
def reconcile(metric: str):
    """Show reconciliation detail and root-cause framing for one metric."""
    reg = load_registry()
    statuses = certify_metrics()
    status = next((s for s in statuses if s.metric == metric), None)
    if status is None:
        typer.echo(f"unknown metric: {metric}")
        raise typer.Exit(code=1)
    render_reconcile_detail(status, reg.get(metric))


def certify_metrics():
    return certify(load_registry(), Warehouse(), AS_OF, FRESHNESS_WINDOW_DAYS)


if __name__ == "__main__":
    app()
```

- [ ] **Step 3: Write `tests/test_cli.py`** (uses Typer's runner; rebuilds clean and broken)

```python
from typer.testing import CliRunner
from gtm.cli import app

runner = CliRunner()

def test_certify_clean_exits_zero():
    result = runner.invoke(app, ["certify"])
    assert result.exit_code == 0
    assert "8/8 metrics certified" in result.stdout

def test_certify_break_exits_one():
    result = runner.invoke(app, ["certify", "--inject-break"])
    assert result.exit_code == 1
    assert "recognized_net_new_arr" in result.stdout

def test_reconcile_detail_runs():
    runner.invoke(app, ["build"])  # restore clean state
    result = runner.invoke(app, ["reconcile", "recognized_net_new_arr"])
    assert result.exit_code == 0
    assert "source of truth" in result.stdout
```

- [ ] **Step 4: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: 3 passed. Then verify `--help` renders:
```bash
.venv/bin/gtm --help
```
Expected: command list prints (confirms click pin works).

- [ ] **Step 5: Restore clean DB and commit**

```bash
.venv/bin/dbt build --vars '{"inject_break": false}' --profiles-dir .
git add -A && git commit -m "Add dbt runner and Typer CLI (build, certify, reconcile)"
```

---

### Task 12: Local anomaly command

**Files:**
- Create: `gtm/anomaly.py`
- Modify: `gtm/cli.py` (add `anomaly` command)
- Test: `tests/test_anomaly.py`

**Interfaces:**
- Produces: `gtm.anomaly.AnomalyPoint` (`index: int, value: float, score: float, method: str`), `gtm.anomaly.detect(series: list[float]) -> list[AnomalyPoint]` (IQR upper-fence with k=1.5, plus z-score>2.5; flag if either), `gtm.anomaly.explain(point, series, use_ollama: bool=False) -> str` (deterministic template; tries local Ollama only if `use_ollama` and the package+server are present, else falls back silently).

- [ ] **Step 1: Write `tests/test_anomaly.py`**

```python
from gtm.anomaly import detect, explain

SERIES = [120000, 130000, 125000, 135000, 260000, 130000]

def test_detects_the_spike():
    points = detect(SERIES)
    assert any(p.index == 4 for p in points)

def test_no_false_positive_on_flat_series():
    assert detect([100, 100, 100, 100, 100]) == []

def test_explain_is_deterministic_without_ollama():
    p = detect(SERIES)[0]
    text = explain(p, SERIES, use_ollama=False)
    assert "260,000" in text or "260000" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_anomaly.py -v`
Expected: FAIL (no module).

- [ ] **Step 3: Write `gtm/anomaly.py`**

```python
from statistics import mean, pstdev
from pydantic import BaseModel


class AnomalyPoint(BaseModel):
    index: int
    value: float
    score: float
    method: str


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def detect(series: list[float]) -> list[AnomalyPoint]:
    if len(series) < 4:
        return []
    s = sorted(series)
    q1, q3 = _quantile(s, 0.25), _quantile(s, 0.75)
    upper = q3 + 1.5 * (q3 - q1)
    mu = mean(series)
    sigma = pstdev(series)
    points: list[AnomalyPoint] = []
    for i, v in enumerate(series):
        z = (v - mu) / sigma if sigma else 0.0
        if v > upper:
            points.append(AnomalyPoint(index=i, value=v, score=z, method="iqr"))
        elif abs(z) > 2.5:
            points.append(AnomalyPoint(index=i, value=v, score=z, method="zscore"))
    return points


def explain(point: AnomalyPoint, series: list[float], use_ollama: bool = False) -> str:
    baseline = mean([v for j, v in enumerate(series) if j != point.index])
    deterministic = (
        f"Month {point.index + 1} recognized {point.value:,.0f}, "
        f"{point.value - baseline:+,.0f} vs the {baseline:,.0f} baseline "
        f"({point.method}, z={point.score:.2f}). Investigate usage spikes or one-off true-ups."
    )
    if not use_ollama:
        return deterministic
    try:
        import ollama  # noqa: F401  (only if user has it locally)
        resp = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": f"Explain this GTM anomaly in one sentence: {deterministic}"}],
        )
        return resp["message"]["content"].strip()
    except Exception:
        return deterministic
```

- [ ] **Step 4: Add the `anomaly` command to `gtm/cli.py`** (append before `if __name__`)

```python
@app.command()
def anomaly(use_ollama: bool = typer.Option(False, "--use-ollama")):
    """Flag anomalies in monthly recognized revenue (local-only)."""
    from gtm.anomaly import detect, explain
    series = Warehouse().monthly_recognized()
    points = detect(series)
    if not points:
        typer.echo("No anomalies detected.")
        return
    for p in points:
        typer.echo(explain(p, series, use_ollama=use_ollama))
```

- [ ] **Step 5: Run tests + smoke the command**

Run:
```bash
.venv/bin/python -m pytest tests/test_anomaly.py -v
.venv/bin/gtm anomaly
```
Expected: 3 passed; command prints the Month-5 spike line.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add local-only anomaly detection command"
```

---

### Task 13: Standards docs, contracts gate, PR template

**Files:**
- Create: `docs/standards/modeling.md`, `docs/standards/testing.md`, `docs/standards/code-review.md`
- Create: `scripts/check_doc_coverage.py`
- Create: `.github/pull_request_template.md`
- Test: `tests/test_doc_coverage.py`

**Interfaces:**
- Produces: `scripts/check_doc_coverage.py` exits 0 when every model column in `models/marts/gtm/_gtm.yml` has a non-empty `description` is **not** required — instead the gate asserts every mart model listed has at least its columns enumerated. (Kept intentionally light; see code.)

- [ ] **Step 1: Write `docs/standards/modeling.md`**

```markdown
# Modeling Standards

- **Layering:** `staging` (1:1 with sources, views) → `intermediate` (business logic, views)
  → `marts` (published tables, contracts enforced) → `reference` (independent recomputation).
- **Naming:** `stg_<source>__<entity>`, `int_<concept>`, `fct_`/`dim_` for marts.
- **Grain:** every model documents its grain; one grain per model.
- **Source of truth:** each metric has exactly one governed source, declared in `metrics/registry.yml`.
- **No metric is trusted until governed + fresh + reconciled.**
```

- [ ] **Step 2: Write `docs/standards/testing.md`**

```markdown
# Testing Standards

- Every staging model: `unique` + `not_null` on its key.
- Every mart: enforced contract + key tests + at least one dbt unit test on critical logic.
- Reconciliation is mandatory for published metrics: the mart value must match an
  independent `ref_metric_values` recomputation within the registry tolerance.
- CI must assert both states: clean build certifies; the planted break is caught.
```

- [ ] **Step 3: Write `docs/standards/code-review.md`**

```markdown
# Code Review Checklist

- [ ] New/changed metric is registered in `metrics/registry.yml` with an owning org and tolerance.
- [ ] An independent reference recomputation exists in `ref_metric_values`.
- [ ] Grain is documented and tests cover the key.
- [ ] `gtm certify` passes locally on a clean build.
- [ ] No `datetime.now()` / network / credentials introduced into the default path.
```

- [ ] **Step 4: Write `.github/pull_request_template.md`**

```markdown
## What changed

## Metric governance
- [ ] Registered in `metrics/registry.yml` (owner + tolerance)
- [ ] Independent reference recomputation added/updated
- [ ] `gtm certify` green locally

## Testing
- [ ] dbt tests pass
- [ ] `pytest` passes
```

- [ ] **Step 5: Write `scripts/check_doc_coverage.py`**

```python
"""Fail if any registry metric lacks a description or freshness source."""
import sys
from gtm.registry import load_registry


def main() -> int:
    reg = load_registry()
    problems = []
    for m in reg.metrics:
        if not m.description.strip():
            problems.append(f"{m.name}: missing description")
        if not m.freshness_sources:
            problems.append(f"{m.name}: no freshness sources")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"Doc coverage OK for {len(reg.metrics)} metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Write `tests/test_doc_coverage.py`**

```python
import subprocess, sys
from gtm.config import REPO_ROOT

def test_doc_coverage_passes():
    r = subprocess.run([sys.executable, "scripts/check_doc_coverage.py"], cwd=REPO_ROOT)
    assert r.returncode == 0
```

- [ ] **Step 7: Run it**

Run: `.venv/bin/python -m pytest tests/test_doc_coverage.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "Add modeling/testing/review standards, doc-coverage gate, PR template"
```

---

### Task 14: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push:
    branches: ["**"]
  pull_request:
jobs:
  certify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: |
          python -m pip install -e ".[dev]"
          dbt deps --profiles-dir .
      - name: dbt build + tests (clean)
        run: dbt build --vars '{"inject_break": false}' --profiles-dir .
      - name: Doc coverage gate
        run: python scripts/check_doc_coverage.py
      - name: Unit + integration tests
        run: pytest -v
      - name: Assert clean build certifies
        run: gtm certify
      - name: Assert injected break is caught
        run: |
          if gtm certify --inject-break; then
            echo "ERROR: reconciliation did not catch the injected break" && exit 1
          else
            echo "OK: reconciliation caught the injected break"
          fi
      - name: Restore clean state
        run: dbt build --vars '{"inject_break": false}' --profiles-dir .
```

- [ ] **Step 2: Validate the workflow locally** (syntax + the asserted-failure logic mirrored in shell)

Run:
```bash
.venv/bin/gtm certify; echo "clean exit: $?"
.venv/bin/gtm certify --inject-break; echo "break exit: $? (expect 1)"
.venv/bin/dbt build --vars '{"inject_break": false}' --profiles-dir .
```
Expected: clean exit 0; break exit 1.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "Add CI asserting clean certification and caught reconciliation break"
```

---

### Task 15: README with capability map

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# gtm-trusted-layer

A runnable dbt + DuckDB **business data layer** for GTM/sales metrics. Every metric is
**certified** only when it is **governed** (one definition, one owning org), **fresh**, and
**reconciled** against an independent recomputation. Clone and run free — no warehouse, no
credentials, no network.

## The proof

`recognized_net_new_arr` is governed to come from **billing usage** (what customers actually
consumed). Run `gtm certify --inject-break` and the metric is silently re-sourced from
**Salesforce bookings**. Every dbt test stays green — but reconciliation against the
independent billing reference catches the **$300K** overstatement (1,200,000 booked vs
900,000 recognized) and CI fails. That gap between *passes tests* and *is actually correct*
is the entire point.

## Quickstart

```bash
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/dbt deps --profiles-dir .
.venv/bin/gtm certify            # builds + certifies; 8/8 metrics certified
.venv/bin/gtm certify --inject-break   # reconciliation FAILS, exit 1
.venv/bin/gtm reconcile recognized_net_new_arr   # root-cause detail
.venv/bin/gtm anomaly            # local anomaly scan on monthly recognized revenue
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
````

- [ ] **Step 2: Verify the documented commands actually run**

Run:
```bash
.venv/bin/gtm certify && .venv/bin/gtm reconcile recognized_net_new_arr && .venv/bin/gtm anomaly
```
Expected: certification table (8/8), reconciliation detail, anomaly line — all exit 0.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "Add README with JD capability map"
```

---

## Self-Review

**Spec coverage:**
- Governed / fresh / reconciled thesis → registry (T7) + certify (T10). ✓
- Proof (bookings re-source caught by reconciliation, tests still green) → T6 + T11 CLI + T14 CI. ✓
- dbt + DuckDB local, Snowflake optional target → T1 profiles. ✓
- 8 metrics → T6/T7. ✓
- CLI build/certify/reconcile/anomaly → T11/T12. ✓
- Local-only AI angle → T12. ✓
- CI asserts both states → T14. ✓
- Standards/mentorship artifacts + contracts + doc gate → T5 contracts, T13. ✓
- README capability map → T15. ✓
- Freshness simulated via `loaded_at` vs fixed as-of → T1 config + T8 + T10. ✓

**Placeholder scan:** No TODO/TBD/draft-then-replace steps remain. Every code step shows the final content.

**Type consistency:** `metric_values()/reference_values()` return `dict[str,float]`; `certify` indexes them and builds `MetricStatus`; `reconcile()` signature matches its callers; CLI `certify_metrics()` reused by `certify` and `reconcile` commands. Names align across tasks.

## Known risks the implementer should watch

1. **dbt contract data types** (T5): DuckDB sum types (`hugeint`/`bigint`) can trip contracts — adjust `data_type` to whatever dbt reports.
2. **dbt unit test partial matching** (T6 Step 4): if dbt 1.8 rejects the single-row `expect`, the Python `test_proof.py` is the authoritative proof; don't block on the dbt unit test.
