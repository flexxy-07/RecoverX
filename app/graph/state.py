from typing import Annotated
from typing_extensions import TypedDict
import operator

class RecoveryState(TypedDict):
  """
    Shared state passed between every node in the RecoverX recovery graph.
    Each node receives the current state and returns a partial dict of
    updates, which LangGraph merges back in before calling the next node.
  """
  transaction: dict
  diagnosis: dict | None
  proposed_action: str | None
  guardrail_result: str | None
  order_status: str | None
  execution_result: dict | None
  retry_history: list
  # Every node appends its own audit event here. operator.add means
    # LangGraph CONCATENATES each node's returned list onto the existing
    # one, instead of overwriting it — without this, only the last node
    # to touch audit_events would "win" and every earlier entry would
    # silently vanish.
  audit_events: Annotated[list, operator.add]