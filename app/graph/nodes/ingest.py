from datetime import datetime, timezone
from app.graph.state import RecoveryState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest(state: RecoveryState) -> dict:
    """
    Entry point of the graph. Takes the raw transaction dict (already
    present in state['transaction'] when the graph is invoked) and
    initializes the fields nothing has touched yet: retry_history starts
    empty, audit_events starts as a list with one entry marking that this
    transaction was received.

    This node doesn't diagnose, decide, or judge anything — it only
    establishes a clean starting state for everything downstream.
    """
    transaction = state["transaction"]

    return {
        "retry_history": state.get("retry_history", []),
        "audit_events": [
            {
                "node": "ingest",
                "event": "transaction_received",
                "transaction_id": transaction.get("id", "unknown"),
                "timestamp": _now(),
            }
        ],
    }