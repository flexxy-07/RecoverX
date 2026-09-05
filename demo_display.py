# demo_display.py
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

STEP_ICONS = {
    "ingest": "📥",
    "classify": "🧠",
    "decide": "⚖️",
    "guardrails": "🛡️",
    "order_status_check": "🔍",
    "execute": "⚡",
}

def print_scenario_header(title: str):
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="cyan")

def print_audit_trail(audit_events: list):
    for event in audit_events:
        node = event.get("node", "?")
        icon = STEP_ICONS.get(node, "•")
        label = node.replace("_", " ").upper()

        # Pull out the interesting fields, skip 'node'/'event' noise
        details = {k: v for k, v in event.items() if k not in ("node", "event", "timestamp")}
        detail_str = "  ".join(f"[dim]{k}:[/dim] {v}" for k, v in details.items())

        console.print(f"  {icon}  [bold]{label}[/bold]  {detail_str}")

def print_final_result(proposed_action: str, execution_result: dict | None, order_status: str | None = None):
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[bold]Final action[/bold]", str(proposed_action))
    if order_status is not None:
        table.add_row("[bold]Order status[/bold]", str(order_status))

    if execution_result is None:
        table.add_row("[bold]Execution[/bold]", "[bold red]BLOCKED — did not run[/bold red]")
    else:
        status = execution_result.get("status", "unknown")
        color = "green" if "success" in status or "created" in status or "recovered" in status else "yellow"
        table.add_row("[bold]Execution status[/bold]", f"[{color}]{status}[/{color}]")
        if "short_url" in execution_result:
            table.add_row("[bold]Payment link[/bold]", f"[link]{execution_result['short_url']}[/link]")

    console.print(Panel(table, title="RESULT", border_style="green" if execution_result else "red"))