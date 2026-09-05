import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai

from app.graph.state import RecoveryState
from app.models.diagnosis import Diagnosis

load_dotenv()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in environment or .env")
    return genai.Client(api_key=api_key)

SYSTEM_PROMPT = """You are a payment failure diagnosis classifier for RecoverX, a payment
recovery system. Your ONLY job is to classify why a payment failed. You
must NOT recommend, suggest, or imply any recovery action — that
decision is made by separate, deterministic code, never by you.

Classify the failure into EXACTLY ONE of these 7 categories:

- gateway_transient: A temporary failure at the payment gateway level
  (e.g. gateway timeout, temporary gateway error) likely to succeed if
  retried shortly.
- bank_transient: A temporary failure at the issuing bank's end (e.g.
  bank system timeout) likely to succeed if retried later.
- insufficient_funds: The payment failed because the customer's account
  or card had insufficient funds.
- authentication_failure: The payment failed due to authentication
  issues (e.g. failed OTP, 3D Secure failure, incorrect CVV).
- payment_risk: The payment was blocked or flagged due to fraud/risk
  detection systems (gateway-side or bank-side).
- customer_action_required: The failure requires the customer to take
  action outside of a simple retry (e.g. expired card, blocked card,
  needs to update payment method).
- unknown: The evidence provided is insufficient to confidently
  determine the root cause, OR the failure doesn't clearly fit any
  category above.

CRITICAL RULES:
- Do NOT invent or assume information not present in the provided data.
- If the evidence is ambiguous, incomplete, or could fit multiple
  categories, you MUST return "unknown" rather than guessing.
- Do NOT recommend, mention, or imply any recovery action, retry
  strategy, or next step. Diagnosis only.
- Provide a confidence score reflecting your actual certainty — do not
  default to high confidence out of habit. A vague or generic error
  description should produce LOW confidence.
- Your explanation should describe the reasoning for the classification
  in 1-2 sentences, based only on the provided evidence."""

def _build_payload(transaction: dict) -> dict:
    """
    Extracts ONLY the fields Gemini needs to diagnose the failure. Deliberately exludes customer_email, transaction id, and any other field not explicitly required for diagnosis. This is what we actually enforces the "no unnecessary PII" rule, not just a policy in prose.
    """
    return {
        "amount": transaction.get("amount"),
        "currency": transaction.get("currency"),
        "method": transaction.get("method"),
        "error_code": transaction.get("error_code"),
        "error_description": transaction.get("error_description"),
        "error_source": transaction.get("error_source"),
        "error_step": transaction.get("error_step"),
        "error_reason": transaction.get("error_reason"),
    }

def _call_gemini(transaction: dict) -> Diagnosis:
    """
    The actual Gemini call. Allowed to raise - classify() below is responsible for catching failures. kept separate from classify() so tests can monkeypatch this specific function and still exercise classify()'s REAL try/except fallback logic, not a test stand-in.
    """
    
    payload = _build_payload(transaction)
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=(
            f"Payment failure details: \n{payload}\n\n"
            "Classify the failure."
        ), 
        config={
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "response_schema": Diagnosis,
        },
    )
    # response.parsed is already a validated Diagnosis instance when
    # response_schema is a Pydantic model. If Gemini's output doesn't
    # match the schema, the SDK/Pydantic raises here rather than
    # returning a broken object — that failure propagates up to
    # classify()'s except block below.
    diagnosis = response.parsed
    if isinstance(diagnosis, Diagnosis):
        return diagnosis
    if isinstance(diagnosis, dict):
        return Diagnosis.model_validate(diagnosis)
    if response.text:
        return Diagnosis.model_validate_json(response.text)
    raise ValueError("Gemini returned no parsable Diagnosis output.")
def classify(state: RecoveryState) -> dict:
    transaction = state["transaction"]

    try:
        diagnosis = _call_gemini(transaction)

        return {
            "diagnosis": diagnosis.model_dump(),
            "audit_events": [
                {
                    "node": "classify",
                    "event": "diagnosis_completed",
                    "root_cause": diagnosis.root_cause,
                    "confidence": diagnosis.confidence,
                    "timestamp": _now(),
                }
            ],
        }

    except Exception as e:
        # Fallback construction is hardcoded and known-valid, so this
        # itself should never fail — but if it somehow did, we'd rather
        # know than crash silently. Print here as a last-resort signal,
        # separate from the audit trail (which depends on this succeeding).
        print(f"[classify] Gemini call failed: {e}")

        fallback = Diagnosis(
            root_cause="unknown",
            confidence=0.0,
            explanation="Automated diagnosis unavailable. Safe fallback applied.",
        )

        return {
            "diagnosis": fallback.model_dump(),
            "audit_events": [
                {
                    "node": "classify",
                    "event": "diagnosis_failed",
                    "error": str(e),
                    "timestamp": _now(),
                }
            ],
        }