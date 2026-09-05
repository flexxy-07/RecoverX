# ARCHITECTURE.md

Living document. Last updated: 2026-09-05 (final submission state).

## Graph Flow

```
Failed Razorpay Transaction
   ↓
ingest → classify (LLM) → decide → guardrails
                                           ↓
                              ┌─────────────────────────────┐
                              │ BLOCKED → audit → END       │
                              └─────────────────────────────┘
                                           ↓ ALLOWED
                                  (retry / retry_later only)
                              order_status_check (Razorpay API)
                                           ↓
                              ┌─────────────────────────────┐
                              │ paid/captured → audit → END │
                              └─────────────────────────────┘
                                           ↓ unpaid / unknown
                                        execute
                                           ↓
                              audit → Firestore → Dashboard
```

## Nodes

| Node | Responsibility |
|---|---|
| `ingest` | Load/normalize the incoming failed-transaction record into `RecoveryState` |
| `classify` | Call LLM with the Razorpay error payload → `Diagnosis(root_cause, confidence, explanation)`. Never crashes the graph — 503s and parse errors fall back to `unknown / 0.0`. |
| `decide` | Deterministic policy table: `root_cause → proposed_action`. Overrides action to `human_review` if `confidence < 0.6` regardless of policy table. |
| `guardrails` | Hard-blocks `payment_risk` and transactions exceeding `MAX_RETRIES`. Sets `guardrail_result` to `BLOCKED` or `ALLOWED`. |
| `order_status_check` | Only runs for `retry` / `retry_later` (MONEY_MOVING_ACTIONS). Fetches live Razorpay order status — if `paid` or `captured`, routes to `audit` without executing (double-charge protection). |
| `execute` | Creates a Razorpay Payment Link for retries; logs flags for nudge/review actions. Real Razorpay API calls in test mode. |
| `audit` | Writes all state fields + `audit_trail` (list of per-node timestamped events) to Firestore at `recovery_runs/{transaction_id}` with `.set()` (overwrite semantics). |

## Two Independent Routers

- **`guardrail_router`**: reads `guardrail_result` + `proposed_action`. Routes to `audit` if BLOCKED; to `order_status_check` for money-moving actions; straight to `execute` for everything else.
- **`order_status_router`**: reads `order_status` only. Routes to `audit` if already paid; to `execute` if unpaid/uncertain.

They are kept separate on purpose: guardrails answer *"is this action safe to attempt at all?"* (root-cause / retry-count domain), while order-status answers *"has reality already changed underneath us?"* (double-charge domain). Conflating them would obscure which failure mode triggered a block in the audit trail.

Note: `guardrail_router` reads two fields (not just one) because LangGraph only allows one set of conditional edges per node — a third router is not possible here. See DECISIONS.md.

## State Shape

`RecoveryState` (TypedDict, `total=False`) — see [`app/graph/state.py`](app/graph/state.py).

Key design point: `audit_events: Annotated[list, operator.add]` — LangGraph's default merge
for a plain `list` key is overwrite (last writer wins). The `operator.add` annotation tells
LangGraph to concatenate instead, so every node's returned `audit_events` list is appended
to the existing one. Without this, only the last node to touch `audit_events` would survive.

## Classify: Late-Binding Wrapper

`graph.py` does **not** do `from app.graph.nodes.classify import classify`. It imports the
module (`import app.graph.nodes.classify as classify_module`) and wraps the call in a lambda
that looks up `classify_module.classify` at call time. This allows tests to monkeypatch
`classify_module.classify` after import (e.g. `demo_double_charge.py`) and have the swap
actually take effect. A direct function reference captured at import time would be immune to
reassignment. See DECISIONS.md for full rationale.

## Firestore Schema

Collection: `recovery_runs`. Document ID: `transaction_id` (overwrite on re-run).

Each document contains:
```
transaction_id, batch_run_id, timestamp,
diagnosis: { root_cause, confidence, explanation },
proposed_action, guardrail_result, order_status,
execution_result: { action, status, payment_link_id?, short_url?, error?, note? },
outcome,
audit_trail: [ { node, event, timestamp, ...node-specific fields } ]
```

## Dashboard

React + Vite + TailwindCSS. Reads `recovery_runs` collection from Firestore on load.
Clickable rows open a slide-in Evidence Panel with: AI diagnosis + confidence bar,
policy decision + guardrail result, order status, execution result with a clickable
recovery URL, and a full step timeline with per-node wall-clock timestamps.