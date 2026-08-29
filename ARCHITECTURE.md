# ARCHITECTURE.md

Living document. Updated whenever the architecture changes.

## Flow

\`\`\`
Razorpay
   ↓
FastAPI
   ↓
LangGraph Recovery Workflow
   ↓
ingest → classify → decide → guardrails → order_status_check
   ↓
conditional routing
 ├── already resolved → audit → END
 └── unpaid → execute → audit → END
   ↓
Firestore (later)
\`\`\`

## Nodes

| Node | Responsibility |
|---|---|
| `ingest` | Load/normalize the incoming failed-transaction record into state |
| `classify` | Diagnose root cause (fake for now; Gemini later) — never crashes the graph |
| `decide` | Deterministic policy lookup + confidence gate → `proposed_action` |
| `guardrails` | Hard-block unsafe actions (`payment_risk`, retry cap) → `guardrail_result` |
| `order_status_check` | Double-charge protection — checks live order state → `order_status` |
| `execute` | Fake execution of the approved action |
| `audit` | Print/record the accumulated audit trail |

## Two independent routers

- `guardrail_router` reads `guardrail_result` only.
- `order_status_router` reads `order_status` only.

They are kept separate on purpose: guardrails answer "is this action *safe* to attempt at
all" (root cause / retry count), while order-status answers "has reality already changed
underneath us" (double-charge protection). Conflating them into one router would hide which
of two independent failure modes triggered a block.

## State shape

`RecoveryState` (TypedDict) — see `app/graph/state.py`. Key design point:
`audit_events: Annotated[list, operator.add]` so audit events accumulate across nodes instead
of each node's return value overwriting the previous one (LangGraph's default merge behavior
for a plain list key is overwrite, not append).

## Not yet built

Gemini integration, Razorpay integration, Firestore, Flutter, real execution, dashboard,
production auth.


## Implementation note: classify is registered via a late-binding wrapper

`graph.py` does NOT do `from app.graph.nodes.classify import classify`. It imports the
module and wraps the call in a lambda that looks up `classify_module.classify` at call
time, not at import time. This is required for tests to be able to swap in different fake
diagnosis behavior per scenario (see run_test.py). See DECISIONS.md for the full story.


guardrail_router now also checks proposed_action for the money-moving-actions filter, so a future reader doesn't have to rediscover this from the code alone.