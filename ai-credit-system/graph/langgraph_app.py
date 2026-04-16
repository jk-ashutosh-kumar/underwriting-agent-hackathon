"""Real LangGraph orchestration wrapper for underwriting flow.

Migration notes:
- We intentionally reuse node business logic from ``graph.flow``.
- The original ``flow.py`` remains source-of-truth and fallback path.
- This module only handles graph wiring, checkpointing, and interrupt/resume.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from graph.flow import decision_node, hitl_node, resume_node, router_node, run_analysis_node
from graph.state import UnderwritingState, create_initial_state

logger = logging.getLogger(__name__)

RouteName = Literal["approve", "hitl", "review"]


class LangGraphState(UnderwritingState, total=False):
    """LangGraph state extends core flow state with orchestration metadata."""

    route: RouteName
    committee_output: Dict[str, Any]


class LangGraphRunResult(TypedDict, total=False):
    status: Literal["COMPLETED", "NEEDS_INPUT"]
    thread_id: str
    state: UnderwritingState
    route: RouteName


class UnderwritingLangGraph:
    """Compiled graph runtime with in-memory checkpointing."""

    def __init__(self) -> None:
        self.checkpointer = MemorySaver()
        # Fallback store for older langgraph runtimes without get_state/update_state.
        self._pending_states: Dict[str, LangGraphState] = {}
        graph = StateGraph(LangGraphState)

        # Node wrappers intentionally call existing business logic.
        graph.add_node("analysis", self._analysis_node)
        graph.add_node("router", self._router_node)
        graph.add_node("hitl", self._hitl_node)
        graph.add_node("resume", self._resume_node)
        graph.add_node("decision", self._decision_node)

        # Compatibility across langgraph versions:
        # - newer versions support START -> node edge
        # - older versions expect set_entry_point(node)
        entry_wired = False
        try:
            from langgraph.graph import START  # type: ignore

            graph.add_edge(START, "analysis")
            entry_wired = True
        except Exception:
            entry_wired = False
        if not entry_wired:
            graph.set_entry_point("analysis")
        graph.add_edge("analysis", "router")
        graph.add_conditional_edges(
            "router",
            self._route_selector,
            {
                "approve": "decision",
                "hitl": "hitl",
                "review": "decision",
            },
        )
        graph.add_edge("hitl", "resume")
        graph.add_edge("resume", "decision")
        graph.add_edge("decision", END)

        # Interrupt before HITL enables pause/resume.
        self.graph = graph.compile(
            checkpointer=self.checkpointer,
            interrupt_before=["hitl"],
        )

    @staticmethod
    def _analysis_node(state: LangGraphState) -> LangGraphState:
        return run_analysis_node(state)

    @staticmethod
    def _router_node(state: LangGraphState) -> Dict[str, Any]:
        route = router_node(state)
        # Preserve state updates from router and expose route for edge selection.
        return {
            "risk_score": state["risk_score"],
            "agent_logs": state["agent_logs"],
            "decision_status": state["decision_status"],
            "human_input": state.get("human_input", ""),
            "region": state["region"],
            "applicant_data": state["applicant_data"],
            "route": route,
            "committee_output": state.get("committee_output"),
        }

    @staticmethod
    def _route_selector(state: Dict[str, Any]) -> RouteName:
        route = str(state.get("route", "review"))
        if route in {"approve", "hitl", "review"}:
            return route  # type: ignore[return-value]
        return "review"

    @staticmethod
    def _hitl_node(state: LangGraphState) -> LangGraphState:
        # Resume flow should provide ``human_input`` in state before this node runs.
        return hitl_node(state, interactive=False, human_response=state.get("human_input", ""))

    @staticmethod
    def _resume_node(state: LangGraphState) -> LangGraphState:
        return resume_node(state)

    @staticmethod
    def _decision_node(state: LangGraphState) -> LangGraphState:
        return decision_node(state)

    def _config(self, thread_id: str) -> Dict[str, Dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}

    def run(
        self,
        data: Dict[str, Any],
        region: str,
        *,
        thread_id: str,
        human_input: Optional[str] = None,
    ) -> LangGraphRunResult:
        """Run or resume execution for a single thread."""
        config = self._config(thread_id)
        has_state_api = hasattr(self.graph, "get_state") and hasattr(self.graph, "update_state")
        state: LangGraphState = create_initial_state(data, region)
        values: Dict[str, Any] = {}

        if has_state_api:
            snapshot = self.graph.get_state(config)
            if not snapshot.values:
                # First invocation for this thread.
                initial_state = create_initial_state(data, region)
                logger.info("langgraph_invoke_start thread_id=%s region=%s", thread_id, region)
                self.graph.invoke(initial_state, config=config)
            else:
                # Resume path: update human input before continuing.
                if human_input is not None:
                    self.graph.update_state(config, {"human_input": human_input})
                logger.info("langgraph_invoke_resume thread_id=%s has_human_input=%s", thread_id, bool(human_input))
                self.graph.invoke(None, config=config)

            after = self.graph.get_state(config)
            values = dict(after.values or {})
            state.update(values)

            next_nodes = tuple(after.next or ())
            if "hitl" in next_nodes:
                logger.info("langgraph_paused_for_hitl thread_id=%s", thread_id)
                return {
                    "status": "NEEDS_INPUT",
                    "thread_id": thread_id,
                    "state": state,
                    "route": "hitl",
                }
        else:
            # Older runtime compatibility: preserve pause/resume semantics manually.
            # We intentionally reuse existing node logic from flow.py so behavior matches.
            logger.warning("langgraph_state_api_unavailable_using_fallback thread_id=%s", thread_id)
            if human_input is None:
                initial_state = create_initial_state(data, region)
                logger.info("langgraph_invoke_start_legacy thread_id=%s region=%s", thread_id, region)
                state = run_analysis_node(initial_state)
                route = router_node(state)
                state["route"] = route
                if route == "hitl":
                    self._pending_states[thread_id] = state
                    logger.info("langgraph_paused_for_hitl_legacy thread_id=%s", thread_id)
                    return {
                        "status": "NEEDS_INPUT",
                        "thread_id": thread_id,
                        "state": state,
                        "route": "hitl",
                    }
                # approve/review both continue to final decision in this flow design.
                state = decision_node(state)
            else:
                logger.info("langgraph_invoke_resume_legacy thread_id=%s", thread_id)
                state = self._pending_states.pop(thread_id, create_initial_state(data, region))
                state["human_input"] = human_input
                # Continue explicitly from HITL path to preserve behavior.
                state = hitl_node(state, interactive=False, human_response=human_input)
                state = resume_node(state)
                state = decision_node(state)
                state["route"] = "hitl"

        if not isinstance(state, dict):
            state = create_initial_state(data, region)
        if not isinstance(values, dict):
            values = {}
        route = str(state.get("route", values.get("route", "review")))
        if route not in {"approve", "hitl", "review"}:
            route = "review"
        logger.info(
            "langgraph_completed thread_id=%s route=%s decision=%s",
            thread_id,
            route,
            state.get("decision_status"),
        )
        return {
            "status": "COMPLETED",
            "thread_id": thread_id,
            "state": state,
            "route": route,  # type: ignore[typeddict-item]
        }


# Singleton runtime reused by API requests.
LANGGRAPH_RUNTIME = UnderwritingLangGraph()
