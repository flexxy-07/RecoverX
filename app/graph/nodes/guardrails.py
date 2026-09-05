from datetime import datetime, timezone
from app.graph.state import RecoveryState

MAX_RETRIES = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def guardrails(state: RecoveryState) -> dict:
    """
    Independent safety check, separate from decide's policy logic.
    Answers exactly two questions: is this root_cause ever safe to
    auto-act on, and have we already retried too many times. Outputs
    ONLY "ALLOWED" or "BLOCKED" — nothing else — so guardrail_router
    stays a trivial string comparison.
    """
    diagnosis = state["diagnosis"]
    root_cause = diagnosis["root_cause"]

    # retry_count is NEVER stored separately — always derived, so there's
    # only one possible source of truth for how many retries happened.
    retry_count = len(state.get("retry_history", []))

    audit_events = []

    if root_cause == "payment_risk":
        result = "BLOCKED"
        audit_events.append({
            "node": "guardrails",
            "event": "blocked",
            "reason": "root_cause is payment_risk; never auto-actioned.",
            "timestamp": _now(),
        })

    elif retry_count >= MAX_RETRIES:
        result = "BLOCKED"
        audit_events.append({
            "node": "guardrails",
            "event": "blocked",
            "reason": (
                f"retry_count ({retry_count}) has reached the max "
                f"of {MAX_RETRIES}."
            ),
            "timestamp": _now(),
        })

    else:
        result = "ALLOWED"
        audit_events.append({
            "node": "guardrails",
            "event": "allowed",
            "root_cause": root_cause,
            "retry_count": retry_count,
            "timestamp": _now(),
        })

    return {
        "guardrail_result": result,
        "audit_events": audit_events,
    }