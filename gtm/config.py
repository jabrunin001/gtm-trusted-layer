from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DUCKDB_PATH = REPO_ROOT / "gtm_trusted_layer.duckdb"
REGISTRY_PATH = REPO_ROOT / "metrics" / "registry.yml"
AS_OF = date(2026, 6, 22)
FRESHNESS_WINDOW_DAYS = 7
