from app.graph.state import RecoveryState
from app.models.diagnosis import Diagnosis


def classify(state: RecoveryState) -> dict:
    """
    FAKE classify node. Later this will call Gemini with the transaction
    details and parse its structured output into a Diagnosis. For now it
    returns a hardcoded diagnosis so we can build and test the rest of
    the graph without any real LLM dependency.

    The try/except here is not decorative — it's rehearsing the exact
    failure-handling shape the real Gemini call will need: ANY failure
    must fall back to a safe, valid Diagnosis (unknown / 0.0) instead of
    crashing the graph, and the fallback must be visible in the audit
    trail, never silent.
    """
    try:
        # --- FAKE diagnosis logic ---
        # In the real version, this block calls Gemini and validates its
        # response into a Diagnosis. For now: hardcoded.
        diagnosis = Diagnosis(
            root_cause="gateway_transient",
            confidence=0.94,
            explanation="Fake diagnosis for skeleton testing.",
        )

        return {
            "diagnosis": diagnosis.model_dump(),
            "audit_events": [
                {
                    "node": "classify",
                    "event": "diagnosis_completed",
                    "root_cause": diagnosis.root_cause,
                    "confidence": diagnosis.confidence,
                }
            ],
        }

    except Exception as e:
        # Safe fallback — the graph must NEVER crash here. This is the
        # one place classify.py is allowed to silently absorb an error,
        # because we immediately turn it into a visible, honest state:
        # unknown/0.0, plus an audit event that says exactly what broke.
        fallback = Diagnosis(
            root_cause="unknown",
            confidence=0.0,
            explanation="Diagnosis failed; safe fallback applied.",
        )

        return {
            "diagnosis": fallback.model_dump(),
            "audit_events": [
                {
                    "node": "classify",
                    "event": "diagnosis_failed",
                    "error": str(e),
                }
            ],
        }