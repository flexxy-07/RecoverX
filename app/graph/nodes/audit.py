# app/graph/nodes/audit.py

from app.graph.state import RecoveryState


def audit(state: RecoveryState) -> dict:
    """
    Terminal node. Every path through the graph ends here. By this point
    audit_events has accumulated (via operator.add) every event logged
    by every node this transaction passed through — this node's only job
    is to surface that trail. No real logic, no state changes: this is
    intentionally the simplest node in the graph.

    Printing for now; will write to Firestore in a later phase.
    """
    print("\n=== AUDIT TRAIL ===")
    for i, event in enumerate(state.get("audit_events", []), start=1):
        print(f"{i}. {event}")
    print("====================\n")

    # No state updates needed — audit is a terminal side-effect step.
    return {}