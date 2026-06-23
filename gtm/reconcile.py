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
