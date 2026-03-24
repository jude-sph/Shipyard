from src.core.models.core import (
    ProjectModel, ProjectMeta, Requirement, Link, BatchRecord,
    CostEntry, CostSummary, SourceFile, DecompSettings, ModelSettings,
)
from src.core.models.decompose import (
    RequirementNode, RequirementTree, ValidationResult, ValidationIssue,
    SemanticReview,
)


def test_project_model_creation():
    project = ProjectModel(
        project=ProjectMeta(name="Test", mode="capella"),
    )
    assert project.project.name == "Test"
    assert project.auto_send is True
    assert project.decomposition_trees == {}
    assert project.requirements == []
    assert project.layers == {}
    assert project.links == []


def test_requirement_node():
    node = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Ships need to float",
        system_hierarchy_id="SH-001",
    )
    assert node.level == 1
    assert node.children == []
    assert node.decomposition_complete is False


def test_requirement_tree_counts():
    child = RequirementNode(
        level=2, level_name="Major System", allocation="GTR",
        chapter_code="1.1", derived_name="Hull",
        technical_requirement="The hull shall be strong",
        rationale="Structural integrity",
        system_hierarchy_id="SH-002",
    )
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Ship",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
        children=[child],
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test DIG", root=root)
    assert tree.count_nodes() == 2
    assert tree.max_depth() == 2


def test_cost_summary_computed():
    entry = CostEntry(call_type="decompose", stage="decompose", input_tokens=100, output_tokens=50, cost_usd=0.01)
    summary = CostSummary(breakdown=[entry])
    assert summary.total_input_tokens == 100
    assert summary.total_cost_usd == 0.01


def test_source_file():
    sf = SourceFile(filename="GTR-SDS.xlsx", file_type="reference", sha256="abc123")
    assert sf.file_type == "reference"


def test_batch_record():
    br = BatchRecord(
        id="batch-1", batch_type="decompose", source_file="GTR-SDS.xlsx",
        requirement_ids=["9584-L1"], layers_generated=[], model="sonnet",
        cost=0.05, requirement_snapshot=["9584-L1"],
    )
    assert br.batch_type == "decompose"


def test_capella_import():
    from src.core.models.capella import OperationalAnalysisLayer
    assert OperationalAnalysisLayer is not None


def test_rhapsody_import():
    from src.core.models.rhapsody import RequirementsDiagramLayer
    assert RequirementsDiagramLayer is not None
