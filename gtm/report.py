from rich.console import Console
from rich.table import Table
from gtm.certify import MetricStatus
from gtm.registry import MetricDef

console = Console(width=200)


def _mark(b: bool) -> str:
    return "[green]✓[/green]" if b else "[red]✗[/red]"


def render_certify_table(statuses: list[MetricStatus]) -> None:
    table = Table(title="GTM Metric Certification")
    table.add_column("Metric")
    table.add_column("Owner")
    table.add_column("Gov")
    table.add_column("Fresh")
    table.add_column("Recon")
    table.add_column("Mart")
    table.add_column("Reference")
    table.add_column("Status")
    for s in statuses:
        status = "[green]CERTIFIED[/green]" if s.certified else f"[red]FAIL[/red] {s.reason}"
        table.add_row(
            s.metric, s.owning_org, _mark(s.governed), _mark(s.fresh), _mark(s.reconciled),
            "" if s.mart_value is None else f"{s.mart_value:,.2f}",
            "" if s.reference_value is None else f"{s.reference_value:,.2f}",
            status,
        )
    console.print(table)


def render_reconcile_detail(status: MetricStatus, metric_def: MetricDef) -> None:
    console.print(f"[bold]{status.metric}[/bold] — owned by {status.owning_org}")
    console.print(f"  source of truth : {metric_def.source_of_truth}")
    console.print(f"  mart value      : {'N/A' if status.mart_value is None else f'{status.mart_value:,.2f}'}")
    console.print(f"  reference value : {'N/A' if status.reference_value is None else f'{status.reference_value:,.2f}'}")
    console.print(f"  delta           : {'N/A' if status.delta is None else f'{status.delta:+,.2f}'}")
    verdict = "within tolerance" if status.reconciled else "OUT OF TOLERANCE"
    console.print(f"  verdict         : {verdict}")
