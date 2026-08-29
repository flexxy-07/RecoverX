# app/graph/nodes/execute.py

from app.graph.state import RecoveryState


def execute(state: RecoveryState) -> dict:
    """
    Fake execution. By the time this node runs, guardrails already
    confirmed the action is policy-safe (ALLOWED) and order_status_check
    already confirmed the order isn't already resolved — execute trusts
    both of those and just performs (fakes) the proposed_action.

    Each action type gets its own branch so the result and audit trail
    accurately describe what kind of action ran, not just that "an
    action" ran.
    """
    action = state["proposed_action"]

    if action == "retry":
        result = {"action": "retry", "status": "simulated_retry_triggered"}
    elif action == "retry_later":
        result = {"action": "retry_later", "status": "simulated_retry_scheduled"}
    elif action == "customer_nudge":
        result = {"action": "customer_nudge", "status": "simulated_nudge_prepared"}
    elif action == "customer_action":
        result = {"action": "customer_action", "status": "simulated_customer_action_prepared"}
    elif action == "human_review":
        result = {"action": "human_review", "status": "simulated_flagged_for_review"}
    else:
        # Defensive fallback: proposed_action should always be one of the
        # 5 known values from decide.py's POLICY table, but if something
        # unexpected reaches execute, don't silently no-op — make it loud.
        result = {"action": action, "status": "unrecognized_action"}

    return {
        "execution_result": result,
        "audit_events": [
            {
                "node": "execute",
                "event": "executed",
                "action": action,
                "result": result,
            }
        ],
    }