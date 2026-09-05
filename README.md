# RecoverX — AI-Powered Payment Revenue Recovery Agent

Razorpay AI Buildathon 2026. FastAPI + LangGraph + React + Firebase.

## What it does

Takes a failed Razorpay payment, diagnoses the likely root cause, decides a bounded
recovery action, checks safety guardrails, verifies the current order state, executes
only an approved action, and records a complete audit trail.

**LLM diagnoses. Deterministic code decides. Guardrails authorize. Execution performs.
Audit records everything.** The LLM never directly chooses or executes a money-affecting
action.

## Architecture

1. **Ingest**: Receives a failed transaction.
2. **Classify (AI)**: Uses Gemini to analyze the Razorpay error payload and determine the root cause (with a confidence score).
3. **Decide**: Deterministically maps the root cause to a proposed policy action (e.g., `retry`, `customer_nudge`, `human_review`). Overrides actions to `human_review` if confidence is low.
4. **Guardrails**: Applies strict safety checks (e.g., blocks if max retries exceeded or fraud risk detected).
5. **Order Status Check**: For money-moving actions, verifies the order is actually unpaid via the Razorpay API before proceeding.
6. **Execute**: Performs the final action (e.g., generating a Razorpay Payment Link for a retry).
7. **Audit**: Appends a complete, time-stamped execution timeline and result to Firestore for the dashboard.

## Known Limitations

**Execution Idempotency**: Execution idempotency (preventing duplicate Payment Links on a re-run of the same recovery attempt) is not yet implemented — order-status verification prevents double-charging the customer, but a workflow re-run could currently create a second unused Payment Link for the same failure.

## Honest-uncertainty example

During Razorpay test-mode experimentation we observed:
`error_code=BAD_REQUEST_ERROR`, `error_source=gateway`, `error_step=payment_authorization`,
`error_reason=payment_failed`. This does not prove a specific underlying root cause, so it's
documented to classify as `root_cause=unknown`, `confidence=0.35` — the system reports honest
uncertainty rather than guessing.

## Taxonomy Ambiguity

`authentication_failure` and `customer_action_required` have inherent definitional overlap for OTP/CVV-type failures (both require the customer to take an action to resolve). The LLM may classify an OTP failure as either. This is functionally harmless because the policy table maps both of these root causes to the exact same customer-notification outcome downstream, so the ambiguity does not affect system behavior.

## Setup & Deployment

**Backend (Local Batch Run)**:
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python batch_run.py
```

**Frontend (Dashboard)**:
Run locally with `npm run dev` in the `frontend/` directory. (Designed for Vercel deployment).