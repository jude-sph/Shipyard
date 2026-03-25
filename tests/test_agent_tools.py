"""Tests for consolidated agent tools (7 tools)."""
from src.core.models.core import ProjectModel, ProjectMeta, Requirement, Link
from src.model.agent.tools import apply_tool, TOOL_DEFINITIONS


def _make_project():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    p.requirements = [Requirement(id="REQ-1", text="Ship shall float", source_dig="9584")]
    p.layers = {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Coast Guard"}]}}
    p.links = [Link(id="LNK-001", source="REQ-1", target="OE-001", type="satisfies", description="test")]
    return p


def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 7


def test_query_project_summary():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "summary"})
    assert result["success"]
    assert "requirements" in result["data"]


def test_query_project_requirements():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "requirements"})
    assert result["success"]
    assert len(result["data"]) == 1


def test_query_project_elements():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "elements", "filter": {"layer": "operational_analysis"}})
    assert result["success"]


def test_query_project_coverage():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "coverage"})
    assert result["success"]
    assert result["data"]["total"] == 1
    assert result["data"]["covered"] == 1


def test_trace():
    p = _make_project()
    result = apply_tool(p, "trace", {"id": "REQ-1"})
    assert result["success"]
    assert len(result["data"]["links"]) == 1


def test_modify_model_add_element():
    p = _make_project()
    result = apply_tool(p, "modify_model", {
        "action": "add_element",
        "params": {"layer": "operational_analysis", "collection": "entities",
                   "element": {"id": "OE-002", "name": "Crew"}}
    })
    assert result["success"]
    assert len(p.layers["operational_analysis"]["entities"]) == 2


def test_modify_model_remove_element():
    p = _make_project()
    result = apply_tool(p, "modify_model", {
        "action": "remove_element",
        "params": {"element_id": "OE-001"}
    })
    assert result["success"]
    assert len(p.layers["operational_analysis"]["entities"]) == 0


def test_manage_queue_send():
    p = _make_project()
    result = apply_tool(p, "manage_queue", {"action": "send", "req_ids": ["REQ-1", "REQ-2"]})
    assert result["success"]
    assert "REQ-1" in p.modeling_queue


def test_manage_queue_dismiss():
    p = _make_project()
    p.modeling_queue = ["REQ-1", "REQ-2"]
    result = apply_tool(p, "manage_queue", {"action": "dismiss", "req_ids": ["REQ-1"]})
    assert result["success"]
    assert "REQ-1" in p.dismissed_from_modeling


def test_validate_all():
    p = _make_project()
    result = apply_tool(p, "validate", {"scope": "all"})
    assert result["success"]
    assert "model" in result["data"]
