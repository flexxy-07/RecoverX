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

## 2026-09-04 — "retry" means payment link creation, not re-charge

Razorpay has no generic retry endpoint for one-off payments.
`POST /payments/{id}/retry` returns 404 — the only `/retry` endpoint is
`/subscriptions/{id}/retry`, which applies to recurring mandate billing only.

This is a deliberate PCI security boundary: re-charging a failed card/UPI/netbanking
payment requires fresh customer authentication (CVV, OTP, 3DS). A merchant backend
cannot silently force a re-authorisation on a customer's behalf.

Decision: "retry" in RecoverX means `POST /v1/payment_links` — generate a fresh
payment link for the original amount and surface the `short_url` as the recovery
output. The status is `recovery_link_created` (not `retry_triggered`) to reflect
what actually happens. Sending the link to the customer is a notification-infra
concern (not yet built).

Confirmed live: 6 payment links created with real `rzp.io` short URLs during the
35-transaction batch run.

## 2026-09-04 — authentication_failure and customer_action_required converge on the same action

Batch run finding: Gemini classified 4 out of 5 OTP/CVV/3DS failure transactions as
`customer_action_required` rather than `authentication_failure`. Both are valid
interpretations — an OTP failure does require the customer to re-authenticate, which
is a customer action. The distinction is semantic, not operational.

Crucially, both root causes map to the same action path in the policy table
(`customer_nudge` / `customer_action`), so misclassification between these two is
functionally harmless. The audit trail still records the exact diagnosis Gemini returned,
so the data is never lost — only the label differs.

No change to policy table or prompt. Noted here so future reviewers understand why
authentication_failure appears underrepresented in batch output.

## 2026-09-04 — _derive_outcome must handle recovery_link_failed explicitly

Batch run finding: 2 transactions showed `outcome: unknown` in Firestore despite
reaching the execute node. Root cause: `_derive_outcome` had no case for
`recovery_link_failed` or `recovery_link_skipped` — both fell through to the
catch-all `return "unknown"`.

Fixed by adding an explicit branch: both statuses now return `"recovery_link_failed"`,
which signals that a retry was intended but the payment link API call failed. This
outcome is queryable in Firestore and distinguishable from a genuine unknown/unclassified
run. The downstream implication (a human should follow up) is the same as `human_review`.

## 2026-09-04 — Firestore document ID: transaction_id (overwrite), not transaction_id_timestamp

Options considered:
1. `{transaction_id}` — overwrite on every run. 35 docs always, always current.
2. `{transaction_id}_{batch_run_id}` — one set per run, historical batches preserved.
3. `{transaction_id}_{timestamp}` — original implementation, unbounded growth.

Decision: **Option 1** — doc ID = `transaction_id` with `.set()` (overwrite semantics).
Dashboard query is trivially simple (just read all 35 docs). No dedup logic needed.

Tradeoff accepted: per-transaction history is lost on re-run. Mitigated by adding a
`batch_run_id` field (one UUID per `batch_run.py` invocation) to every document — this
lets you see which run produced the current state without it affecting the document ID.
If run-history analytics are ever needed, the batch_run_id field provides the hook.

This was decided before Day 5 / Flutter dashboard build, so the Firestore query is
stable by the time the dashboard is written.

## 2026-09-04 — batch_run.py sleep bumped from 1s to 2s (18 RPM → demo-safe)

Gemini free tier: 1,500 requests/day, 30 requests/minute.
At `time.sleep(1)`, 35 transactions ≈ 35 RPM — above the rate limit if any retry or
network jitter adds latency. At `time.sleep(2)`, 35 transactions ≈ 18 RPM — comfortably
inside the limit with a ~40% safety margin. Cost: 35 extra seconds per batch run.
