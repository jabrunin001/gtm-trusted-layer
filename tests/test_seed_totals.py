import subprocess, sys
from pathlib import Path
import duckdb
from gtm.config import REPO_ROOT, DUCKDB_PATH

def _dbt(*args):
    exe = Path(sys.executable).parent / "dbt"
    subprocess.run([str(exe), *args, "--profiles-dir", "."], cwd=REPO_ROOT, check=True)

def test_seed_totals():
    _dbt("seed", "--full-refresh")
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    won = con.execute(
        "select sum(net_new_arr) from salesforce_opportunities where stage='Closed Won'"
    ).fetchone()[0]
    usage = con.execute("select sum(recognized_amount) from billing_usage_events").fetchone()[0]
    invoices = con.execute("select sum(invoice_amount) from billing_invoices").fetchone()[0]
    con.close()
    assert won == 1_200_000
    assert usage == 900_000
    assert invoices == 900_000
