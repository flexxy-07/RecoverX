from app.graph.state import RecoveryState

# Order states that mean the payment has already gone through.
RESOLVED_STATUSES = {"paid", "captured"}


def order_status_check(state: RecoveryState) -> dict:
    """
    Double-charge protection. Checks the CURRENT order status (fake for
    now; a real Razorpay order-status call later) immediately before we'd
    otherwise proceed to execute. If the order is already resolved,
    execution is skipped entirely and we route straight to audit.

    This is a separate field (order_status) and a separate node from
    guardrails on purpose — see ARCHITECTURE.md. It answers a different
    question: not "is this action safe," but "has reality already moved
    on since we started."

    NOTE (documented limitation, not a bug): this is a check-then-act
    pattern. Checking order_status here narrows the race window before
    execute runs, but does not mathematically eliminate it — full
    elimination requires the execute operation itself to be idempotent.
    That's a later-phase, real-Razorpay-integration concern.
    """
    # Fake for now: in the real graph, order_status would already be
    # populated upstream by a real Razorpay order-status API call. Since
    # nothing populates it yet, default to "unpaid" so the fake path
    # continues to execute unless a test explicitly sets it otherwise.
    order_status = state.get("order_status", "unpaid")

    if order_status in RESOLVED_STATUSES:
        audit_event = {
            "node": "order_status_check",
            "event": "already_resolved",
            "order_status": order_status,
            "reason": "Order already resolved. Execution blocked to prevent double charge.",
        }
    else:
        audit_event = {
            "node": "order_status_check",
            "event": "unpaid_confirmed",
            "order_status": order_status,
        }

    return {
        "order_status": order_status,
        "audit_events": [audit_event],
    }