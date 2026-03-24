from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

from src.core.models.core import Requirement


def parse_requirements_file(file_path: Path) -> list[Requirement]:
    """Parse XLSX or CSV file into a list of Requirement objects."""
    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return _parse_xlsx(file_path)
    elif suffix == ".csv":
        return _parse_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .xlsx, .xls, or .csv")


# Known aliases for each canonical column.  First match wins.
_ID_ALIASES = ["id", "node_id", "req_id", "requirement_id", "dng"]
_TEXT_ALIASES = ["text", "technical_requirement", "requirement_text", "requirement", "dig text", "dig_text", "description"]
_SOURCE_ALIASES = ["source_dig", "dig_id", "dig", "dng", "source"]


def _normalise_header(headers: list[str]) -> dict[str, int]:
    """Return a mapping of canonical column name -> zero-based column index."""
    normalised: dict[str, int] = {}
    for idx, header in enumerate(headers):
        if header is None:
            continue
        key = str(header).strip().lower()
        normalised[key] = idx
    return normalised


def _resolve_column(col_map: dict[str, int], aliases: list[str]) -> int | None:
    """Find the first matching column index from a list of aliases."""
    for alias in aliases:
        if alias in col_map:
            return col_map[alias]
    return None


def _row_to_requirement(
    values: list,
    id_col: int | None,
    text_col: int | None,
    source_col: int | None,
    row_number: int = 0,
) -> Requirement | None:
    """Convert a list of cell values into a Requirement, or None if the row is empty."""

    def get(idx: int | None) -> str:
        if idx is None:
            return ""
        raw = values[idx] if idx < len(values) else None
        return str(raw).strip() if raw is not None else ""

    req_id = get(id_col)
    text = get(text_col)
    source_dig = get(source_col)

    # Skip entirely empty rows
    if not req_id and not text:
        return None

    # If no explicit ID, generate one from source_dig or row number
    if not req_id and source_dig:
        req_id = f"REQ-{source_dig}"
    elif not req_id:
        req_id = f"REQ-{row_number:03d}"

    # If source_dig matches ID column (DNG used for both), keep it
    if not source_dig and req_id:
        source_dig = req_id

    return Requirement(id=req_id, text=text, source_dig=source_dig)


def _has_recognisable_headers(col_map: dict[str, int]) -> bool:
    """Check if the column map contains at least one known text column alias."""
    return any(alias in col_map for alias in _TEXT_ALIASES) or any(alias in col_map for alias in _ID_ALIASES)


def _parse_xlsx(file_path: Path) -> list[Requirement]:
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active

    requirements: list[Requirement] = []
    id_col: int | None = None
    text_col: int | None = None
    source_col: int | None = None
    header_found = False
    row_number = 1

    for row in ws.iter_rows(values_only=True):
        # Skip completely empty rows before the header
        if all(cell is None for cell in row):
            continue

        if not header_found:
            # Auto-detect header row using known aliases
            candidate = _normalise_header(list(row))
            if _has_recognisable_headers(candidate):
                id_col = _resolve_column(candidate, _ID_ALIASES)
                text_col = _resolve_column(candidate, _TEXT_ALIASES)
                source_col = _resolve_column(candidate, _SOURCE_ALIASES)
                header_found = True
            continue

        req = _row_to_requirement(list(row), id_col, text_col, source_col, row_number)
        if req is not None:
            requirements.append(req)
            row_number += 1

    wb.close()
    return requirements


def _parse_csv(file_path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []

    with file_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return requirements

        # Build normalised lookup and resolve via aliases
        col_map: dict[str, int] = {}
        original_names: list[str] = []
        for idx, h in enumerate(reader.fieldnames):
            if h is not None:
                col_map[h.strip().lower()] = idx
                original_names.append(h)

        id_idx = _resolve_column(col_map, _ID_ALIASES)
        text_idx = _resolve_column(col_map, _TEXT_ALIASES)
        source_idx = _resolve_column(col_map, _SOURCE_ALIASES)

        row_number = 1
        for row_dict in reader:
            values = [row_dict.get(h, "") for h in original_names]
            req = _row_to_requirement(values, id_idx, text_idx, source_idx, row_number)
            if req is not None:
                requirements.append(req)
                row_number += 1

    return requirements
