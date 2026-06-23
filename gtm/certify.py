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
