# Testing Standards

- Every staging model: `unique` + `not_null` on its key.
- Every mart: enforced contract + key tests + at least one dbt unit test on critical logic.
- Reconciliation is mandatory for published metrics: the mart value must match an
  independent `ref_metric_values` recomputation within the registry tolerance.
- CI must assert both states: clean build certifies; the planted break is caught.
