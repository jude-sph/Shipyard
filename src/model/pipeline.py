import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.core.config import MODEL_PRICING
from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm, create_client
from src.core.models.core import MBSEModel, Meta, Requirement, Link, ProjectModel, BatchRecord
from src.model.stages import analyze_requirements, apply_clarifications, generate_layer, generate_links, generate_instructions

logger = logging.getLogger(__name__)

STAGE_RETRIES = 2  # Total attempts per stage (1 original + 1 retry)
STAGE_RETRY_DELAY = 3  # Seconds between retries


def _run_with_retry(fn, stage_name, emit):
    """Run a stage function with retry logic. Returns the result or raises."""
    for attempt in range(1, STAGE_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt < STAGE_RETRIES:
                logger.warning(f"Stage '{stage_name}' failed (attempt {attempt}): {exc}. Retrying in {STAGE_RETRY_DELAY}s...")
                emit({"stage": stage_name, "status": "running", "detail": f"Retrying after error (attempt {attempt + 1})..."})
                time.sleep(STAGE_RETRY_DELAY)
            else:
                raise


def estimate_cost(requirements: list[Requirement], mode: str, selected_layers: list[str], model: str) -> dict:
    """Pre-run cost estimation. Returns dict with call breakdown and cost range."""
    pricing = MODEL_PRICING.get(model, {})
    input_rate = pricing.get("input_per_mtok", 0.0)
    output_rate = pricing.get("output_per_mtok", 0.0)

    num_reqs = len(requirements)
    num_layers = len(selected_layers)

    # Estimate token counts per stage
    # analyze: prompt ~500 + reqs ~100/each, output ~500
    analyze_in = 500 + num_reqs * 100
    analyze_out = 500

    # generate: prompt ~1500 + reqs ~100/each, output ~1000-2000 per layer
    gen_in = 1500 + num_reqs * 100
    gen_out_min = 800
    gen_out_max = 2000

    # link: prompt ~500 + all elements ~200/layer + reqs, output ~500-1500
    link_in = 500 + num_layers * 200 + num_reqs * 100
    link_out_min = 500
    link_out_max = 1500

    # instruct: prompt ~500 + model ~200/layer, output ~500-2000
    instruct_in = 500 + num_layers * 200
    instruct_out_min = 500
    instruct_out_max = 2000

    total_calls = 1 + num_layers + 1 + 1  # analyze + generate(N) + link + instruct

    min_tokens_in = analyze_in + gen_in * num_layers + link_in + instruct_in
    max_tokens_in = min_tokens_in  # input is deterministic
    min_tokens_out = analyze_out + gen_out_min * num_layers + link_out_min + instruct_out_min
    max_tokens_out = analyze_out + gen_out_max * num_layers + link_out_max + instruct_out_max

    min_cost = (min_tokens_in * input_rate + min_tokens_out * output_rate) / 1_000_000
    max_cost = (max_tokens_in * input_rate + max_tokens_out * output_rate) / 1_000_000

    return {
        "total_calls": total_calls,
        "num_requirements": num_reqs,
        "num_layers": num_layers,
        "model": model,
        "estimated_min_cost": round(min_cost, 4),
        "estimated_max_cost": round(max_cost, 4),
        "clarify_note": "Clarification stage may add 1 additional call if ambiguities are detected",
        "breakdown": [
            {"stage": "analyze", "calls": 1},
            {"stage": "generate", "calls": num_layers},
            {"stage": "link", "calls": 1},
            {"stage": "instruct", "calls": 1},
        ]
    }


def fix_id_collisions(new_elements: list[dict], existing_ids: set[str]) -> list[dict]:
    """Rename new element IDs that collide with existing ones."""
    import re
    used_ids = set(existing_ids)
    for elem in new_elements:
        eid = elem.get("id", "")
        if eid in used_ids:
            # Extract prefix and number, increment until unique
            match = re.match(r'^(.*?)(\d+)$', eid)
            if match:
                prefix, num = match.group(1), int(match.group(2))
                while f"{prefix}{num}" in used_ids:
                    num += 1
                elem["id"] = f"{prefix}{num}"
            else:
                elem["id"] = f"{eid}-dup"
        used_ids.add(elem["id"])
    return new_elements


def _collect_all_ids(layers: dict) -> set[str]:
    """Collect all element IDs from all layers."""
    ids = set()
    for layer_data in layers.values():
        if isinstance(layer_data, dict):
            for elements in layer_data.values():
                if isinstance(elements, list):
                    for elem in elements:
                        if isinstance(elem, dict) and "id" in elem:
                            ids.add(elem["id"])
    return ids


def merge_batch_into_project(
    project: ProjectModel,
    new_requirements: list[Requirement],
    new_layers: dict,
    new_links: list[Link],
    new_instructions: dict,
    source_file: str,
    layers_generated: list[str],
    model_name: str,
    cost: float,
) -> None:
    """Merge pipeline output into the project model. Mutates project in place."""
    # 1. Collect all existing element IDs
    existing_ids = _collect_all_ids(project.layers)

    # 2. Fix ID collisions in new layers
    for layer_key, layer_data in new_layers.items():
        if isinstance(layer_data, dict):
            for collection_key, elements in layer_data.items():
                if isinstance(elements, list):
                    fix_id_collisions(elements, existing_ids)
                    # Add new IDs to existing set
                    for e in elements:
                        if isinstance(e, dict) and "id" in e:
                            existing_ids.add(e["id"])

    # 3. Append new elements to existing layers
    for layer_key, layer_data in new_layers.items():
        if layer_key not in project.layers:
            project.layers[layer_key] = {}
        if isinstance(layer_data, dict):
            for collection_key, elements in layer_data.items():
                if collection_key not in project.layers[layer_key]:
                    project.layers[layer_key][collection_key] = []
                project.layers[layer_key][collection_key].extend(elements)

    # 4. Append requirements
    project.requirements.extend(new_requirements)

    # 5. Append links
    project.links.extend(new_links)

    # 6. Replace instructions (regenerated for full model)
    project.instructions = new_instructions

    # 7. Add batch record
    batch_num = len(project.batches) + 1
    project.batches.append(BatchRecord(
        id=f"batch-{batch_num:03d}",
        source_file=source_file,
        requirement_ids=[r.id for r in new_requirements],
        layers_generated=layers_generated,
        model=model_name,
        cost=cost,
    ))


def run_pipeline(
    requirements: list[Requirement],
    mode: str,
    selected_layers: list[str],
    model: str,
    provider: str,
    clarifications: dict[str, str] | None = None,
    emit: Callable[[dict], None] | None = None,
    cost_log_path: Path | None = None,
    existing_model: ProjectModel | None = None,
) -> MBSEModel:
    """Run the full 5-stage pipeline. Returns an MBSEModel.

    emit: callback for SSE events, called with {"stage": ..., "status": ..., "detail": ...}
    """
    tracker = CostTracker(model=model, cost_log_path=cost_log_path)
    client = create_client()
    _emit = emit or (lambda e: None)

    # Stage 1: Analyze
    _emit({"stage": "analyze", "status": "running", "detail": "Analyzing requirements..."})
    analysis = _run_with_retry(
        lambda: analyze_requirements(requirements, tracker, client=client),
        "analyze", _emit,
    )
    flagged_count = len(analysis.get("flagged", []))
    _emit({"stage": "analyze", "status": "complete", "detail": f"{flagged_count} issues found", "data": analysis})

    # Stage 2: Clarify (conditional)
    if clarifications:
        _emit({"stage": "clarify", "status": "running", "detail": "Applying clarifications..."})
        requirements = apply_clarifications(requirements, clarifications)
        _emit({"stage": "clarify", "status": "complete", "detail": f"{len(clarifications)} clarifications applied"})

    # Stage 3: Generate (layer by layer)
    layers = {}
    for i, layer_key in enumerate(selected_layers, 1):
        _emit({"stage": "generate", "status": "running", "detail": f"Generating {layer_key} ({i}/{len(selected_layers)})...", "cost": tracker.format_cost_line()})
        existing_elements = existing_model.layers.get(layer_key) if existing_model else None
        layers[layer_key] = _run_with_retry(
            lambda lk=layer_key, ee=existing_elements: generate_layer(mode, lk, requirements, tracker, client=client, existing_elements=ee),
            "generate", _emit,
        )
        _emit({"stage": "generate", "status": "layer_complete", "detail": f"{layer_key} complete", "cost": tracker.format_cost_line()})

    _emit({"stage": "generate", "status": "complete", "detail": f"All {len(selected_layers)} layers generated"})

    # Stage 4: Link
    _emit({"stage": "link", "status": "running", "detail": "Generating cross-element links...", "cost": tracker.format_cost_line()})
    existing_links_payload = [l.model_dump() for l in existing_model.links] if existing_model else None
    link_result = _run_with_retry(
        lambda: generate_links(mode, layers, requirements, tracker, client=client, existing_links=existing_links_payload),
        "link", _emit,
    )
    links = [Link(**l) for l in link_result.get("links", [])]
    _emit({"stage": "link", "status": "complete", "detail": f"{len(links)} links created", "cost": tracker.format_cost_line()})

    # Stage 5: Instruct — use the full accumulated model when an existing_model is provided (non-fatal)
    tool_name = "Capella 7.0" if mode == "capella" else "IBM Rhapsody 10.0"
    try:
        _emit({"stage": "instruct", "status": "running", "detail": "Generating recreation instructions...", "cost": tracker.format_cost_line()})
        if existing_model:
            # Build the full merged layer view: existing layers + newly generated layers
            full_layers = dict(existing_model.layers)
            full_layers.update(layers)
            instruct_model_data = {"layers": full_layers}
        else:
            instruct_model_data = {"layers": layers}
        instructions = _run_with_retry(
            lambda: generate_instructions(mode, instruct_model_data, tracker, client=client, emit=_emit),
            "instruct", _emit,
        )
        _emit({"stage": "instruct", "status": "complete", "detail": "Instructions generated", "cost": tracker.format_cost_line()})
    except Exception as exc:
        logger.warning(f"Instruct stage failed: {exc}. Continuing without instructions.")
        instructions = {"tool": tool_name, "steps": [], "error": str(exc)}
        _emit({"stage": "instruct", "status": "complete", "detail": "Instructions failed - you can retry from the Instructions tab", "cost": tracker.format_cost_line()})

    # Build final model
    model_obj = MBSEModel(
        meta=Meta(
            source_file="uploaded",
            mode=mode,
            selected_layers=selected_layers,
            llm_provider=provider,
            llm_model=model,
            cost=tracker.get_summary(),
        ),
        requirements=requirements,
        layers=layers,
        links=links,
        instructions=instructions,
    )

    # Log cost
    tracker.flush_log(run_type="pipeline_run", source_file=model_obj.meta.source_file, mode=mode, layers=selected_layers)

    _emit({"stage": "done", "status": "complete", "detail": tracker.format_cost_line()})
    return model_obj
