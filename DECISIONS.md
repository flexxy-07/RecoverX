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