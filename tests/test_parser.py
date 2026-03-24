# tests/test_parser.py
from pathlib import Path
from src.core.parser import parse_requirements_file
import openpyxl

def test_parse_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["id", "text", "source_dig"])
    ws.append(["REQ-001", "The ship shall float", "9584"])
    ws.append(["REQ-002", "The hull shall be strong", "9584"])
    path = tmp_path / "test.xlsx"
    wb.save(path)
    reqs = parse_requirements_file(path)
    assert len(reqs) == 2
    assert reqs[0].id == "REQ-001"
    assert reqs[0].source_dig == "9584"

def test_parse_reqdecomp_columns(tmp_path):
    """Test that reqdecomp output columns are detected correctly."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["dig_id", "node_id", "technical_requirement"])
    ws.append(["9584", "9584-L1", "The vessel shall maintain ice-strengthened hull"])
    path = tmp_path / "reqdecomp_output.xlsx"
    wb.save(path)
    reqs = parse_requirements_file(path)
    assert len(reqs) == 1
    assert reqs[0].id == "9584-L1"
    assert "ice-strengthened" in reqs[0].text
