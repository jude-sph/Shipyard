import logging

from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm
from src.decompose.loader import WorkbookData
from src.core.models.decompose import RequirementNode, RequirementTree, SemanticReview
from src.decompose.prompts import format_refine_prompt

logger = logging.getLogger(__name__)


def refine_tree(
    tree: RequirementTree,
    judge_review: SemanticReview,
    ref_data: WorkbookData,
    cost_tracker: CostTracker,
) -> RequirementTree:
    """Refine a requirement tree based on semantic judge feedback."""
    logger.info("Refining tree based on judge feedback...")

    feedback_lines = []
    for issue in judge_review.issues:
        feedback_lines.append(f"[{issue.severity}] {issue.node_path}: {issue.message}")
    judge_feedback = "\n".join(feedback_lines)

    hierarchy_str = "\n".join(h["id"] for h in ref_data.system_hierarchy)
    gtr_str = "\n".join(ref_data.gtr_chapters)
    sds_str = "\n".join(ref_data.sds_chapters)
    chapter_list = f"### GTR Chapters\n{gtr_str}\n\n### SDS Chapters\n{sds_str}"

    tree_json = tree.model_dump_json(indent=2, exclude={"validation", "cost"})
    prompt = format_refine_prompt(
        dig_id=tree.dig_id,
        dig_text=tree.dig_text,
        tree_json=tree_json,
        judge_feedback=judge_feedback,
        system_hierarchy=hierarchy_str,
        chapter_list=chapter_list,
    )

    try:
        result = call_llm(prompt, cost_tracker, "refine", 0, max_tokens=8192)

        refined_root = _parse_node(result.get("root", result))
        refined_tree = RequirementTree(
            dig_id=tree.dig_id,
            dig_text=tree.dig_text,
            root=refined_root,
        )

        old_count = tree.count_nodes()
        new_count = refined_tree.count_nodes()
        logger.info(f"  Refinement complete: {old_count} -> {new_count} nodes")
        return refined_tree

    except Exception as e:
        logger.error(f"Failed to refine tree: {e}")
        return tree


def _parse_node(data: dict) -> RequirementNode:
    """Recursively parse a node dict into a RequirementNode."""
    children = [_parse_node(c) for c in data.get("children", [])]
    return RequirementNode(
        level=data.get("level", 1),
        level_name=data.get("level_name", ""),
        allocation=data.get("allocation", "Information Not Found"),
        chapter_code=data.get("chapter_code", "Information Not Found"),
        derived_name=data.get("derived_name", ""),
        technical_requirement=data.get("technical_requirement", ""),
        rationale=data.get("rationale", ""),
        system_hierarchy_id=data.get("system_hierarchy_id", "Information Not Found"),
        acceptance_criteria=data.get("acceptance_criteria"),
        verification_method=data.get("verification_method", []),
        verification_event=data.get("verification_event", []),
        test_case_descriptions=data.get("test_case_descriptions", []),
        confidence_notes=data.get("confidence_notes"),
        decomposition_complete=data.get("decomposition_complete", False),
        children=children,
    )
