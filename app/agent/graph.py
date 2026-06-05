from __future__ import annotations

from app.agent.observability import timed_step
from app.agent import nodes


class AgentGraph:
    def run(self, state, *, use_web: bool = True, include_system_context: bool = True, mode: str = "auto"):
        with timed_step("normalize_input", state.timings_ms):
            state = nodes.normalize_input(state)
        with timed_step("classify_intent", state.timings_ms):
            state = nodes.classify_intent(state)
        with timed_step("load_context", state.timings_ms):
            state = nodes.load_context(state, include_system_context=include_system_context)
        with timed_step("decide_mode", state.timings_ms):
            state = nodes.decide_mode(state, use_web=use_web, requested_mode=mode)
        with timed_step("retrieve_memory", state.timings_ms):
            state = nodes.retrieve_memory(state)
        with timed_step("retrieve_knowledge", state.timings_ms):
            state = nodes.retrieve_knowledge(state)
        with timed_step("decide_web_need", state.timings_ms):
            state = nodes.decide_web_need(state, use_web=use_web)
        with timed_step("web_research_if_needed", state.timings_ms):
            state = nodes.web_research_if_needed(state)
        with timed_step("specialist_analysis", state.timings_ms):
            state = nodes.specialist_analysis(state)
        with timed_step("select_tools", state.timings_ms):
            state = nodes.select_tools(state)
        with timed_step("safety_check", state.timings_ms):
            state = nodes.safety_check(state)
        with timed_step("create_plan", state.timings_ms):
            state = nodes.create_plan_node(state)
        with timed_step("generate_draft", state.timings_ms):
            state = nodes.generate_draft(state)
        with timed_step("verify_evidence", state.timings_ms):
            state = nodes.verify_evidence(state)
        with timed_step("critic_review", state.timings_ms):
            state = nodes.critic_review(state)
        with timed_step("format_final", state.timings_ms):
            state = nodes.format_final(state)
        return state
