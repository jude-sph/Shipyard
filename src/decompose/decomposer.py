import logging

from src.core.config import LEVEL_NAMES
from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm, create_client
from src.decompose.loader import WorkbookData
from src.core.models.decompose import RequirementNode, RequirementTree
from src.decompose.prompts import format_decompose_prompt

logger = logging.getLogger(__name__)


def _format_ref_data(ref_data: WorkbookData) -> dict:
    hierarchy_str = "\n".join(h["id"] for h in ref_data.system_hierarchy)
    gtr_str = "\n".join(ref_data.gtr_chapters)
    sds_str = "\n".join(ref_data.sds_chapters)
    return {
        "system_hierarchy": hierarchy_str,
        "all_chapters": f"### GTR Chapters\n{gtr_str}\n\n### SDS Chapters\n{sds_str}",
    }


def _build_parent_chain(ancestors: list[RequirementNode]) -> str:
    if not ancestors:
        return "(This is the first level — no parent requirements yet.)"
    lines = []
    for node in ancestors:
        lines.append(f"Level {node.level} ({node.level_name}):\n  Requirement: {node.technical_requirement}\n  Allocation: {node.allocation}\n  System: {node.system_hierarchy_id}\n  Chapter: {node.chapter_code}")
    return "\n\n".join(lines)


def decompose_dig(dig_id: str, dig_text: str, ref_data: WorkbookData, max_depth: int, max_breadth: int, skip_vv: bool, cost_tracker: CostTracker, model: str | None = None) -> RequirementTree:
    logger.info(f'Decomposing DIG {dig_id}: "{dig_text[:80]}..."')
    client = create_client(model=model)
    refs = _format_ref_data(ref_data)
    tree = RequirementTree(dig_id=dig_id, dig_text=dig_text)
    root_children = _decompose_level(client=client, dig_id=dig_id, dig_text=dig_text, target_level=1, ancestors=[], refs=refs, max_breadth=max_breadth, cost_tracker=cost_tracker, model=model)
    if not root_children:
        logger.warning(f"DIG {dig_id}: No Level 1 requirements generated")
        return tree
    root = root_children[0]
    tree.root = root
    if max_depth > 1:
        _decompose_children(client=client, dig_id=dig_id, dig_text=dig_text, parent=root, ancestors=[root], refs=refs, max_depth=max_depth, max_breadth=max_breadth, cost_tracker=cost_tracker, model=model)
    return tree


def _decompose_level(client, dig_id, dig_text, target_level, ancestors, refs, max_breadth, cost_tracker, model=None):
    target_name = LEVEL_NAMES.get(target_level, f"Level {target_level}")
    parent_name = LEVEL_NAMES.get(target_level - 1, "DIG") if target_level > 1 else "DIG"
    prompt = format_decompose_prompt(dig_id=dig_id, dig_text=dig_text, target_level=target_level, target_level_name=target_name, parent_scope=parent_name, child_scope=target_name, parent_chain=_build_parent_chain(ancestors), system_hierarchy=refs["system_hierarchy"], chapter_list=refs["all_chapters"], max_breadth=max_breadth)
    result = call_llm(prompt, cost_tracker, "decompose", target_level, client=client, model=model)
    if result.get("decomposition_complete", False):
        logger.info(f"  L{target_level}: Decomposition complete (no further breakdown)")
        return []
    children = []
    for child_data in result.get("children", [])[:max_breadth]:
        try:
            node = RequirementNode(level=child_data.get("level", target_level), level_name=child_data.get("level_name", target_name), allocation=child_data.get("allocation", "Information Not Found"), chapter_code=child_data.get("chapter_code", "Information Not Found"), derived_name=child_data.get("derived_name", ""), technical_requirement=child_data.get("technical_requirement", ""), rationale=child_data.get("rationale", ""), system_hierarchy_id=child_data.get("system_hierarchy_id", "Information Not Found"), confidence_notes=child_data.get("confidence_notes"), decomposition_complete=child_data.get("decomposition_complete", False))
            children.append(node)
            logger.info(f'  L{target_level} ({node.allocation}): "{node.technical_requirement[:60]}..."')
        except Exception as e:
            logger.error(f"  L{target_level}: Failed to parse child: {e}")
    return children


def _decompose_children(client, dig_id, dig_text, parent, ancestors, refs, max_depth, max_breadth, cost_tracker, model=None):
    if parent.level >= max_depth:
        return
    if parent.decomposition_complete:
        return
    children = _decompose_level(client=client, dig_id=dig_id, dig_text=dig_text, target_level=parent.level + 1, ancestors=ancestors, refs=refs, max_breadth=max_breadth, cost_tracker=cost_tracker, model=model)
    parent.children = children
    for child in children:
        if not child.decomposition_complete and child.level < max_depth:
            _decompose_children(client=client, dig_id=dig_id, dig_text=dig_text, parent=child, ancestors=ancestors + [child], refs=refs, max_depth=max_depth, max_breadth=max_breadth, cost_tracker=cost_tracker, model=model)
