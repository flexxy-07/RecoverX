# demo_golden_scenarios.py

import json
from app.graph.graph import build_graph
from demo_display import print_scenario_header, print_audit_trail, print_final_result

GOLDEN_IDS = ["txn_034", "txn_016", "txn_024"]  # removed txn_001
LABELS = {
    "txn_034": "SCENARIO 1 — Recoverable gateway failure",
    "txn_016": "SCENARIO 2 — Insufficient funds",
    "txn_024": "SCENARIO 3 — High-risk payment (hard block)",
}

# New: hardcoded ambiguous transaction for Scenario 4, instead of pulling
# txn_001 from the dataset — its diagnosis wasn't reliably reproducible.
SCENARIO_4_TRANSACTION = {
    "id": "txn_ambiguous_demo",
    "payment_id": "pay_demo_ambiguous",
    "order_id": "order_demo_ambiguous",
    "amount": 50000,
    "currency": "INR",
    "method": "card",
    "error_code": "BAD_REQUEST_ERROR",
    "error_description": "Payment failed",
    "error_source": "gateway",
    "error_step": "payment_authorization",
    "error_reason": "payment_failed",
}

with open("data/transactions.json") as f:
    all_transactions = json.load(f)
by_id = {t["id"]: t for t in all_transactions}

graph = build_graph()
for tid in GOLDEN_IDS:
    txn = by_id.get(tid)
    if not txn:
        continue

    print_scenario_header(LABELS[tid])

    initial_state = {
        "transaction": txn, "diagnosis": None, "proposed_action": None,
        "guardrail_result": None, "execution_result": None, "order_status": None,
        "retry_history": txn.get("retry_history", []), "audit_events": [],
    }
    result = graph.invoke(initial_state)

    print_audit_trail(result["audit_events"])
    print_final_result(result["proposed_action"], result["execution_result"], result.get("order_status"))

# Run Scenario 4 separately, using the hardcoded ambiguous transaction
print_scenario_header("SCENARIO 4 — Low-confidence / uncertain diagnosis")

initial_state = {
    "transaction": SCENARIO_4_TRANSACTION, "diagnosis": None, "proposed_action": None,
    "guardrail_result": None, "execution_result": None, "order_status": None,
    "retry_history": [], "audit_events": [],
}
result = graph.invoke(initial_state)

print_audit_trail(result["audit_events"])
print_final_result(result["proposed_action"], result["execution_result"], result.get("order_status"))