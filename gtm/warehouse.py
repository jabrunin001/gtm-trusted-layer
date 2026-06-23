from datetime import date
from pathlib import Path
import duckdb
from gtm.config import DUCKDB_PATH


class Warehouse:
    def __init__(self, db_path: Path = DUCKDB_PATH):
        self.db_path = Path(db_path)

    def _con(self):
        return duckdb.connect(str(self.db_path), read_only=True)

    def _query(self, sql, params=None):
        con = self._con()
        try:
            return con.execute(sql, params or []).fetchall()
        finally:
            con.close()

    def metric_values(self) -> dict[str, float]:
        rows = self._query("select metric_name, metric_value from mart_gtm_metrics")
        return {name: float(val) for name, val in rows}

    def reference_values(self) -> dict[str, float]:
        rows = self._query("select metric_name, reference_value from ref_metric_values")
        return {name: float(val) for name, val in rows}

    def mart_metric_names(self) -> set[str]:
        return set(self.metric_values().keys())

    def source_max_loaded_at(self, source: str) -> date | None:
        # `source` is a registry-controlled dbt model name, not external input, so the f-string is safe.
        rows = self._query(f"select max(loaded_at) from {source}")
        row = rows[0] if rows else None
        return row[0] if row else None

    def monthly_recognized(self) -> list[float]:
        rows = self._query(
            "select sum(recognized_amount) from stg_billing__usage_events "
            "group by usage_month order by usage_month"
        )
        return [float(r[0]) for r in rows]
