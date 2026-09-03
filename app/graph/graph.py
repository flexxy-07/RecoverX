# app/graph/graph.py

from langgraph.graph import StateGraph, END

from app.graph.state import RecoveryState
from app.graph.nodes.ingest import ingest
import app.graph.nodes.classify as classify_module   # <-- import the MODULE, not the function
from app.graph.nodes.decide import decide
from app.graph.nodes.guardrails import guardrails
from app.graph.nodes.order_status_check import order_status_check
from app.graph.nodes.execute import execute
from app.graph.nodes.audit import audit


# Actions that actually attempt to touch a payment. Only these need the
# order-status check before proceeding — checking order status ahead of
# a human_review/customer_nudge/customer_action would burn a real
# Razorpay API call for a decision that was never going to touch money.
MONEY_MOVING_ACTIONS = {"retry", "retry_later"}


def guardrail_router(state: RecoveryState) -> str:
    """
    Reads guardrail_result AND proposed_action. BLOCKED always goes to
    audit. If ALLOWED, only route to order_status_check for actions that
    actually attempt a payment (retry / retry_later) — every other
    allowed action (human_review, customer_nudge, customer_action) skips
    the status check entirely and goes straight to execute, since
    there's no double-charge risk to guard against for a non-money
    action. See DECISIONS.md for why this reads two fields instead of
    one, unlike order_status_router.
    """
    if state["guardrail_result"] == "BLOCKED":
        return "audit"
    if state["proposed_action"] in MONEY_MOVING_ACTIONS:
        return "order_status_check"
    return "execute"


def order_status_router(state: RecoveryState) -> str:
    if state["order_status"] in ("paid", "captured"):
        return "audit"
    return "execute"


def build_graph():
    workflow = StateGraph(RecoveryState)  # type: ignore[bad-specialization] 

    workflow.add_node("ingest", ingest)
    # Wrapper, not a direct function reference — this looks up
    # classify_module.classify freshly on every call, so monkeypatching
    # classify_module.classify (as run_test.py does) actually takes
    # effect. A direct `workflow.add_node("classify", classify)` would
    # have permanently captured whatever function object existed at
    # import time, immune to later reassignment.
    workflow.add_node("classify", lambda state: classify_module.classify(state))
    workflow.add_node("decide", decide)
    workflow.add_node("guardrails", guardrails)
    workflow.add_node("order_status_check", order_status_check)
    workflow.add_node("execute", execute)
    workflow.add_node("audit", audit)

    workflow.set_entry_point("ingest")

    workflow.add_edge("ingest", "classify")
    workflow.add_edge("classify", "decide")
    workflow.add_edge("decide", "guardrails")

    workflow.add_conditional_edges(
    "guardrails",
    guardrail_router,
    {
        "audit": "audit",
        "order_status_check": "order_status_check",
        "execute": "execute",
    },
)

    workflow.add_conditional_edges(
        "order_status_check",
        order_status_router,
        {"audit": "audit", "execute": "execute"},
    )

    workflow.add_edge("execute", "audit")
    workflow.add_edge("audit", END)

    return workflow.compile()