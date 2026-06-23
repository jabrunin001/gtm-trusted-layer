from datetime import date
from pathlib import Path
import duckdb
from gtm.config import DUCKDB_PATH


class Warehouse:
    def __init__(self, db_path: Path = DUCKDB_PATH):
        self.db_path = Path(db_path)

    def _con(self):
        return duckdb.connect(str(self.db_path), read_only=True)

    def metric_values(self) -> dict[str, float]:
        con = self._con()
        rows = con.execute("select metric_name, metric_value from mart_gtm_metrics").fetchall()
        con.close()
        return {name: float(val) for name, val in rows}

    def reference_values(self) -> dict[str, float]:
        con = self._con()
        rows = con.execute("select metric_name, reference_value from ref_metric_values").fetchall()
        con.close()
        return {name: float(val) for name, val in rows}

    def mart_metric_names(self) -> set[str]:
        return set(self.metric_values().keys())

    def source_max_loaded_at(self, source: str) -> date | None:
        con = self._con()
        try:
            row = con.execute(f"select max(loaded_at) from {source}").fetchone()
        finally:
            con.close()
        return row[0] if row else None

    def monthly_recognized(self) -> list[float]:
        con = self._con()
        rows = con.execute(
            "select sum(recognized_amount) from stg_billing__usage_events "
            "group by usage_month order by usage_month"
        ).fetchall()
        con.close()
        return [float(r[0]) for r in rows]
