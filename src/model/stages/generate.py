# src/model/stages/generate.py
import json
from pathlib import Path
from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm
from src.core.models.core import Requirement

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PROMPT_MAP = {
    ("capella", "operational_analysis"): "generate_capella_oa.txt",
    ("capella", "system_needs_analysis"): "generate_capella_sa.txt",
    ("capella", "system_analysis"): "generate_capella_sa.txt",  # backward compat
    ("capella", "logical_architecture"): "generate_capella_la.txt",
    ("capella", "physical_architecture"): "generate_capella_pa.txt",
    ("capella", "epbs"): "generate_capella_epbs.txt",
    ("rhapsody", "requirements_diagram"): "generate_rhapsody_req.txt",
    ("rhapsody", "block_definition"): "generate_rhapsody_bdd.txt",
    ("rhapsody", "internal_block"): "generate_rhapsody_ibd.txt",
    ("rhapsody", "activity_diagram"): "generate_rhapsody_act.txt",
    ("rhapsody", "sequence_diagram"): "generate_rhapsody_seq.txt",
    ("rhapsody", "state_machine"): "generate_rhapsody_stm.txt",
}


def generate_layer(mode: str, layer_key: str, requirements: list[Requirement], tracker: CostTracker, client=None, existing_elements=None, model: str | None = None) -> dict:
    """Stage 3: Generate model elements for a single layer/diagram type."""
    prompt_file = PROMPT_MAP.get((mode, layer_key))
    if not prompt_file:
        raise ValueError(f"No prompt template for mode={mode}, layer={layer_key}")
    template = (PROMPTS_DIR / prompt_file).read_text()
    reqs_json = json.dumps([r.model_dump() for r in requirements], indent=2)

    existing_ctx = ""
    if existing_elements:
        existing_ctx = _format_existing_elements(existing_elements)

    prompt = template.format(requirements=reqs_json, existing_elements=existing_ctx)
    return call_llm(prompt=prompt, cost_tracker=tracker, call_type="generate",
                    stage=f"generate_{layer_key}", max_tokens=8192, client=client, model=model)


def _format_existing_elements(layer_data: dict) -> str:
    """Format existing layer elements as a compact summary for the prompt."""
    if not layer_data:
        return ""
    lines = ["\nExisting elements in this layer (DO NOT recreate these, reference by ID when relevant):"]
    for collection_key, elements in layer_data.items():
        if not isinstance(elements, list) or not elements:
            continue
        for elem in elements:
            if isinstance(elem, dict):
                eid = elem.get("id", "?")
                name = elem.get("name", "?")
                etype = elem.get("type", collection_key)
                lines.append(f"- {eid}: {name} ({etype})")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)
