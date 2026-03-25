import logging
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}


def _load_template(name: str) -> str:
    if name not in _cache:
        path = PROMPTS_DIR / name
        logger.debug(f"Loading prompt template: {path}")
        _cache[name] = path.read_text(encoding="utf-8")
    return _cache[name]


def format_decompose_prompt(
    dig_id: str,
    dig_text: str,
    target_level: int,
    target_level_name: str,
    parent_scope: str,
    child_scope: str,
    parent_chain: str,
    system_hierarchy: str,
    chapter_list: str,
    max_breadth: int,
) -> str:
    template = _load_template("decompose_level.txt")
    levels_example = _load_template("levels_example.txt")
    return template.format(
        dig_id=dig_id,
        dig_text=dig_text,
        target_level=target_level,
        target_level_name=target_level_name,
        parent_scope=parent_scope,
        child_scope=child_scope,
        parent_chain=parent_chain,
        system_hierarchy=system_hierarchy,
        chapter_list=chapter_list,
        levels_example=levels_example,
        max_breadth=max_breadth,
    )


def format_vv_prompt(
    level: int,
    level_name: str,
    technical_requirement: str,
    system_hierarchy_id: str,
    acceptance_phases: str,
    verification_methods: str,
    verification_events: str,
) -> str:
    template = _load_template("generate_vv.txt")
    return template.format(
        level=level,
        level_name=level_name,
        technical_requirement=technical_requirement,
        system_hierarchy_id=system_hierarchy_id,
        acceptance_phases=acceptance_phases,
        verification_methods=verification_methods,
        verification_events=verification_events,
    )


def format_judge_prompt(dig_id: str, dig_text: str, tree_json: str) -> str:
    template = _load_template("semantic_judge.txt")
    return template.format(
        dig_id=dig_id,
        dig_text=dig_text,
        tree_json=tree_json,
    )


def format_refine_prompt(
    dig_id: str,
    dig_text: str,
    tree_json: str,
    judge_feedback: str,
    system_hierarchy: str,
    chapter_list: str,
) -> str:
    template = _load_template("refine_tree.txt")
    return template.format(
        dig_id=dig_id,
        dig_text=dig_text,
        tree_json=tree_json,
        judge_feedback=judge_feedback,
        system_hierarchy=system_hierarchy,
        chapter_list=chapter_list,
    )
