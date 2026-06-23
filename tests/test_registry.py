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
