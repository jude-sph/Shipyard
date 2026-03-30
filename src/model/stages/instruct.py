# src/model/stages/instruct.py
import json
import logging
from pathlib import Path
from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def generate_instructions(mode: str, model_data: dict, tracker: CostTracker, client=None, emit=None, model: str | None = None) -> dict:
    """Stage 5: Generate tool-specific recreation instructions. Returns {tool: ..., steps: [...]}.

    For large models, generates instructions per layer and merges them to avoid
    exceeding the LLM's output token limit.
    """
    _emit = emit or (lambda e: None)
    prompt_file = "instruct_capella.txt" if mode == "capella" else "instruct_rhapsody.txt"
    template = (PROMPTS_DIR / prompt_file).read_text()
    tool_name = "Capella 7.0" if mode == "capella" else "IBM Rhapsody 10.0"

    layers = model_data.get("layers", {})

    # For small models (1-2 layers), do it in one call
    if len(layers) <= 2:
        model_json = json.dumps(model_data, indent=2)
        prompt = template.format(model=model_json)
        return call_llm(prompt=prompt, cost_tracker=tracker, call_type="instruct",
                        stage="instruct", max_tokens=8192, client=client, model=model)

    # For larger models, generate instructions per layer and merge
    all_steps = []
    step_num = 1

    # First: general setup step
    setup = {"layers": {k: {} for k in layers}}
    setup_json = json.dumps(setup, indent=2)
    prompt = template.format(model=setup_json)
    # Add instruction to only output project setup steps
    prompt += "\n\nIMPORTANT: Only output the initial project setup steps (creating the project, configuring the profile). Do NOT output steps for individual elements -- those will be generated separately. Keep it to 3-5 setup steps maximum."
    try:
        result = call_llm(prompt=prompt, cost_tracker=tracker, call_type="instruct",
                          stage="instruct_setup", max_tokens=4096, client=client, model=model)
        for step in result.get("steps", []):
            step["step"] = step_num
            all_steps.append(step)
            step_num += 1
    except Exception as exc:
        logger.warning(f"Setup instruction generation failed: {exc}. Adding generic setup step.")
        all_steps.append({"step": step_num, "action": f"Create new {tool_name} project",
                          "detail": "Create a new project in the modeling tool.", "layer": "general"})
        step_num += 1

    # Then: per-layer instructions
    layer_keys = list(layers.keys())
    total_layers = len(layer_keys)
    for li, layer_key in enumerate(layer_keys, 1):
        _emit({"stage": "instruct", "status": "running", "detail": f"Writing steps for {layer_key} ({li}/{total_layers})..."})
        layer_data = layers[layer_key]
        single_layer = {"layers": {layer_key: layer_data}}
        layer_json = json.dumps(single_layer, indent=2)
        prompt = template.format(model=layer_json)
        prompt += f"\n\nIMPORTANT: Only output steps for the {layer_key} layer elements shown above. Do NOT include project setup steps. Start step numbering at {step_num}."
        try:
            result = call_llm(prompt=prompt, cost_tracker=tracker, call_type="instruct",
                              stage=f"instruct_{layer_key}", max_tokens=4096, client=client, model=model)
            for step in result.get("steps", []):
                step["step"] = step_num
                step["layer"] = layer_key
                all_steps.append(step)
                step_num += 1
        except Exception as exc:
            logger.warning(f"Instruction generation for {layer_key} failed: {exc}. Skipping.")
            all_steps.append({"step": step_num, "action": f"Create {layer_key} elements",
                              "detail": f"Manually create the elements shown in the {layer_key} layer of the model tree.",
                              "layer": layer_key})
            step_num += 1

    return {"tool": tool_name, "steps": all_steps}
