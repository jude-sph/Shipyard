from src.core.config import (
    MODEL_PRICING, MODEL_CATALOGUE, LEVEL_NAMES,
    CAPELLA_LAYERS, RHAPSODY_DIAGRAMS,
    DEFAULT_MAX_DEPTH, DEFAULT_MAX_BREADTH,
    DECOMPOSE_MODEL, MBSE_MODEL, PROJECTS_DIR,
)

def test_model_pricing_has_entries():
    assert len(MODEL_PRICING) > 10

def test_model_catalogue_has_entries():
    assert len(MODEL_CATALOGUE) > 10
    for m in MODEL_CATALOGUE:
        assert "id" in m
        assert "name" in m

def test_level_names():
    assert LEVEL_NAMES[1] == "Whole Ship"
    assert LEVEL_NAMES[4] == "Equipment"

def test_capella_layers():
    assert "operational_analysis" in CAPELLA_LAYERS
    assert len(CAPELLA_LAYERS) == 5

def test_rhapsody_diagrams():
    assert "requirements_diagram" in RHAPSODY_DIAGRAMS
    assert len(RHAPSODY_DIAGRAMS) == 6

def test_defaults():
    assert DEFAULT_MAX_DEPTH == 4
    assert DEFAULT_MAX_BREADTH == 3

def test_per_workflow_models():
    assert isinstance(DECOMPOSE_MODEL, str)
    assert isinstance(MBSE_MODEL, str)
