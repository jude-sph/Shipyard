import logging

from src.core.cost_tracker import CostTracker
from src.core.llm_client import call_llm, create_client
from src.decompose.loader import WorkbookData
from src.core.models.decompose import RequirementNode, RequirementTree
from src.decompose.prompts import format_vv_prompt

logger = logging.getLogger(__name__)


def _format_refs(ref_data: WorkbookData) -> dict:
    return {
        "acceptance_phases": "\n\n".join(ref_data.acceptance_phases),
        "verification_methods": "\n".join(f"- {m['name']}: {m['description']}" for m in ref_data.verification_methods),
        "verification_events": "\n".join(f"- {e['name']}: {e['description']}" for e in ref_data.verification_events),
    }


def apply_vv_to_tree(tree: RequirementTree, ref_data: WorkbookData, cost_tracker: CostTracker, model: str | None = None) -> None:
    if not tree.root:
        return
    client = create_client(model=model)
    refs = _format_refs(ref_data)

    def _apply_vv(node: RequirementNode) -> None:
        logger.info(f'  Generating V&V for L{node.level}: "{node.technical_requirement[:50]}..."')
        prompt = format_vv_prompt(level=node.level, level_name=node.level_name, technical_requirement=node.technical_requirement, system_hierarchy_id=node.system_hierarchy_id, acceptance_phases=refs["acceptance_phases"], verification_methods=refs["verification_methods"], verification_events=refs["verification_events"])
        try:
            result = call_llm(prompt, cost_tracker, "vv", stage=f"level_{node.level}", client=client, model=model, level=node.level)
            node.acceptance_criteria = result.get("acceptance_criteria")
            node.verification_method = result.get("verification_method", [])
            node.verification_event = result.get("verification_event", [])
            node.test_case_descriptions = result.get("test_case_descriptions", [])
            logger.info(f"    V&V: {len(node.verification_method)} method(s)")
        except Exception as e:
            logger.error(f"    V&V failed for L{node.level}: {e}")
        for child in node.children:
            _apply_vv(child)

    _apply_vv(tree.root)
