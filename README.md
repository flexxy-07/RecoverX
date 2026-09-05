# RecoverX — AI-Powered Payment Recovery Agent

Razorpay AI Buildathon 2026. LangGraph + LLM + React + Firestore.

## What it does

Takes a failed Razorpay payment and runs it through a 7-node autonomous recovery graph:
diagnoses the root cause with LLM, applies a deterministic policy to pick a recovery
action, enforces safety guardrails, verifies current order state via the Razorpay API,
executes the action (real Payment Links in test mode), and writes a full timestamped audit
trail to Firestore for the dashboard.

**The LLM diagnoses. Deterministic code decides. Guardrails authorize. The LLM never
directly chooses or executes a money-affecting action.**

## Architecture

```
Failed Razorpay Transaction
   ↓
ingest → classify (LLM) → decide → guardrails
                                           ↓
                              ┌────────────────────────┐
                              │ BLOCKED → audit → END  │
                              └────────────────────────┘
                                           ↓ ALLOWED
                              order_status_check (Razorpay API)
                                           ↓
                              ┌────────────────────────┐
                              │ paid/captured → audit  │
                              └────────────────────────┘
                                           ↓ unpaid
                                        execute
                                           ↓
                                         audit → Firestore → Dashboard
```

| Node | What it does |
|---|---|
| `ingest` | Normalises the incoming failed-transaction dict into `RecoveryState` |
| `classify` | Calls LLM with the Razorpay error payload; returns `Diagnosis(root_cause, confidence, explanation)`. Falls back to `unknown / 0.0` if LLM fails. |
| `decide` | Deterministic policy table: root_cause → action. Overrides to `human_review` if `confidence < 0.6`. |
| `guardrails` | Hard-blocks `payment_risk` transactions and transactions exceeding the retry cap. |
| `order_status_check` | Live Razorpay order fetch — only runs for `retry` / `retry_later`. If order is `paid` or `captured`, routes to `audit` (no execution). |
| `execute` | Creates a Razorpay Payment Link for retries; logs nudge/review flags for other actions. |
| `audit` | Writes the full `audit_trail` + all state fields to Firestore (`recovery_runs/{transaction_id}`). |

## Running it

**Backend (batch mode):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python batch_run.py        # processes data/transactions.json → Firestore
```


**Frontend dashboard:**
```powershell
cd frontend
npm install
npm run dev        
```

## Known Limitations

**Execution Idempotency**: A re-run of the same recovery attempt (same `transaction_id`) can
create a second, unused Razorpay Payment Link. The order-status check prevents the customer
from being double-*charged* (it won't re-execute if the order is already paid), but a
redundant link is still generated. Fix: check Firestore for an existing
`execution_result.payment_link_id` before calling the Payment Links API. Not shipped due
to deadline constraints; identified and documented via a live test
(`test_idempo.py`).



**Notification infrastructure**: `customer_nudge` and `customer_action` execution steps
log intent only — there is no email/SMS/webhook sending built. The payment link exists; delivery
is a notification-infra concern outside the scope of this buildathon.

## Honest-uncertainty examples

- `BAD_REQUEST_ERROR / gateway / payment_failed` with no further signal: classified as
  `root_cause=unknown, confidence=0.35` — the system reports honest uncertainty rather than guessing.

- `authentication_failure` and `customer_action_required` overlap for OTP/CVV failures.
  Functionally harmless: both map to the same policy action (`customer_nudge`). See DECISIONS.md.