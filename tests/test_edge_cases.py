# tests/test_edge_cases.py
from src.core.models.core import ProjectModel, ProjectMeta, Requirement, Link


def test_detect_orphaned_links():
    from src.web.app import _detect_orphaned_links
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.requirements = [Requirement(id="REQ-VALID", text="Valid", source_dig="9584")]
    project.layers = {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Test"}]}}
    project.links = [
        Link(id="LNK-1", source="REQ-OLD", target="OE-GONE", type="satisfies", description="orphaned"),
        Link(id="LNK-2", source="REQ-VALID", target="OE-001", type="satisfies", description="valid"),
    ]
    orphaned = _detect_orphaned_links(project)
    assert len(orphaned) == 1
    assert orphaned[0].id == "LNK-1"


def test_no_orphaned_links():
    from src.web.app import _detect_orphaned_links
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.requirements = [Requirement(id="REQ-1", text="Test", source_dig="9584")]
    project.links = [
        Link(id="LNK-1", source="REQ-1", target="OE-001", type="satisfies", description="ok"),
    ]
    project.layers = {"oa": {"entities": [{"id": "OE-001", "name": "Test"}]}}
    orphaned = _detect_orphaned_links(project)
    assert len(orphaned) == 0
