# app/graph/nodes/audit.py

import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from app.graph.state import RecoveryState

load_dotenv()

# Firestore client is initialised lazily so a missing credentials file
# never crashes the graph at import time — same pattern as classify.py.
_firestore_client = None


def _get_firestore_client():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client

    creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not creds_path:
        raise ValueError("FIREBASE_CREDENTIALS_PATH is not set in environment or .env")

    import firebase_admin
    from firebase_admin import credentials, firestore

    # Guard against re-initialising if another module already did it.
    if not firebase_admin._apps:
        cred = credentials.Certificate(creds_path)
        firebase_admin.initialize_app(cred)

    _firestore_client = firestore.client()
    return _firestore_client


def _derive_outcome(state: RecoveryState) -> str:
    """
    Summarise the run into a single outcome label for easy querying and
    aggregation in Firestore. Reads the execution_result status first,
    then falls back to guardrail/order state signals.
    """
    execution_result = state.get("execution_result") or {}
    exec_status = execution_result.get("status", "")

    if exec_status == "recovery_link_created":
        return "recovery_link_created"
    if exec_status in ("recovery_link_failed", "recovery_link_skipped"):
        # Payment link creation failed or had no payment_id — the intent
        # was retry but it couldn't execute. Treated as human_review so a
        # person can follow up rather than silently dropping the record.
        return "recovery_link_failed"
    if exec_status == "retry_scheduled":
        return "retry_scheduled"
    if exec_status in ("nudge_logged", "customer_action_logged"):
        return "customer_notified"
    if exec_status == "flagged_for_review":
        return "human_review"

    if state.get("guardrail_result") == "BLOCKED":
        return "blocked"
    if state.get("order_status") in ("paid", "captured"):
        return "already_resolved"

    # Catch-all — something reached audit without a clear outcome.
    return "unknown"


def audit(state: RecoveryState) -> dict:
    """
    Terminal node. Every path through the graph ends here. Writes one
    Firestore document to the recovery_runs collection containing the
    full audit trail, diagnosis, final action, and execution result.

    Firestore write is best-effort: if it fails (missing credentials,
    network error, quota) the node prints a warning but still returns {}
    so the graph completes cleanly. The trail is always printed to stdout
    as a secondary record.
    """
    # --- Always print to stdout ---
    print("\n=== AUDIT TRAIL ===")
    for i, event in enumerate(state.get("audit_events", []), start=1):
        print(f"{i}. {event}")
    print("====================\n")

    # --- Build the Firestore document ---
    transaction = state.get("transaction") or {}
    transaction_id = transaction.get("id", "unknown")
    outcome = _derive_outcome(state)
    collection = os.getenv("FIRESTORE_COLLECTION", "recovery_runs")

    doc = {
        "transaction_id": transaction_id,
        "batch_run_id": transaction.get("batch_run_id"),
        "timestamp": datetime.now(timezone.utc),
        "diagnosis": state.get("diagnosis"),
        "proposed_action": state.get("proposed_action"),
        "guardrail_result": state.get("guardrail_result"),
        "order_status": state.get("order_status"),
        "execution_result": state.get("execution_result"),
        "audit_trail": state.get("audit_events", []),
        "outcome": outcome,
    }

    # --- Write to Firestore (best-effort) ---
    try:
        db = _get_firestore_client()
        # Doc ID = transaction_id (overwrite semantics).
        # Always reflects the latest run; batch_run_id field tracks which run wrote it.
        db.collection(collection).document(transaction_id).set(doc)
        print(f"[audit] Firestore write OK → {collection}/{transaction_id} (outcome: {outcome})")
    except Exception as e:
        print(f"[audit] Firestore write FAILED (graph still completes): {e}")

    return {}