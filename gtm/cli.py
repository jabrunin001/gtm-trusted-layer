import typer
from gtm import dbt_runner
from gtm.registry import load_registry
from gtm.warehouse import Warehouse
from gtm.certify import certify as _certify, summary
from gtm.report import render_certify_table, render_reconcile_detail
from gtm.config import AS_OF, FRESHNESS_WINDOW_DAYS

app = typer.Typer(help="Certify GTM metrics as governed, fresh, and reconciled.")


@app.command()
def build(
    inject_break: bool = typer.Option(False, "--inject-break"),
    target: str = typer.Option("local", "--target"),
):
    """Build the dbt project (optionally with the planted reconciliation break)."""
    dbt_runner.build(inject_break=inject_break, target=target)


@app.command()
def certify(
    inject_break: bool = typer.Option(False, "--inject-break"),
    target: str = typer.Option("local", "--target"),
):
    """Build, then certify every registry metric. Exit 1 if any metric fails."""
    dbt_runner.build(inject_break=inject_break, target=target)
    statuses = _certify_metrics()
    render_certify_table(statuses)
    n_ok, n_total = summary(statuses)
    typer.echo(f"{n_ok}/{n_total} metrics certified")
    if n_ok != n_total:
        raise typer.Exit(code=1)


@app.command()
def reconcile(metric: str):
    """Show reconciliation detail and root-cause framing for one metric."""
    reg = load_registry()
    statuses = _certify_metrics()
    status = next((s for s in statuses if s.metric == metric), None)
    if status is None:
        typer.echo(f"unknown metric: {metric}")
        raise typer.Exit(code=1)
    render_reconcile_detail(status, reg.get(metric))


def _certify_metrics():
    return _certify(load_registry(), Warehouse(), AS_OF, FRESHNESS_WINDOW_DAYS)


if __name__ == "__main__":
    app()
