from datetime import date
from gtm.warehouse import Warehouse

def test_metric_and_reference_values():
    wh = Warehouse()
    mv = wh.metric_values()
    rv = wh.reference_values()
    assert mv["recognized_net_new_arr"] == 900_000
    assert rv["recognized_net_new_arr"] == 900_000
    assert mv["logo_count"] == 5

def test_mart_metric_names():
    assert "gross_new_arr" in Warehouse().mart_metric_names()

def test_source_freshness():
    assert Warehouse().source_max_loaded_at("stg_billing__usage_events") == date(2026, 6, 20)

def test_monthly_recognized_series():
    series = Warehouse().monthly_recognized()
    assert series == [120000, 130000, 125000, 135000, 260000, 130000]
