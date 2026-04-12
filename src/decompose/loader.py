import logging
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

logger = logging.getLogger(__name__)


def _strip(val) -> str:
    """Convert cell value to stripped string. Handle None, floats, non-breaking spaces."""
    if val is None:
        return ""
    s = str(val).strip()
    s = s.replace("\xa0", " ")
    return s


@dataclass
class WorkbookData:
    digs: dict[str, dict] = field(default_factory=dict)
    system_hierarchy: list[dict] = field(default_factory=list)
    gtr_chapters: list[str] = field(default_factory=list)
    sds_chapters: list[str] = field(default_factory=list)
    acceptance_phases: list[str] = field(default_factory=list)
    verification_methods: list[dict] = field(default_factory=list)
    verification_events: list[dict] = field(default_factory=list)


def load_workbook_data(xlsx_path: Path) -> WorkbookData:
    logger.info(f"Loading workbook: {xlsx_path}")
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    data = WorkbookData()

    _load_digs(wb["Requirements Decomposition"], data)
    _load_system_hierarchy(wb["System Hierarchy"], data)
    _load_chapters(wb["GTR Chapters"], data.gtr_chapters, prefix="GTR-Ch")
    _load_chapters(wb["SDS Chapters"], data.sds_chapters, prefix="SDS-Ch")
    _load_acceptance_phases(wb, data)
    _load_verification_methods(wb["Verification Events"], data)
    _load_verification_events(wb["Verification Means"], data)

    wb.close()
    logger.info(
        f"Loaded: {len(data.digs)} DIGs, {len(data.system_hierarchy)} hierarchy entries, "
        f"{len(data.gtr_chapters)} GTR chapters, {len(data.sds_chapters)} SDS chapters, "
        f"{len(data.acceptance_phases)} phases, {len(data.verification_methods)} methods, "
        f"{len(data.verification_events)} events"
    )
    return data


def _load_digs(ws, data: WorkbookData) -> None:
    seen_ids = set()
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row[0] is None:
            continue
        raw_id = _strip(row[0])
        if not raw_id:
            continue
        try:
            dig_id = str(int(float(raw_id)))
        except (ValueError, TypeError):
            logger.warning(f"Row {i}: cannot parse DIG ID '{raw_id}' as a number, skipping")
            continue
        dig_text = _strip(row[1])
        if not dig_text:
            continue
        if dig_id in seen_ids:
            logger.warning(f"Duplicate DIG ID {dig_id} at row {i}, skipping")
            continue
        seen_ids.add(dig_id)
        data.digs[dig_id] = {"dig_id": dig_id, "dig_text": dig_text}
    logger.info(f"  Loaded {len(data.digs)} unique DIGs")


def _load_system_hierarchy(ws, data: WorkbookData) -> None:
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        val = _strip(row[0])
        if val:
            data.system_hierarchy.append({"id": val})


def _load_chapters(ws, chapter_list: list[str], prefix: str) -> None:
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        val = _strip(row[0])
        if val and val.startswith(prefix):
            chapter_list.append(val)


def _load_acceptance_phases(wb, data: WorkbookData) -> None:
    ws = wb["Acceptance Phases"]
    for row in ws.iter_rows(min_row=1, values_only=True):
        if not row:
            continue
        val = _strip(row[0])
        if val and "Acceptance Phase" in val:
            data.acceptance_phases.append(val)


def _load_verification_methods(ws, data: WorkbookData) -> None:
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        name = _strip(row[0])
        desc = _strip(row[1]) if len(row) > 1 else ""
        if name:
            data.verification_methods.append({"name": name, "description": desc})


def _load_verification_events(ws, data: WorkbookData) -> None:
    current_name = ""
    current_desc = ""
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        name = _strip(row[0])
        desc = _strip(row[1]) if len(row) > 1 else ""
        if name:
            if current_name:
                data.verification_events.append({"name": current_name, "description": current_desc})
            current_name = name
            current_desc = desc
        elif current_name and desc:
            current_desc += " " + desc
    if current_name:
        data.verification_events.append({"name": current_name, "description": current_desc})
