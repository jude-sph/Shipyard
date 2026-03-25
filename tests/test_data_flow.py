# tests/test_data_flow.py
from src.core.models.core import ProjectModel, ProjectMeta, Requirement
from src.core.models.decompose import RequirementNode, RequirementTree


def test_flatten_tree_to_requirements():
    from src.web.app import _flatten_tree_to_requirements
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
        children=[
            RequirementNode(
                level=2, level_name="Major System", allocation="GTR",
                chapter_code="1.1", derived_name="Hull",
                technical_requirement="The hull shall be strong",
                rationale="Structural integrity",
                system_hierarchy_id="SH-002",
            )
        ]
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test", root=root)
    reqs = _flatten_tree_to_requirements(tree)
    assert len(reqs) >= 2
    assert all(isinstance(r, Requirement) for r in reqs)
    assert all(r.source_dig == "9584" for r in reqs)


def test_sync_modeling_queue_auto_send_on():
    from src.web.app import _sync_modeling_queue
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.auto_send = True
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test", root=root)
    project.decomposition_trees["9584"] = tree.model_dump()
    _sync_modeling_queue(project)
    assert len(project.modeling_queue) > 0
    assert len(project.requirements) > 0


def test_sync_modeling_queue_auto_send_off():
    from src.web.app import _sync_modeling_queue
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.auto_send = False
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test", root=root)
    project.decomposition_trees["9584"] = tree.model_dump()
    _sync_modeling_queue(project)
    assert len(project.modeling_queue) == 0


def test_dismiss_effective_queue():
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.modeling_queue = ["REQ-1", "REQ-2", "REQ-3"]
    project.dismissed_from_modeling = ["REQ-2"]
    effective = [r for r in project.modeling_queue if r not in project.dismissed_from_modeling]
    assert effective == ["REQ-1", "REQ-3"]
