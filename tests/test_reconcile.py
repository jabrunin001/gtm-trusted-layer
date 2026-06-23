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
