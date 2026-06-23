from typer.testing import CliRunner
from gtm.cli import app

runner = CliRunner()


def test_certify_clean_exits_zero():
    result = runner.invoke(app, ["certify"])
    assert result.exit_code == 0
    assert "8/8 metrics certified" in result.stdout


def test_certify_break_exits_one():
    result = runner.invoke(app, ["certify", "--inject-break"])
    assert result.exit_code == 1
    assert "recognized_net_new_arr" in result.stdout


def test_reconcile_detail_runs():
    runner.invoke(app, ["build"])  # restore clean state
    result = runner.invoke(app, ["reconcile", "recognized_net_new_arr"])
    assert result.exit_code == 0
    assert "source of truth" in result.stdout
