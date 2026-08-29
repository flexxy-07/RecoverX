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