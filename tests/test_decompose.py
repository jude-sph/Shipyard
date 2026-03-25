from pathlib import Path


def test_loader_import():
    from src.decompose.loader import load_workbook_data, WorkbookData
    assert WorkbookData is not None


def test_decomposer_import():
    from src.decompose.decomposer import decompose_dig
    assert decompose_dig is not None


def test_verifier_import():
    from src.decompose.verifier import apply_vv_to_tree
    assert apply_vv_to_tree is not None


def test_validator_import():
    from src.decompose.validator import validate_tree_structure, run_semantic_judge
    assert validate_tree_structure is not None


def test_refiner_import():
    from src.decompose.refiner import refine_tree
    assert refine_tree is not None


def test_prompts_import():
    from src.decompose.prompts import format_decompose_prompt, format_vv_prompt
    assert format_decompose_prompt is not None


def test_loader_with_real_xlsx():
    from src.decompose.loader import load_workbook_data
    xlsx_path = Path("/Users/jude/Documents/projects/Requirements/GTR-SDS.xlsx")
    if not xlsx_path.exists():
        import pytest
        pytest.skip("GTR-SDS.xlsx not available")
    data = load_workbook_data(xlsx_path)
    assert len(data.digs) > 0
    assert len(data.system_hierarchy) > 0
