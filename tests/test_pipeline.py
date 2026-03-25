# tests/test_pipeline.py
from src.core.models.core import Requirement
from src.model.pipeline import estimate_cost


def test_estimate_cost():
    reqs = [
        Requirement(id="REQ-1", text="The ship shall float", source_dig="9584"),
        Requirement(id="REQ-2", text="The hull shall be strong", source_dig="9584"),
    ]
    est = estimate_cost(reqs, "capella", ["operational_analysis", "logical_architecture"], "claude-sonnet-4-6")
    assert "total_calls" in est
    assert est["num_requirements"] == 2
    assert est["num_layers"] == 2
    assert est["estimated_min_cost"] >= 0


def test_stages_import():
    from src.model.stages import (
        analyze_requirements, apply_clarifications, generate_layer,
        generate_links, generate_instructions
    )
    assert analyze_requirements is not None
    assert generate_layer is not None


def test_pipeline_import():
    from src.model.pipeline import run_pipeline, estimate_cost, merge_batch_into_project
    assert run_pipeline is not None
    assert merge_batch_into_project is not None
