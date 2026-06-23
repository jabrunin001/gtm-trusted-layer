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
