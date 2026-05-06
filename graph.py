from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import architect_node, developer_node, tester_node

MAX_ITERATIONS = 5


class AgentState(TypedDict):
    request: str
    design: str
    code: str
    test_result: str
    feedback: str
    iteration: int


def should_continue(state: AgentState) -> Literal["architect", "__end__"]:
    """Route after the Tester: loop back on FAIL, finish on PASS or max retries."""
    if state["test_result"] == "PASS":
        return END
    if state["iteration"] >= MAX_ITERATIONS:
        print(f"\n⚠️  Max iterations ({MAX_ITERATIONS}) reached. Returning last attempt.")
        return END
    return "architect"


def build_graph() -> StateGraph:
    """Construct the Architect → Developer → Tester loop graph."""
    graph = StateGraph(AgentState)

    graph.add_node("architect", architect_node)
    graph.add_node("developer", developer_node)
    graph.add_node("tester", tester_node)

    graph.add_edge(START, "architect")
    graph.add_edge("architect", "developer")
    graph.add_edge("developer", "tester")
    graph.add_conditional_edges("tester", should_continue)

    return graph.compile()
