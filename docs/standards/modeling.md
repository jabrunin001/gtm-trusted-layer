# Modeling Standards

- **Layering:** `staging` (1:1 with sources, views) → `intermediate` (business logic, views)
  → `marts` (published tables, contracts enforced) → `reference` (independent recomputation).
- **Naming:** `stg_<source>__<entity>`, `int_<concept>`, `fct_`/`dim_` for marts.
- **Grain:** every model documents its grain; one grain per model.
- **Source of truth:** each metric has exactly one governed source, declared in `metrics/registry.yml`.
- **No metric is trusted until governed + fresh + reconciled.**
