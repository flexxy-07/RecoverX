# app/graph/nodes/execute.py

import os
from datetime import datetime, timezone
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

from app.graph.state import RecoveryState

load_dotenv()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


RAZORPAY_BASE = "https://api.razorpay.com/v1"


def _razorpay_auth() -> HTTPBasicAuth:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in environment or .env")
    return HTTPBasicAuth(key_id, key_secret)


def _execute_retry(transaction: dict) -> dict:
    """
    Creates a Razorpay Payment Link (POST /v1/payment_links) as the
    recovery action for a failed one-off payment.

    Why not POST /payments/{id}/retry?
    Razorpay has no generic retry endpoint for one-off payments. The
    only /retry endpoint is /subscriptions/{id}/retry, which is for
    recurring mandate billing only. This is a deliberate PCI boundary:
    re-charging a failed card/UPI/netbanking payment requires fresh
    customer authentication (CVV, OTP, 3DS) — a merchant backend cannot
    silently force a re-authorization on a customer's behalf.

    So "retry" in RecoverX means: generate a fresh Payment Link for the
    original amount and hand the short_url to the customer. The status
    is "recovery_link_created" to reflect what's actually happening.
    Sending the link to the customer belongs to notification infra
    (not yet built).

    Returns a result dict. Never raises — all failures are captured so
    execute() can always return a well-formed state update.
    """
    amount = transaction.get("amount")
    currency = transaction.get("currency", "INR")
    original_payment_id = transaction.get("payment_id")

    if not amount:
        return {
            "action": "retry",
            "status": "recovery_link_skipped",
            "reason": "no amount in transaction — cannot create a Payment Link.",
        }
    try:
        auth = _razorpay_auth()
        payload = {
            # Razorpay Payment Links expect amount in paise (smallest unit).
            # Our transaction amounts are already in paise.
            "amount": amount,
            "currency": currency,
            "description": f"Recovery link for failed payment {original_payment_id or 'unknown'}",
            "reminder_enable": False,
        }
        response = requests.post(
            f"{RAZORPAY_BASE}/payment_links",
            json=payload,
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return {
            "action": "retry",
            "status": "recovery_link_created",
            "payment_link_id": data.get("id"),
            "short_url": data.get("short_url"),
            "original_payment_id": original_payment_id,
        }
    except Exception as e:
        return {
            "action": "retry",
            "status": "recovery_link_failed",
            "original_payment_id": original_payment_id,
            "error": str(e),
        }


def _execute_retry_later(transaction: dict) -> dict:
    """
    Razorpay has no "schedule a retry" endpoint, so we confirm current
    payment state via GET /v1/payments/{payment_id} and log a
    retry_scheduled event. Real scheduling would require a job queue
    (out of scope for this phase).
    """
    payment_id = transaction.get("payment_id")
    if not payment_id:
        return {
            "action": "retry_later",
            "status": "retry_scheduled",
            "reason": "no payment_id — logged intent to retry later without confirming state.",
        }
    try:
        auth = _razorpay_auth()
        response = requests.get(
            f"{RAZORPAY_BASE}/payments/{payment_id}",
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()
        payment = response.json()
        return {
            "action": "retry_later",
            "status": "retry_scheduled",
            "payment_id": payment_id,
            "current_payment_status": payment.get("status"),
        }
    except Exception as e:
        return {
            "action": "retry_later",
            "status": "retry_scheduled",
            "payment_id": payment_id,
            "error": str(e),
            "note": "Razorpay state fetch failed but retry intent is still logged.",
        }


def execute(state: RecoveryState) -> dict:
    """
    Executes the proposed action. By the time this node runs:
      - guardrails confirmed the action is policy-safe (ALLOWED)
      - order_status_check confirmed the order isn't already resolved
    execute trusts both of those and acts on proposed_action.

    retry / retry_later  →  real Razorpay Test Mode API calls
    human_review         →  logged-only (no real alerting infra yet)
    customer_nudge       →  logged-only (no real notification infra yet)
    customer_action      →  logged-only (no real notification infra yet)
    """
    action = state["proposed_action"]
    transaction = state["transaction"]

    if action == "retry":
        result = _execute_retry(transaction)
    elif action == "retry_later":
        result = _execute_retry_later(transaction)
    elif action == "customer_nudge":
        result = {"action": "customer_nudge", "status": "nudge_logged", "note": "no notification infra yet"}
    elif action == "customer_action":
        result = {"action": "customer_action", "status": "customer_action_logged", "note": "no notification infra yet"}
    elif action == "human_review":
        result = {"action": "human_review", "status": "flagged_for_review", "note": "no alerting infra yet"}
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
                "timestamp": _now(),
            }
        ],
    }
