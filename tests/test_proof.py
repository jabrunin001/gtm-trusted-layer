import subprocess, sys
from pathlib import Path
import duckdb
from gtm.config import REPO_ROOT, DUCKDB_PATH

def _dbt(*args):
    exe = Path(sys.executable).parent / "dbt"
    subprocess.run([str(exe), *args, "--profiles-dir", "."], cwd=REPO_ROOT, check=True)

def _metric(con, table, value_col, name):
    return con.execute(
        f"select {value_col} from {table} where metric_name = ?", [name]
    ).fetchone()[0]

def test_clean_build_reconciles_headline():
    _dbt("build", "--vars", '{"inject_break": false}')
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    mart = _metric(con, "mart_gtm_metrics", "metric_value", "recognized_net_new_arr")
    ref = _metric(con, "ref_metric_values", "reference_value", "recognized_net_new_arr")
    con.close()
    assert mart == 900_000
    assert ref == 900_000
    assert abs(mart - ref) < 1.0

def test_injected_break_diverges_but_dbt_tests_pass():
    # dbt build includes tests; it must SUCCEED even with the break (tests are green).
    _dbt("build", "--vars", '{"inject_break": true}')
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    mart = _metric(con, "mart_gtm_metrics", "metric_value", "recognized_net_new_arr")
    ref = _metric(con, "ref_metric_values", "reference_value", "recognized_net_new_arr")
    con.close()
    assert mart == 1_200_000          # re-sourced from bookings
    assert ref == 900_000             # independent billing reference unchanged
    assert abs(mart - ref) == 300_000 # the overstatement reconciliation will catch
