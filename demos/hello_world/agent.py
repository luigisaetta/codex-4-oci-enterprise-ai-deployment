"""
Author: L. Saetta
Date last modified: 2026-09-22
License: MIT
Description: Build a LangGraph workflow that greets the supplied name.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class GreetingState(TypedDict, total=False):
    """Per-invocation input name and generated greeting."""

    name: str
    message: str


def greet(state: GreetingState) -> GreetingState:
    """Generate the greeting for a validated input.

    Args:
        state: Graph state containing the input name.

    Returns:
        The message update for this invocation.
    """
    return {"message": f"Hello {state['name']}"}


def build_agent() -> CompiledStateGraph:
    """Compile the single-node greeting workflow.

    Returns:
        An executable LangGraph with no persistence or external dependencies.
    """
    builder = StateGraph(GreetingState)
    builder.add_node("greet", greet)
    builder.add_edge(START, "greet")
    builder.add_edge("greet", END)
    return builder.compile()
