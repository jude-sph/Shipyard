# src/model/agent/chat.py
import json
from pathlib import Path

from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm_with_tools
from src.core.models.core import ProjectModel
from src.model.agent.tools import TOOL_DEFINITIONS, apply_tool

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_system_prompt() -> str:
    """Load the agent system prompt from agent_system.txt."""
    return (PROMPTS_DIR / "agent_system.txt").read_text()


def _build_summary(project: ProjectModel) -> str:
    """Build summary counts for agent context."""
    num_reqs = len(project.requirements)
    num_digs = len(project.decomposition_trees)
    num_elements = sum(
        sum(len(v) for v in layer.values() if isinstance(v, list))
        for layer in project.layers.values()
        if isinstance(layer, dict)
    )
    num_links = len(project.links)
    covered = len({l.source for l in project.links if any(r.id == l.source for r in project.requirements)})
    coverage_pct = round(covered / num_reqs * 100) if num_reqs else 0

    return (f"Project: {project.project.name} ({project.project.mode})\n"
            f"{num_digs} decomposed DIGs, {num_reqs} requirements, "
            f"{num_elements} model elements, {num_links} links, "
            f"{coverage_pct}% coverage ({num_reqs - covered} uncovered)")


def _build_system_prompt(project: ProjectModel, mode: str = "model") -> str:
    """Build system prompt for the agent."""
    summary = _build_summary(project)
    base_prompt = _load_system_prompt()
    return f"{base_prompt}\n\n## Current Project State\n\n{summary}\n\nThe engineer is currently in {mode} mode."


def chat_with_agent(
    project: ProjectModel,
    user_message: str,
    conversation_history: list[dict],
    tracker: CostTracker,
    mode: str = "model",
) -> tuple[str, list[dict]]:
    """Send a message to the chat agent. Returns (agent_response_text, updated_history).

    The agent may call tools to modify the project. Tool calls are executed
    automatically in a loop until the agent produces a final text response
    or the iteration limit is reached.
    """
    full_system = _build_system_prompt(project, mode)

    # Build messages
    messages = [{"role": "system", "content": full_system}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    # Tool-calling loop
    max_iterations = 10
    for _ in range(max_iterations):
        response = call_llm_with_tools(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            cost_tracker=tracker,
            call_type="chat_agent",
            stage="chat",
        )

        choice = response.choices[0]
        if choice.finish_reason == "tool_calls" or (
            hasattr(choice.message, "tool_calls") and choice.message.tool_calls
        ):
            # Execute each tool call and append results
            messages.append(choice.message)
            for tool_call in choice.message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = apply_tool(project, tool_call.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })
        else:
            # Final text response
            agent_text = choice.message.content or ""
            # Return updated history without the system message
            updated_history = messages[1:]
            return agent_text, updated_history

    return (
        "I've reached the maximum number of tool call iterations. Please try a simpler request.",
        messages[1:],
    )
