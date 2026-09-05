# batch_run.py
#
# Runs all transactions in data/transactions.json through the live
# RecoverX graph sequentially. Each run writes one document to Firestore
# via the audit node. Prints a summary at the end.

import sys
import io
import json
import time
import uuid
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.graph.graph import build_graph

print("=" * 60)
print("RECOVERX BATCH RUN")
print("=" * 60)

# One shared ID for every document written in this run.
# Stored as a field on each Firestore doc so you can filter by batch
# without it affecting the doc ID (which stays = transaction_id).
batch_run_id = str(uuid.uuid4())
print(f"Batch run ID: {batch_run_id}")

with open("data/transactions.json", "r", encoding="utf-8") as f:
    transactions = json.load(f)

graph = build_graph()

results = []
errors  = []

for txn in transactions:
    txn_id = txn["id"]
    print(f"\n--- {txn_id} | {txn.get('error_code')} | {txn.get('method')} ---")

    # Inject batch_run_id so audit.py can write it to Firestore
    # without needing it in the graph state schema.
    txn_with_batch = {**txn, "batch_run_id": batch_run_id}
    initial_state = {
        "transaction": txn_with_batch,
        "retry_history": [],
        "audit_events": [],
        "diagnosis": None,
        "proposed_action": None,
        "guardrail_result": None,
        "order_status": None,
        "execution_result": None,
    }

    try:
        final_state = graph.invoke(initial_state)
        diag = final_state.get("diagnosis") or {}

        outcome_node = "audit"
        # Derive outcome from what audit.py would compute, without re-importing it
        exec_result  = final_state.get("execution_result") or {}
        exec_status  = exec_result.get("status", "")
        guardrail    = final_state.get("guardrail_result")
        order_status = final_state.get("order_status")

        if exec_status == "recovery_link_created":
            outcome = "recovery_link_created"
        elif exec_status in ("recovery_link_failed", "recovery_link_skipped"):
            outcome = "recovery_link_failed"
        elif exec_status == "retry_scheduled":
            outcome = "retry_scheduled"
        elif exec_status in ("nudge_logged", "customer_action_logged"):
            outcome = "customer_notified"
        elif exec_status == "flagged_for_review":
            outcome = "human_review"
        elif guardrail == "BLOCKED":
            outcome = "blocked"
        elif order_status in ("paid", "captured"):
            outcome = "already_resolved"
        else:
            outcome = "unknown"

        results.append({
            "id": txn_id,
            "root_cause": diag.get("root_cause", "?"),
            "confidence": diag.get("confidence", 0.0),
            "proposed_action": final_state.get("proposed_action"),
            "guardrail_result": guardrail,
            "outcome": outcome,
        })
        print(f"    root_cause={diag.get('root_cause')} | confidence={diag.get('confidence')} | outcome={outcome}")

    except Exception as e:
        print(f"    [ERROR] {txn_id} crashed: {e}")
        errors.append({"id": txn_id, "error": str(e)})

    # 2s pause → ~18 RPM, safely inside the 30 RPM free-tier rate limit.
    # 1s was too tight (35 RPM) for a live demo with any network jitter.
    time.sleep(2)

# ── Summary ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BATCH SUMMARY")
print("=" * 60)

total      = len(transactions)
succeeded  = len(results)
failed     = len(errors)
outcomes   = Counter(r["outcome"] for r in results)
root_causes = Counter(r["root_cause"] for r in results)

print(f"Total transactions:          {total}")
print(f"Successfully processed:      {succeeded}")
print(f"Errors (graph crashed):      {failed}")
print()
print("Outcomes:")
for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
    print(f"  {outcome:<28} {count}")
print()
print("Root causes (LLM diagnoses):")
for cause, count in sorted(root_causes.items(), key=lambda x: -x[1]):
    print(f"  {cause:<28} {count}")

if errors:
    print("\nFailed transactions:")
    for e in errors:
        print(f"  {e['id']}: {e['error']}")

print("\nFirestore collection: recovery_runs")
print(f"Documents written:    {succeeded}  (check Firebase console to confirm)")
print("=" * 60)
