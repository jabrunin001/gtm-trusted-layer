# Code Review Checklist

- [ ] New/changed metric is registered in `metrics/registry.yml` with an owning org and tolerance.
- [ ] An independent reference recomputation exists in `ref_metric_values`.
- [ ] Grain is documented and tests cover the key.
- [ ] `gtm certify` passes locally on a clean build.
- [ ] No `datetime.now()` / network / credentials introduced into the default path.
