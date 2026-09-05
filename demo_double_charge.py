# demo_double_charge.py
from unittest.mock import patch
from rich.console import Console
from app.graph.graph import build_graph
from demo_display import print_audit_trail, print_final_result

console = Console()
console.rule("[bold red]LIVE DOUBLE-CHARGE PROTECTION[/bold red]", style="red")
console.print(
    "[yellow]order_id:[/yellow]   order_TVTPcDQ2NzlAAu\n"
    "[yellow]payment_id:[/yellow] pay_TVUEe2EsXsqwom  (captured on a real second attempt)"
)

FORCED_DIAGNOSIS = {
    "root_cause": "gateway_transient",
    "confidence": 0.95,
    "explanation": "Forced for demo — this test proves order-status enforcement, not classification.",
}

transaction = {
    "id": "txn_spike_live_demo",
    "payment_id": "pay_TVUEe2EsXsqwom",
    "order_id": "order_TVTPcDQ2NzlAAu",
    "amount": 50000,
    "currency": "INR",
    "method": "card",
    "error_code": "BAD_REQUEST_ERROR",
    "error_description": "Payment failed",
    "error_source": "gateway",
    "error_step": "payment_authorization",
    "error_reason": "payment_failed",
}

initial_state = {
    "transaction": transaction, "diagnosis": None, "proposed_action": None,
    "guardrail_result": None, "execution_result": None, "order_status": None,
    "retry_history": [], "audit_events": [],
}
graph = build_graph()
with patch("app.graph.nodes.classify.classify", return_value={
    "diagnosis": FORCED_DIAGNOSIS,
    "audit_events": [{"node": "classify", "event": "diagnosis_completed", **FORCED_DIAGNOSIS}],
}):
    result = graph.invoke(initial_state)

print_audit_trail(result["audit_events"])
print_final_result(result["proposed_action"], result["execution_result"], result.get("order_status"))

order_checked = any(e.get("node") == "order_status_check" for e in result["audit_events"])
order_paid = result.get("order_status") in ("paid", "captured")

# if order_checked and order_paid and result["execution_result"] is None:
#     console.print("\n[bold green]✓ Real Razorpay lookup confirmed 'paid' — execution correctly blocked[/bold green]")
# else:
#     console.print("\n[bold red]⚠ Did not reach the expected block — check before recording[/bold red]")