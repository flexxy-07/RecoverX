from datetime import datetime, timezone
from app.graph.state import RecoveryState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# Deterministic policy table. This is NEVER modified by the LLM — classify
# only ever sets root_cause; this mapping is fixed, auditable, ordinary
# Python.
POLICY = {
    "gateway_transient": "retry",
    "bank_transient": "retry_later",
    "insufficient_funds": "customer_nudge",
    "authentication_failure": "customer_action",
    "payment_risk": "human_review",
    "customer_action_required": "customer_nudge",
    "unknown": "human_review",
}

# Below this confidence, we don't trust ANY root cause enough to act on
# it automatically — force human_review regardless of what POLICY says.
CONFIDENCE_THRESHOLD = 0.6


def decide(state: RecoveryState) -> dict:
    """
    Looks up the deterministic policy action for the diagnosed root
    cause, then applies the confidence gate: a low-confidence diagnosis
    is never trusted enough to auto-act on, no matter how "actionable"
    its root_cause looks in the table.
    """
    diagnosis = state["diagnosis"]
    # pyrefly: ignore [unsupported-operation]
    root_cause = diagnosis["root_cause"]
    # pyrefly: ignore [unsupported-operation]
    confidence = diagnosis["confidence"]

    policy_action = POLICY[root_cause]
    audit_events = []

    if confidence < CONFIDENCE_THRESHOLD:
        action = "human_review"
        audit_events.append({
            "node": "decide",
            "event": "confidence_override",
            "root_cause": root_cause,
            "confidence": confidence,
            "policy_action": policy_action,
            "final_action": action,
            "reason": (
                f"Confidence {confidence} below threshold "
                f"{CONFIDENCE_THRESHOLD}; forcing human_review "
                f"regardless of policy table."
            ),
            "timestamp": _now(),
        })
    else:
        action = policy_action
        audit_events.append({
            "node": "decide",
            "event": "policy_applied",
            "root_cause": root_cause,
            "confidence": confidence,
            "final_action": action,
            "timestamp": _now(),
        })

    return {
        "proposed_action": action,
        "audit_events": audit_events,
    }