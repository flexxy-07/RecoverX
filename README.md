# RecoverX — AI-Powered Payment Revenue Recovery Agent

Razorpay AI Buildathon 2026. FastAPI + LangGraph + Pydantic.

## What it does

Takes a failed Razorpay payment, diagnoses the likely root cause, decides a bounded
recovery action, checks safety guardrails, verifies the current order state, executes
only an approved action, and records a complete audit trail.

**LLM diagnoses. Deterministic code decides. Guardrails authorize. Execution performs.
Audit records everything.** The LLM never directly chooses or executes a money-affecting
action.

## Status

Phase 1: project skeleton only. Nodes are empty stubs — logic comes in Phase 2.

## Honest-uncertainty example

During Razorpay test-mode experimentation we observed:
`error_code=BAD_REQUEST_ERROR`, `error_source=gateway`, `error_step=payment_authorization`,
`error_reason=payment_failed`. This does not prove a specific underlying root cause, so it's
documented to classify as `root_cause=unknown`, `confidence=0.35` — the system reports honest
uncertainty rather than guessing.

## Taxonomy Ambiguity

`authentication_failure` and `customer_action_required` have inherent definitional overlap for OTP/CVV-type failures (both require the customer to take an action to resolve). The LLM may classify an OTP failure as either. This is functionally harmless because the policy table maps both of these root causes to the exact same customer-notification outcome downstream, so the ambiguity does not affect system behavior.

## Setup (Windows)

\`\`\`powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
\`\`\`