from datetime import date
import gtm
from gtm import config

def test_package_imports():
    assert gtm.__version__ == "0.1.0"

def test_config_constants():
    assert config.AS_OF == date(2026, 6, 22)
    assert config.FRESHNESS_WINDOW_DAYS == 7
    assert config.REPO_ROOT.name == "gtm-trusted-layer"
