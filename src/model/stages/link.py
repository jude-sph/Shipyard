# src/model/stages/link.py
import json
from pathlib import Path
from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm
from src.core.models.core import Requirement

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def generate_links(mode: str, layers: dict, requirements: list[Requirement], tracker: CostTracker, client=None, existing_links=None, model: str | None = None) -> dict:
    """Stage 4: Generate cross-element links. Returns {links: [...]}."""
    template = (PROMPTS_DIR / "link.txt").read_text()
    reqs_json = json.dumps([r.model_dump() for r in requirements], indent=2)
    layers_json = json.dumps(layers, indent=2)

    # Select valid link types based on mode
    if mode == "capella":
        link_types = "satisfies, realizes, implements, allocates, communicates, traces, involves, exchanges"
    else:
        link_types = "deriveReqt, satisfy, refine, trace, allocate"

    # Format existing links context if provided
    if existing_links:
        lines = ["Existing links (DO NOT recreate these):"]
        for lnk in existing_links:
            lines.append(f"- {lnk['id']}: {lnk['source']} --{lnk['type']}--> {lnk['target']}")
        lines.append("Generate only NEW links for the new elements and requirements below.")
        existing_links_context = "\n".join(lines)
    else:
        existing_links_context = ""

    prompt = template.format(
        requirements=reqs_json,
        layers=layers_json,
        link_types=link_types,
        mode=mode,
        existing_links=existing_links_context,
    )
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="link", stage="link", client=client, model=model)
