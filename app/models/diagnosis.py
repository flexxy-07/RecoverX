from pydantic import BaseModel, Field
from typing import Literal


class Diagnosis(BaseModel):
    """
    The output contract for the classify node. This is the ONLY thing
    classify is allowed to produce — whether it's the current hardcoded
    fake version or a real Gemini call later. Pydantic validation means
    a malformed or out-of-scope value raises an error at creation time,
    not somewhere downstream in decide/guardrails/execute.
    """

    root_cause: Literal[
        "gateway_transient",
        "bank_transient",
        "insufficient_funds",
        "authentication_failure",
        "payment_risk",
        "customer_action_required",
        "unknown",
    ]

    confidence: float = Field(ge=0.0, le=1.0)

    explanation: str