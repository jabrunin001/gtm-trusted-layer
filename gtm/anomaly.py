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
        import ollama  # only if user has it locally
        resp = ollama.chat(
            model="llama3",
            messages=[{"role": "user", "content": f"Explain this GTM anomaly in one sentence: {deterministic}"}],
        )
        return resp["message"]["content"].strip()
    except Exception:
        return deterministic
