# DECISIONS.md

Running log of technical decisions and rationale.

## 2026-08-29 — Project name: RecoverX

## 2026-08-29 — Two separate routers, not one

`guardrail_router` and `order_status_router` stay independent. Merging them would make it
ambiguous whether a block came from a safety-policy violation (guardrails) or a real-world
state change (order already paid). Keeping them separate keeps each router single-purpose
and the audit trail unambiguous about *why* execution stopped.

## 2026-08-29 — `retry_count` is derived, not stored

`len(retry_history)` is computed wherever needed instead of maintaining a separate
`retry_count` field. Avoids two sources of truth that could drift out of sync.

## 2026-08-29 — Explicit `__init__.py` packages

Added empty `__init__.py` to every `app/` subdirectory even though the original file tree
didn't list them. Python 3 doesn't strictly require this (namespace packages work without
them), but explicit packages behave more predictably with tooling like pytest and linters.
Not a scope change, just flagged per working-style rules — happy to revert if preferred.

## Deferred decisions

- Gemini prompt design and structured-output schema — later phase.
- Razorpay order-status API integration shape — later phase.
- Firestore schema for audit persistence — later phase.

## 2026-08-30 — classify node registered via late-binding wrapper

Original `graph.py` did `from app.graph.nodes.classify import classify` and passed that
function directly to `workflow.add_node("classify", classify)`. This captures the function
object at import time (early binding) — reassigning `classify_module.classify` later (as
run_test.py does to inject test-specific fake diagnoses) had no effect, because graph.py
was still holding its original reference.

Fixed by importing the module itself (`import app.graph.nodes.classify as classify_module`)
and registering `lambda state: classify_module.classify(state)` instead — this looks up
`classify_module.classify` fresh on every call (late binding), so monkeypatching it from
run_test.py now actually takes effect.

Confirmed the fix by re-running all 5 test scenarios — Tests 2, 3, and 5 (which all rely on
swapping in a different fake classify) now correctly show their scenario-specific diagnosis
in the audit trail instead of the original hardcoded gateway_transient/0.94.

## 2026-08-30 — guardrail_router now also reads proposed_action

Originally order_status_check ran for every guardrails-ALLOWED transaction, including
human_review / customer_nudge / customer_action — none of which attempt a payment, so
none of them carry double-charge risk. Once order_status_check calls the real Razorpay
API, this would burn an API call on every non-money decision for no reason.

Fixed by expanding guardrail_router to also check proposed_action: only "retry" and
"retry_later" (MONEY_MOVING_ACTIONS) route to order_status_check; every other allowed
action routes straight to execute. order_status_router is unchanged — still reads
order_status only.

Trade-off, noted honestly: guardrail_router now reads two fields instead of one,
diverging slightly from the original "each router reads exactly one field" rule. Judged
acceptable since both fields describe the same checkpoint's decision, and the
alternative (a third router) isn't supported — LangGraph only allows one set of
conditional edges per node.

Confirmed via full test suite: Tests 2/3/5 (human_review outcomes) now skip
order_status_check entirely (order_status stays None). Tests 1/4 (retry outcomes)
unaffected — order_status_check still runs and still correctly blocks on
already-resolved orders.