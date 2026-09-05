import os
import razorpay
from datetime import datetime, timezone
from dotenv import load_dotenv

from app.graph.state import RecoveryState

load_dotenv()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# Order states that mean the payment has already gone through.
RESOLVED_STATUSES = {"paid", "captured"}


def _get_razorpay_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in environment or .env")
    return razorpay.Client(auth=(key_id, key_secret))


def order_status_check(state: RecoveryState) -> dict:
    """
    Double-charge protection. Fetches the CURRENT order status from
    Razorpay immediately before we'd otherwise proceed to execute.
    If the order is already resolved (paid/captured), execution is
    skipped entirely and we route straight to audit.

    This is a separate field (order_status) and a separate node from
    guardrails on purpose — see ARCHITECTURE.md. It answers a different
    question: not "is this action safe," but "has reality already moved
    on since we started."

    NOTE (documented limitation, not a bug): this is a check-then-act
    pattern. Checking order_status here narrows the race window before
    execute runs, but does not mathematically eliminate it — full
    elimination requires the execute operation itself to be idempotent.
    That's a later-phase concern.

    Fallback contract: any failure (missing order_id, API error, network
    timeout) resolves to "unpaid" so a legitimate retry is never blocked
    by an infrastructure failure. The specific failure reason is always
    recorded in audit_events.
    """
    transaction = state["transaction"]
    order_id = transaction.get("order_id")

    # --- Fallback: no order_id present ---
    if not order_id:
        return {
            "order_status": "unpaid",
            "audit_events": [
                {
                    "node": "order_status_check",
                    "event": "no_order_id",
                    "reason": "transaction has no order_id — treating as unpaid to avoid blocking a legitimate retry.",
                    "timestamp": _now(),
                }
            ],
        }

    # --- Real Razorpay fetch ---
    try:
        client = _get_razorpay_client()
        order = client.order.fetch(order_id)  # type: ignore[missing-attribute]
        order_status = order.get("status", "created")
    except Exception as e:
        # Network / auth / API failure → safe fallback.
        # We log the real error so engineers can debug, but we never
        # block execution solely because the status check failed.
        print(f"[order_status_check] Razorpay fetch failed for {order_id}: {e}")
        return {
            "order_status": "unpaid",
            "audit_events": [
                {
                    "node": "order_status_check",
                    "event": "status_check_failed",
                    "order_id": order_id,
                    "error": str(e),
                    "fallback": "treating as unpaid",
                    "timestamp": _now(),
                }
            ],
        }

    # --- Guard logic (unchanged from stub) ---
    if order_status in RESOLVED_STATUSES:
        audit_event = {
            "node": "order_status_check",
            "event": "already_resolved",
            "order_id": order_id,
            "order_status": order_status,
            "reason": "Order already resolved. Execution blocked to prevent double charge.",
            "timestamp": _now(),
        }
    else:
        audit_event = {
            "node": "order_status_check",
            "event": "unpaid_confirmed",
            "order_id": order_id,
            "order_status": order_status,
            "timestamp": _now(),
        }

    return {
        "order_status": order_status,
        "audit_events": [audit_event],
    }