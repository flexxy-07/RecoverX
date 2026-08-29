from langgraph.graph import StateGraph, END

from app.graph.state import RecoveryState
from app.graph.nodes.ingest import ingest
from app.graph.nodes.classify import classify
from app.graph.nodes.decide import decide
from app.graph.nodes.guardrails import guardrails
from app.graph.nodes.order_status_check import order_status_check
from app.graph.nodes.execute import execute
from app.graph.nodes.audit import audit

def guardrail_router(state: RecoveryState) -> str:
  """
  Reads guardrail_result ONLY. This is one of two independent decision points in the graph - see ARCHITECTURE.md for why this is never merged with order_status_router.
  """
  if state['guardrail_result'] == "BLOCKED":
    return "audit"
  return "order_status_check"

def order_status_router(state: RecoveryState) -> str:
  """
  Reads order_status ONLY - never guardrail_result.
  This is the double-charge protection branch: if the order is already resolved, skip execute entirely. 
  """
  if state['order_status'] in {"paid", "captured"}:
    return "audit"
  return "execute"

def build_graph():
  """
  Wires all 7 nodes into the RecoverX recovery workflow and returns a compiled, runnable graph. 
  """
  workflow = StateGraph(RecoveryState)
  
  
  workflow.add_node("ingest", ingest)
  workflow.add_node("classify", classify)
  workflow.add_node("decide", decide)
  workflow.add_node("guardrails", guardrails)
  workflow.add_node("order_status_check", order_status_check)
  workflow.add_node("execute", execute)
  workflow.add_node("audit", audit)
  
  workflow.set_entry_point("ingest")
  
  workflow.add_edge("ingest", "classify")
  workflow.add_edge("classify", "decide")
  workflow.add_edge("decide", "guardrails")
  
  workflow.add_conditional_edges(
    "guardrails",
    guardrail_router,
    {
      "audit" : "audit",
      "order_status_check" : "order_status_check",
    }
  )
  
  workflow.add_conditional_edges(
    "order_status_check",
    order_status_router,
    {
      "audit" : "audit",
      "execute" : "execute",
    } 
  )
 
  workflow.add_edge("execute", "audit")
  workflow.add_edge("audit", END)
  
  return workflow.compile()