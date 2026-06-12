from langgraph.graph import END, START, StateGraph

from graph.nodes import analyst_node, scheduler_node, scout_node
from models.state import GraphState


def _has_matches(state: GraphState) -> str:
    if state.get("matches"):
        return "scout"
    return "end"


def build_graph():
    workflow = StateGraph(GraphState)

    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("analyst", analyst_node)

    workflow.add_edge(START, "scheduler")
    workflow.add_conditional_edges(
        "scheduler",
        _has_matches,
        {"scout": "scout", "end": END},
    )
    workflow.add_edge("scout", "analyst")
    workflow.add_edge("analyst", END)

    return workflow.compile()
