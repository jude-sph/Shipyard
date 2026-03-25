import logging

from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm
from src.decompose.loader import WorkbookData
from src.core.models.decompose import RequirementNode, RequirementTree, ValidationIssue, ValidationResult, SemanticReview
from src.decompose.prompts import format_judge_prompt

logger = logging.getLogger(__name__)


def validate_tree_structure(tree: RequirementTree, ref_data: WorkbookData, max_depth: int, max_breadth: int) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not tree.root:
        return issues
    valid_chapters = set(ref_data.gtr_chapters + ref_data.sds_chapters)
    valid_hierarchy = {h["id"] for h in ref_data.system_hierarchy}
    valid_allocations = {"GTR", "SDS", "GTR / SDS"}

    def _check_node(node: RequirementNode, path: str, parent_level: int | None) -> None:
        if "shall" not in node.technical_requirement.lower():
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"Technical requirement missing 'shall': \"{node.technical_requirement[:60]}...\""))
        if node.allocation not in valid_allocations:
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"Invalid allocation '{node.allocation}'"))
        if node.chapter_code != "Information Not Found" and node.chapter_code not in valid_chapters:
            issues.append(ValidationIssue(severity="warning", node_path=path, message=f"Chapter code '{node.chapter_code}' not in reference data"))
        if node.system_hierarchy_id != "Information Not Found" and node.system_hierarchy_id not in valid_hierarchy:
            issues.append(ValidationIssue(severity="warning", node_path=path, message=f"System hierarchy ID '{node.system_hierarchy_id}' not in reference data"))
        lengths = [len(node.verification_method), len(node.verification_event), len(node.test_case_descriptions)]
        non_zero = [l for l in lengths if l > 0]
        if non_zero and len(set(non_zero)) > 1:
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"V&V array length mismatch: methods={lengths[0]}, events={lengths[1]}, cases={lengths[2]}"))
        if parent_level is not None and node.level != parent_level + 1:
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"Child level {node.level} != parent level {parent_level} + 1"))
        if node.level > max_depth:
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"Node at depth {node.level} exceeds max_depth {max_depth}"))
        if len(node.children) > max_breadth:
            issues.append(ValidationIssue(severity="error", node_path=path, message=f"Node has {len(node.children)} children, exceeds max_breadth {max_breadth}"))
        if "[TBD]" in node.technical_requirement and not node.confidence_notes:
            issues.append(ValidationIssue(severity="warning", node_path=path, message="Technical requirement contains [TBD] but confidence_notes is empty"))
        for i, child in enumerate(node.children):
            child_path = f"{path} > L{child.level}.{i + 1}"
            _check_node(child, child_path, node.level)

    _check_node(tree.root, f"L{tree.root.level}", None)
    return issues


def run_semantic_judge(tree: RequirementTree, cost_tracker: CostTracker) -> SemanticReview:
    logger.info("Running semantic judge...")
    tree_json = tree.model_dump_json(indent=2, exclude={"validation", "cost"})
    prompt = format_judge_prompt(dig_id=tree.dig_id, dig_text=tree.dig_text, tree_json=tree_json)
    try:
        result = call_llm(prompt, cost_tracker, "judge", 0)
        issues = [ValidationIssue(severity=i.get("severity", "warning"), message=i.get("message", ""), node_path=i.get("node_path", "")) for i in result.get("issues", [])]
        review = SemanticReview(status=result.get("status", "flag"), issues=issues)
        logger.info(f"  Semantic judge: {review.status} ({len(issues)} issues)")
        return review
    except Exception as e:
        logger.error(f"  Semantic judge failed: {e}")
        return SemanticReview(status="error", issues=[ValidationIssue(severity="error", message=str(e), node_path="judge")])
