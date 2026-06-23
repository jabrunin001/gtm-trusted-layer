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
