# Shipyard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Combine reqdecomp and MBSE Generator into a unified web app (Shipyard) with shared project state, seamless data flow, and a project-wide AI agent.

**Architecture:** Unified pipeline architecture with 4 layers: Web (FastAPI + vanilla JS), Decompose module (from reqdecomp), Model module (from MBSE), and Core (shared infrastructure). Both pipelines operate on a single `project.json`. The agent uses a tool-loop architecture with 7 consolidated tools.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic 2, openpyxl, anthropic SDK, openai SDK, vanilla JavaScript, Server-Sent Events.

**Spec:** `docs/superpowers/specs/2026-03-24-shipyard-integration-design.md`

**Source repos:**
- reqdecomp: `/Users/jude/Documents/projects/Requirements`
- MBSE: `/Users/jude/Documents/projects/MBSE`

---

## Phase 1: Project Scaffolding & Core Infrastructure

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/core/models/__init__.py`
- Create: `src/decompose/__init__.py`
- Create: `src/model/__init__.py`
- Create: `src/model/stages/__init__.py`
- Create: `src/model/agent/__init__.py`
- Create: `src/web/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "shipyard"
version = "1.0.0"
description = "Unified shipbuilding requirements decomposition and MBSE modeling platform"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "pydantic>=2.0.0",
    "openpyxl>=3.1.0",
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    "httpx>=0.27.0",
    "jinja2>=3.1.0",
    "python-dotenv>=1.0.0",
    "python-multipart>=0.0.5",
    "tqdm>=4.60.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[project.scripts]
shipyard = "src.main:main"

[tool.setuptools.packages.find]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create directory structure and init files**

Create all `__init__.py` files (empty). Create `.env.example`:

```
PROVIDER=anthropic
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
LOCAL_LLM_URL=http://localhost:11434/v1
DECOMPOSE_MODEL=claude-sonnet-4-6
MBSE_MODEL=claude-sonnet-4-6
DEFAULT_MODE=capella
```

- [ ] **Step 3: Update .gitignore**

Append to existing `.gitignore`:

```
__pycache__/
*.egg-info/
.env
output/
projects/
*.pyc
dist/
build/
```

- [ ] **Step 4: Install in dev mode and verify**

Run: `cd /Users/jude/Documents/projects/Shipyard && pip install -e ".[dev]"`
Expected: Successful installation

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ tests/ .env.example .gitignore
git commit -m "feat: project scaffolding with package structure"
```

---

### Task 2: Core config module

**Files:**
- Create: `src/core/config.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/config.py` (primary, has CAPELLA_LAYERS/RHAPSODY_DIAGRAMS)
- Reference: `/Users/jude/Documents/projects/Requirements/src/config.py` (has LEVEL_NAMES, DEFAULT_MAX_DEPTH/BREADTH)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write test for config loading**

```python
# tests/test_config.py
import os
from src.core.config import (
    MODEL_PRICING, MODEL_CATALOGUE, LEVEL_NAMES,
    CAPELLA_LAYERS, RHAPSODY_DIAGRAMS,
    DEFAULT_MAX_DEPTH, DEFAULT_MAX_BREADTH,
)

def test_model_pricing_has_entries():
    assert len(MODEL_PRICING) > 10

def test_model_catalogue_has_entries():
    assert len(MODEL_CATALOGUE) > 10
    for m in MODEL_CATALOGUE:
        assert "id" in m
        assert "name" in m

def test_level_names():
    assert LEVEL_NAMES[1] == "Whole Ship"
    assert LEVEL_NAMES[4] == "Equipment"

def test_capella_layers():
    assert "operational_analysis" in CAPELLA_LAYERS
    assert len(CAPELLA_LAYERS) == 5

def test_rhapsody_diagrams():
    assert "requirements_diagram" in RHAPSODY_DIAGRAMS
    assert len(RHAPSODY_DIAGRAMS) == 6

def test_defaults():
    assert DEFAULT_MAX_DEPTH == 4
    assert DEFAULT_MAX_BREADTH == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Build config.py**

Merge both source configs. Copy MBSE's `config.py` as the base (it has CAPELLA_LAYERS, RHAPSODY_DIAGRAMS, MODEL_PRICING, MODEL_CATALOGUE, provider/key loading). Add from reqdecomp: `LEVEL_NAMES`, `DEFAULT_MAX_DEPTH`, `DEFAULT_MAX_BREADTH`. Add new vars: `DECOMPOSE_MODEL`, `MBSE_MODEL`, `PROJECTS_DIR`.

Key changes from MBSE source:
- `PACKAGE_ROOT = Path(__file__).resolve().parent.parent` (points to `src/`)
- `PROMPTS_DIR` removed (each module has its own prompts dir)
- Add `DECOMPOSE_MODEL = os.getenv("DECOMPOSE_MODEL", "claude-sonnet-4-6")`
- Add `MBSE_MODEL = os.getenv("MBSE_MODEL", "claude-sonnet-4-6")`
- Add `PROJECTS_DIR = CWD / "projects"`
- Add `LEVEL_NAMES = {1: "Whole Ship", 2: "Major System", 3: "Subsystem", 4: "Equipment"}`
- Add `DEFAULT_MAX_DEPTH = 4`, `DEFAULT_MAX_BREADTH = 3`
- Merge MODEL_CATALOGUE from both (MBSE has 13 entries, reqdecomp has 15 — union by ID, MBSE takes precedence for duplicates)
- Merge MODEL_PRICING similarly

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/test_config.py
git commit -m "feat: core config merging both app configurations"
```

---

### Task 3: Core data models

**Files:**
- Create: `src/core/models/core.py`
- Create: `src/core/models/decompose.py`
- Copy: `src/core/models/capella.py` from MBSE `src/models/capella.py`
- Copy: `src/core/models/rhapsody.py` from MBSE `src/models/rhapsody.py`
- Update: `src/core/models/__init__.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write test for core models**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL

- [ ] **Step 3: Create core.py models**

Build `src/core/models/core.py`. Start from MBSE's `src/models/core.py` (has CostEntry, CostSummary, Requirement, Link, Meta, MBSEModel, ProjectMeta, BatchRecord, ProjectModel). Modify:

- Add `SourceFile` model: `filename: str`, `upload_time: datetime = Field(default_factory=utcnow)`, `file_type: Literal["reference", "requirements"]`, `sha256: str`
- Add `DecompSettings` model: `max_depth: int = 4`, `max_breadth: int = 3`, `skip_vv: bool = False`, `skip_judge: bool = False`, `model: str = "claude-sonnet-4-6"`
- Add `ModelSettings` model: `selected_layers: list[str] = []`, `model: str = "claude-sonnet-4-6"`
- Expand `BatchRecord` with: `batch_type: Literal["decompose", "model", "import"]`, `requirement_snapshot: list[str] = []`
- Expand `ProjectModel` with: `sources: list[SourceFile] = []`, `reference_data: dict | None = None`, `decomposition_trees: dict[str, Any] = {}`, `decomposition_settings: DecompSettings = Field(default_factory=DecompSettings)`, `auto_send: bool = True`, `modeling_queue: list[str] = []`, `dismissed_from_modeling: list[str] = []`, `model_settings: ModelSettings = Field(default_factory=ModelSettings)`, `cost_summary: CostSummary | None = None`
- Keep existing ProjectModel fields: `requirements`, `layers`, `links`, `instructions`, `batches`, `chat_history`
- Add `CostEntry.stage` field (MBSE has it, reqdecomp uses `level` — keep both: `stage: str = ""`, `level: int = 0`)

- [ ] **Step 4: Create decompose.py models**

Copy from reqdecomp's `src/models.py`: `RequirementNode`, `RequirementTree`, `ValidationResult`, `ValidationIssue`, `SemanticReview`. These models are self-contained. No import changes needed except the package path.

- [ ] **Step 5: Copy Capella and Rhapsody models**

Copy verbatim from MBSE:
- `src/models/capella.py` → `src/core/models/capella.py`
- `src/models/rhapsody.py` → `src/core/models/rhapsody.py`

No changes needed — these are standalone Pydantic models.

- [ ] **Step 6: Update models __init__.py**

```python
# src/core/models/__init__.py
from src.core.models.core import *
from src.core.models.decompose import *
from src.core.models.capella import *
from src.core.models.rhapsody import *
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/core/models/ tests/test_models.py
git commit -m "feat: core data models merging reqdecomp and MBSE schemas"
```

---

### Task 4: Core LLM client

**Files:**
- Create: `src/core/llm_client.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/llm_client.py` (primary — has local provider + tool calling)
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write test for client creation and JSON extraction**

```python
# tests/test_llm_client.py
from src.core.llm_client import _extract_json

def test_extract_json_from_code_block():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == '{"key": "value"}'

def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == '{"key": "value"}'

def test_extract_json_with_trailing_comma():
    text = '{"items": ["a", "b",]}'
    result = _extract_json(text)
    assert '"a"' in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL

- [ ] **Step 3: Copy and adapt MBSE's llm_client.py**

Copy MBSE's `src/llm_client.py` to `src/core/llm_client.py`. Changes:
- Update imports: `from src.core.config import ...` (instead of `from src.config`)
- Keep all three providers: Anthropic, OpenRouter, Local
- Keep `call_llm()` signature but change `stage` parameter to be optional (reqdecomp passes `level`, MBSE passes `stage`): `call_llm(prompt, cost_tracker, call_type, stage="", level=0, max_tokens=4096, client=None)`
- Keep `call_llm_with_tools()` for agent
- Keep `_extract_json()`, `create_client()`

- [ ] **Step 4: Run test**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/llm_client.py tests/test_llm_client.py
git commit -m "feat: unified LLM client with Anthropic, OpenRouter, and local support"
```

---

### Task 5: Core cost tracker

**Files:**
- Create: `src/core/cost_tracker.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/cost_tracker.py` (primary — has JSONL logging)
- Test: `tests/test_cost_tracker.py`

- [ ] **Step 1: Write test**

```python
# tests/test_cost_tracker.py
from src.core.cost_tracker import CostTracker

def test_record_and_summary():
    tracker = CostTracker(model="test-model")
    tracker.record("decompose", "decompose", 100, 50, 0.01)
    tracker.record("generate", "model_oa", 200, 100, 0.03)
    summary = tracker.get_summary()
    assert summary.total_input_tokens == 300
    assert summary.total_output_tokens == 150
    assert summary.total_cost_usd == 0.04
    assert summary.api_calls == 2

def test_reset():
    tracker = CostTracker(model="test-model")
    tracker.record("decompose", "test", 100, 50, 0.01)
    tracker.reset()
    assert tracker.get_summary().api_calls == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: FAIL

- [ ] **Step 3: Copy and adapt MBSE's cost_tracker.py**

Copy MBSE's `src/cost_tracker.py` to `src/core/cost_tracker.py`. Changes:
- Update imports: `from src.core.models.core import CostEntry, CostSummary`
- Update `from src.core.config import MODEL_PRICING`
- Ensure `record()` accepts both `stage` (for model) and `level` (for decompose) params: `record(self, call_type, stage, input_tokens, output_tokens, actual_cost=None, level=0)`

- [ ] **Step 4: Run test**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/cost_tracker.py tests/test_cost_tracker.py
git commit -m "feat: cost tracker with JSONL logging and per-pipeline tracking"
```

---

### Task 6: Core project manager

**Files:**
- Create: `src/core/project.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/project.py` (has save/load/backup/undo/redo)
- Test: `tests/test_project.py`

- [ ] **Step 1: Write test**

```python
# tests/test_project.py
import json
from pathlib import Path
from src.core.project import new_project, save_project, load_project, list_projects

def test_new_project(tmp_path):
    project = new_project("capella", "Test Ship", projects_dir=tmp_path)
    assert project.project.name == "Test Ship"
    assert project.project.mode == "capella"
    assert project.auto_send is True

def test_save_and_load(tmp_path):
    project = new_project("capella", "Test Ship", projects_dir=tmp_path)
    path = save_project(project, projects_dir=tmp_path)
    assert path.exists()
    loaded = load_project(project.project.name, projects_dir=tmp_path)
    assert loaded.project.name == "Test Ship"

def test_list_projects(tmp_path):
    new_project("capella", "Ship A", projects_dir=tmp_path)
    save_project(new_project("capella", "Ship A", projects_dir=tmp_path), projects_dir=tmp_path)
    new_project("rhapsody", "Ship B", projects_dir=tmp_path)
    save_project(new_project("rhapsody", "Ship B", projects_dir=tmp_path), projects_dir=tmp_path)
    projects = list_projects(projects_dir=tmp_path)
    assert len(projects) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project.py -v`
Expected: FAIL

- [ ] **Step 3: Build project manager**

Start from MBSE's `src/project.py`. Major changes:
- Add `projects_dir` parameter (default: `config.PROJECTS_DIR`) to all functions
- Projects stored as `projects/<slug>/project.json` where slug is sanitized project name
- `new_project(mode, name, projects_dir)` → creates `ProjectModel` with new schema
- `save_project(project, projects_dir)` → writes to `projects/<slug>/project.json`, creates dirs
- `load_project(name_or_id, projects_dir)` → loads from project dir
- `list_projects(projects_dir)` → scans `projects/` dir, returns list of `{name, mode, modified, path}`
- `delete_project(name_or_id, projects_dir)` → removes project dir
- Keep undo/redo logic from MBSE (snapshot stack, max 20)
- Add `backup_project()` from MBSE
- Handle old `system_analysis` → `system_needs_analysis` migration from MBSE

- [ ] **Step 4: Run test**

Run: `pytest tests/test_project.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/project.py tests/test_project.py
git commit -m "feat: project manager with server-side storage and undo/redo"
```

---

### Task 7: Core parser and exporter

**Files:**
- Create: `src/core/parser.py`
- Create: `src/core/exporter.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/parser.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/exporter.py` (MBSE model export)
- Reference: `/Users/jude/Documents/projects/Requirements/src/exporter.py` (decomp tree export)
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write test for parser**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL

- [ ] **Step 3: Copy parser from MBSE**

Copy `src/parser.py` to `src/core/parser.py`. Update imports to `from src.core.models.core import Requirement`. No other changes needed — the flexible column detection already handles reqdecomp output.

- [ ] **Step 4: Build unified exporter**

Create `src/core/exporter.py` combining both:
- From MBSE: `export_json()`, `export_xlsx()`, `export_text()` for model export
- From reqdecomp: `tree_to_rows()`, `export_trees_to_xlsx()` for decomposition export
- Add: `export_full_project(project, output_path)` for full project JSON export

Update all imports to use `src.core.models`.

- [ ] **Step 5: Run test**

Run: `pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/core/parser.py src/core/exporter.py tests/test_parser.py
git commit -m "feat: requirement parser and unified exporter for both pipelines"
```

---

### Task 8: Core __init__ exports

**Files:**
- Update: `src/core/__init__.py`

- [ ] **Step 1: Create core package exports**

```python
# src/core/__init__.py
from src.core.config import *
from src.core.llm_client import call_llm, call_llm_with_tools, create_client
from src.core.cost_tracker import CostTracker
from src.core.project import new_project, save_project, load_project, list_projects
```

- [ ] **Step 2: Verify all core imports work**

Run: `python -c "from src.core import CostTracker, call_llm, new_project; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add src/core/__init__.py
git commit -m "feat: core package exports"
```

---

## Phase 2: Decompose Module

### Task 9: Decompose prompts

**Files:**
- Create: `src/decompose/prompts/decompose_level.txt`
- Create: `src/decompose/prompts/levels_example.txt`
- Create: `src/decompose/prompts/generate_vv.txt`
- Create: `src/decompose/prompts/semantic_judge.txt`
- Create: `src/decompose/prompts/refine_tree.txt`
- Create: `src/decompose/prompts.py`

- [ ] **Step 1: Copy prompt templates from reqdecomp**

Copy all 5 `.txt` files from `/Users/jude/Documents/projects/Requirements/prompts/` to `src/decompose/prompts/`. No modifications needed.

- [ ] **Step 2: Create prompts.py loader**

Copy `/Users/jude/Documents/projects/Requirements/src/prompts.py` to `src/decompose/prompts.py`. Change:
- `PROMPTS_DIR = Path(__file__).parent / "prompts"` (local to decompose module)
- No other changes — the format functions are self-contained

- [ ] **Step 3: Verify prompt loading**

Run: `python -c "from src.decompose.prompts import format_decompose_prompt; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add src/decompose/prompts/ src/decompose/prompts.py
git commit -m "feat: decompose prompt templates and loader"
```

---

### Task 10: Decompose pipeline modules

**Files:**
- Create: `src/decompose/loader.py`
- Create: `src/decompose/decomposer.py`
- Create: `src/decompose/verifier.py`
- Create: `src/decompose/validator.py`
- Create: `src/decompose/refiner.py`
- Test: `tests/test_decompose.py`

- [ ] **Step 1: Write test for loader**

```python
# tests/test_decompose.py
from pathlib import Path
from src.decompose.loader import load_workbook_data

def test_load_workbook_data_structure():
    # This test requires the actual GTR-SDS.xlsx
    # Skip if not available
    xlsx_path = Path("/Users/jude/Documents/projects/Requirements/GTR-SDS.xlsx")
    if not xlsx_path.exists():
        import pytest
        pytest.skip("GTR-SDS.xlsx not available")
    data = load_workbook_data(xlsx_path)
    assert len(data.digs) > 0
    assert len(data.system_hierarchy) > 0
    assert len(data.gtr_chapters) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_decompose.py -v`
Expected: FAIL

- [ ] **Step 3: Copy and adapt all decompose modules**

Copy each file from reqdecomp `src/` to `src/decompose/`, updating imports:

**loader.py:** Copy from `Requirements/src/loader.py`. No import changes needed — it only uses stdlib + openpyxl.

**decomposer.py:** Copy from `Requirements/src/decomposer.py`. Update:
- `from src.core.config import LEVEL_NAMES`
- `from src.core.cost_tracker import CostTracker`
- `from src.core.llm_client import call_llm, create_client`
- `from src.decompose.loader import WorkbookData`
- `from src.core.models.decompose import RequirementNode, RequirementTree`
- `from src.decompose.prompts import format_decompose_prompt`

**verifier.py:** Copy from `Requirements/src/verifier.py`. Similar import updates.

**validator.py:** Copy from `Requirements/src/validator.py`. Similar import updates.

**refiner.py:** Copy from `Requirements/src/refiner.py`. Similar import updates.

- [ ] **Step 4: Run test**

Run: `pytest tests/test_decompose.py -v`
Expected: PASS (or skip if no XLSX)

- [ ] **Step 5: Verify module imports**

Run: `python -c "from src.decompose.decomposer import decompose_dig; print('OK')"`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add src/decompose/ tests/test_decompose.py
git commit -m "feat: decompose module with loader, decomposer, verifier, validator, refiner"
```

---

## Phase 3: Model Module

### Task 11: Model prompts

**Files:**
- Create: `src/model/prompts/` (17 prompt files)

- [ ] **Step 1: Copy all prompt templates from MBSE**

Copy all 17 `.txt` files from `/Users/jude/Documents/projects/MBSE/prompts/` to `src/model/prompts/`. No modifications needed.

- [ ] **Step 2: Verify files copied**

Run: `ls src/model/prompts/*.txt | wc -l`
Expected: 17

- [ ] **Step 3: Commit**

```bash
git add src/model/prompts/
git commit -m "feat: model prompt templates for Capella and Rhapsody"
```

---

### Task 12: Model pipeline and stages

**Files:**
- Create: `src/model/pipeline.py`
- Create: `src/model/stages/analyze.py`
- Create: `src/model/stages/clarify.py`
- Create: `src/model/stages/generate.py`
- Create: `src/model/stages/link.py`
- Create: `src/model/stages/instruct.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write test for cost estimation**

```python
# tests/test_pipeline.py
from src.core.models.core import Requirement
from src.model.pipeline import estimate_cost

def test_estimate_cost():
    reqs = [
        Requirement(id="REQ-1", text="The ship shall float", source_dig="9584"),
        Requirement(id="REQ-2", text="The hull shall be strong", source_dig="9584"),
    ]
    est = estimate_cost(reqs, "capella", ["operational_analysis", "logical_architecture"], "claude-sonnet-4-6")
    assert "total_calls" in est
    assert est["num_requirements"] == 2
    assert est["num_layers"] == 2
    assert est["estimated_min_cost"] >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Copy and adapt all stage modules**

Copy each from MBSE `src/stages/` to `src/model/stages/`, updating imports:

For all stage files, change:
- `from src.config import ...` → `from src.core.config import ...`
- `from src.cost_tracker import ...` → `from src.core.cost_tracker import ...`
- `from src.llm_client import ...` → `from src.core.llm_client import ...`
- `from src.models import ...` → `from src.core.models import ...`
- Prompt loading: change `PROMPTS_DIR` to `Path(__file__).resolve().parent.parent / "prompts"` (points to `src/model/prompts/`)

Update `src/model/stages/__init__.py`:
```python
from src.model.stages.analyze import analyze_requirements
from src.model.stages.clarify import apply_clarifications
from src.model.stages.generate import generate_layer
from src.model.stages.link import generate_links
from src.model.stages.instruct import generate_instructions
```

- [ ] **Step 4: Copy and adapt pipeline.py**

Copy MBSE `src/pipeline.py` to `src/model/pipeline.py`. Update imports:
- Stage imports: `from src.model.stages import ...`
- Models: `from src.core.models import ...`
- Config: `from src.core.config import ...`
- LLM: `from src.core.llm_client import ...`
- Cost: `from src.core.cost_tracker import CostTracker`

Keep `estimate_cost()`, `fix_id_collisions()`, `merge_batch_into_project()`, `run_pipeline()`.

- [ ] **Step 5: Run test**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/model/pipeline.py src/model/stages/ tests/test_pipeline.py
git commit -m "feat: model pipeline with 5-stage orchestration"
```

---

### Task 13: Agent tools (7 consolidated)

**Files:**
- Create: `src/model/agent/tools.py`
- Test: `tests/test_agent_tools.py`

- [ ] **Step 1: Write test for agent tools**

```python
# tests/test_agent_tools.py
from src.core.models.core import ProjectModel, ProjectMeta, Requirement, Link
from src.model.agent.tools import apply_tool, TOOL_DEFINITIONS

def _make_project():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    p.requirements = [Requirement(id="REQ-1", text="Ship shall float", source_dig="9584")]
    p.layers = {"operational_analysis": {"entities": [{"id": "OE-001", "name": "Coast Guard"}]}}
    p.links = [Link(id="LNK-001", source="REQ-1", target="OE-001", type="satisfies", description="test")]
    return p

def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 7

def test_query_project_summary():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "summary"})
    assert result["success"]
    assert "requirements" in result["data"]

def test_query_project_requirements():
    p = _make_project()
    result = apply_tool(p, "query_project", {"scope": "requirements"})
    assert result["success"]
    assert len(result["data"]) == 1

def test_modify_model_add_element():
    p = _make_project()
    result = apply_tool(p, "modify_model", {
        "action": "add_element",
        "params": {"layer": "operational_analysis", "collection": "entities",
                   "element": {"id": "OE-002", "name": "Crew"}}
    })
    assert result["success"]
    assert len(p.layers["operational_analysis"]["entities"]) == 2

def test_validate_all():
    p = _make_project()
    result = apply_tool(p, "validate", {"scope": "all"})
    assert result["success"]
    assert "model" in result["data"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_tools.py -v`
Expected: FAIL

- [ ] **Step 3: Build consolidated tools**

Create `src/model/agent/tools.py` with 7 tools. Start from MBSE's `src/agent/tools.py` (has 13 tools + `apply_tool` dispatcher). Consolidate:

**`query_project(scope, filter?)`** — Combines: `list_elements`, `list_links`, `get_element_details`, `get_uncovered_requirements`, `get_coverage_summary`. Add new scopes: "requirements" (query decomposition trees), "batches", "reference", "summary", "validation".

**`trace(id)`** — New tool. Given any ID, walks: requirement → links → elements, or element → links → requirements. Returns full chain.

**`modify_decomposition(action, params)`** — New tool. Actions: "edit" (modify requirement fields in tree), "add" (add child node), "remove" (remove node), "re_decompose" (triggers re-decompose of a DIG).

**`modify_model(action, params)`** — Combines: `add_element`, `modify_element`, `remove_element`, `add_link`, `modify_link`, `remove_link`, `regenerate_layer`. Each action maps to the existing handler functions from MBSE's tools.py.

**`manage_queue(action, req_ids)`** — New tool. Actions: "send" (add to modeling_queue), "dismiss" (add to dismissed_from_modeling), "restore" (remove from dismissed).

**`batch_modify(operations)`** — Wraps multiple modify_decomposition/modify_model calls.

**`validate(scope?)`** — New tool. Scope "decomposition" runs reqdecomp's structural validator. Scope "model" checks coverage and link integrity. Scope "all" runs both.

Define `TOOL_DEFINITIONS` as OpenAI function-calling format (7 entries).

- [ ] **Step 4: Run test**

Run: `pytest tests/test_agent_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/model/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: 7 consolidated agent tools with query, modify, trace, validate"
```

---

### Task 14: Agent chat with tool loop

**Files:**
- Create: `src/model/agent/chat.py`
- Test: `tests/test_agent_chat.py`

- [ ] **Step 1: Write test for chat context building**

```python
# tests/test_agent_chat.py
from src.core.models.core import ProjectModel, ProjectMeta, Requirement
from src.model.agent.chat import _build_system_prompt, _build_summary

def test_build_summary():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    p.requirements = [Requirement(id="REQ-1", text="Ship shall float", source_dig="9584")]
    summary = _build_summary(p)
    assert "1 requirements" in summary or "1 requirement" in summary

def test_build_system_prompt():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    prompt = _build_system_prompt(p, mode="decompose")
    assert "Shipyard" in prompt
    assert "decompose" in prompt.lower() or "decomposition" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_chat.py -v`
Expected: FAIL

- [ ] **Step 3: Build chat module**

Start from MBSE's `src/agent/chat.py`. Major changes:

- Replace `_build_model_context()` with `_build_summary(project)` — returns counts only (requirements, DIGs, elements per layer, links, coverage %, uncovered count). Does NOT dump full state.
- Add `_build_system_prompt(project, mode)` — generates system prompt explaining Shipyard, available tools, current mode, project summary. Load base text from `src/model/prompts/agent_system.txt`.
- Update `chat_with_agent()` signature: `chat_with_agent(project: ProjectModel, user_message: str, conversation_history: list[dict], tracker: CostTracker, mode: str = "model")` — adds `mode` param.
- Tool loop: keep MBSE's loop (max 10 iterations) but use new `TOOL_DEFINITIONS` and `apply_tool` from consolidated tools.
- Update imports to `src.core.*` and `src.model.agent.tools`.

- [ ] **Step 4: Update agent_system.txt prompt**

Edit `src/model/prompts/agent_system.txt` to describe Shipyard (not just MBSE). Include:
- Description of both workflows (decompose + model)
- Available tools with brief descriptions
- Guidance on when to use each tool
- Mode-aware behavior (different suggestions per mode)

- [ ] **Step 5: Run test**

Run: `pytest tests/test_agent_chat.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/model/agent/chat.py src/model/prompts/agent_system.txt tests/test_agent_chat.py
git commit -m "feat: project-wide chat agent with tool-loop architecture"
```

---

## Phase 4: Web Backend

### Task 15: FastAPI app with project routes

**Files:**
- Create: `src/web/app.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write test for project endpoints**

```python
# tests/test_web.py
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

def test_root():
    # Will fail until we have templates, but app should load
    resp = client.get("/project/list")
    assert resp.status_code == 200

def test_create_project():
    resp = client.post("/project/new", json={"name": "Test Ship", "mode": "capella"})
    assert resp.status_code == 200
    assert resp.json()["project"]["name"] == "Test Ship"

def test_get_project():
    client.post("/project/new", json={"name": "Test Ship 2", "mode": "capella"})
    resp = client.get("/project")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web.py -v`
Expected: FAIL

- [ ] **Step 3: Build FastAPI app skeleton with project routes**

Create `src/web/app.py`. Start fresh but borrow patterns from MBSE's `src/web/app.py`. Include:

- FastAPI app setup with static files and templates
- Global state: `current_project`, `jobs` dict, `_undo_stack`, `_redo_stack`
- Project routes (Section 4.1 of spec): `/project/list`, `/project/new`, `/project`, `/project/select/{id}`, `/project/rename`, `/project/delete/{id}`, `/project/download`, `/project/import`, `/project/undo`, `/project/redo`, `/project/batches`
- Job dataclass from MBSE (with `emit()` method)
- Settings routes (Section 4.5): `/settings`, `POST /settings`, `/settings/models`, `/settings/auto-send`, `/settings/cost-history`, `/settings/check-updates`, `POST /settings/update`
- Root route `GET /` serving index.html template

- [ ] **Step 4: Run test**

Run: `pytest tests/test_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web.py
git commit -m "feat: FastAPI app with project management and settings routes"
```

---

### Task 16: Decompose routes

**Files:**
- Modify: `src/web/app.py`
- Test: `tests/test_decompose_routes.py`

- [ ] **Step 1: Write test for decompose endpoints**

```python
# tests/test_decompose_routes.py
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

def test_decompose_results_empty():
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/decompose/results")
    assert resp.status_code == 200
    assert resp.json() == []

def test_decompose_digs_no_reference():
    resp = client.get("/decompose/digs")
    assert resp.status_code == 200
    # Should return empty or error when no reference data loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_decompose_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Add decompose routes to app.py**

Add all routes from Section 4.2 of spec:
- `POST /decompose/upload` — upload GTR-SDS.xlsx, call `load_workbook_data()`, store in project
- `GET /decompose/digs` — return DIGs from loaded reference data
- `POST /decompose/run` — start async decompose job (adapted from reqdecomp's `_run_job_async`)
- `GET /decompose/stream/{job_id}` — SSE stream
- `POST /decompose/cancel/{job_id}` — cancel job
- `GET /decompose/results` — list decomposition trees metadata
- `GET /decompose/results/{dig_id}` — full tree
- `DELETE /decompose/results/{dig_id}` — delete tree
- `POST /decompose/estimate` — dry-run cost estimate
- `POST /decompose/send-to-model` — add requirement IDs to modeling_queue
- `POST /decompose/settings` — update decompose model/depth/breadth

The decompose job handler should:
1. For each DIG, call `decompose_dig()` from decompose module
2. Optionally run `apply_vv_to_tree()`, `validate_tree_structure()`, `run_semantic_judge()`, `refine_tree()`
3. Store trees in `project.decomposition_trees`
4. If auto_send is on, flatten to requirements and add to `modeling_queue`
5. Emit SSE events throughout
6. Auto-save project after completion

- [ ] **Step 4: Run test**

Run: `pytest tests/test_decompose_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_decompose_routes.py
git commit -m "feat: decompose API routes with upload, run, stream, results"
```

---

### Task 17: Model routes

**Files:**
- Modify: `src/web/app.py`
- Test: `tests/test_model_routes.py`

- [ ] **Step 1: Write test for model endpoints**

```python
# tests/test_model_routes.py
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

def test_model_queue_empty():
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/model/queue")
    assert resp.status_code == 200
    assert resp.json() == []

def test_model_dismiss_and_restore():
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    # Queue would be empty, but endpoint should work
    resp = client.post("/model/dismiss", json={"req_ids": ["REQ-1"]})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_routes.py -v`
Expected: FAIL

- [ ] **Step 3: Add model routes to app.py**

Add all routes from Section 4.3 of spec:
- `POST /model/upload` — parse requirements file, add to project
- `GET /model/queue` — compute queue: `modeling_queue - dismissed_from_modeling`
- `POST /model/dismiss` — add IDs to `dismissed_from_modeling`
- `POST /model/restore` — remove IDs from `dismissed_from_modeling`
- `POST /model/run` — start async MBSE pipeline job using `run_pipeline()` from model module. Merge results via `merge_batch_into_project()`.
- `GET /model/stream/{job_id}` — SSE stream (reuse same mechanism as decompose)
- `POST /model/cancel/{job_id}` — cancel job
- `POST /model/chat` — call `chat_with_agent()`, save chat history, auto-save project
- `POST /model/chat/clear` — clear chat history
- `POST /model/retry-instructions` — re-run instruct stage only
- `POST /model/settings` — update model settings

Add export routes (Section 4.4):
- `GET /export/decomposition` — call `export_trees_to_xlsx()`
- `GET /export/model/{fmt}` — call `export_json/xlsx/text()`
- `GET /export/full` — dump full project.json

- [ ] **Step 4: Run test**

Run: `pytest tests/test_model_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_model_routes.py
git commit -m "feat: model API routes with queue, pipeline, chat, export"
```

---

## Phase 5: Frontend

### Task 18: HTML template shell

**Files:**
- Create: `src/web/templates/index.html`
- Create: `src/web/templates/print.html`

- [ ] **Step 1: Create index.html**

Build the main SPA shell. Reference MBSE's `index.html` for structure but redesign per spec wireframes. Key sections:

- **Top bar:** Shipyard logo + version, Decompose/Model tabs, project selector dropdown, auto-send toggle, model indicator, Settings button, Agent toggle
- **Update notification banner** (hidden by default)
- **Decompose mode container** (shown/hidden by tab):
  - Upload area with drag-drop
  - Controls (depth/breadth sliders, V&V/Judge checkboxes)
  - DIG search + Run + Est. Cost bar
  - Results section with compact rows
- **Model mode container** (shown/hidden by tab):
  - Left sidebar: mode toggle, layer checkboxes, requirements drop zone, Add Batch button
  - Coverage bar
  - Content tabs: Model Tree, Links, Instructions, Raw JSON, Batches
  - Model tree view
  - Export dropdown
- **Agent side panel** (shared between modes, collapsible)
  - Chat history
  - Suggested prompts
  - Input + Send
- **Settings modal** (provider toggle, API keys, model selectors, auto-send, updates, cost history)
- **Confirmation modals** (cost estimate, mode switch warning, delete confirmation)
- **Toast notifications**

Template variables from FastAPI context:
- `{{ project }}` — current project JSON
- `{{ models }}` — model catalogue
- `{{ version }}` — Shipyard version
- `{{ settings }}` — current settings

- [ ] **Step 2: Create print.html**

Copy MBSE's `print.html` and adapt for Shipyard branding. Minor changes only.

- [ ] **Step 3: Verify template renders**

Run: `python -c "from src.web.app import app; print('Templates loaded')"`
Expected: Templates loaded

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/
git commit -m "feat: HTML templates with unified Decompose/Model layout"
```

---

### Task 19: CSS styling

**Files:**
- Create: `src/web/static/style.css`

- [ ] **Step 1: Build unified stylesheet**

Start from MBSE's `style.css` (44.9 KB, more comprehensive). Add/modify:

- **Top bar styles:** mode tabs (green for decompose, amber for model), project selector dropdown, agent toggle button
- **Decompose mode styles:** upload area, DIG search bar, result rows with queue badges, depth/breadth sliders
- **Agent panel styles:** slide-in panel, chat bubbles, suggested prompts, close button
- **Update banner:** thin notification bar at top
- **Mode switching:** `.mode-decompose` and `.mode-model` container visibility classes
- **Responsive adjustments:** agent panel collapses on narrow screens
- Keep MBSE's existing styles for: model tree, element cards, coverage bar, tabs, export dropdown, settings modal, toasts

Color scheme (from both apps — identical):
- Background: `#0a0a12`
- Card bg: `#12121e`
- Primary: `#7c7cff`
- Decompose accent: `#4ade80`
- Model accent: `#f59e0b`
- Text: `#e2e8f0`, `#94a3b8`, `#64748b`

- [ ] **Step 2: Commit**

```bash
git add src/web/static/style.css
git commit -m "feat: unified dark theme CSS for both modes"
```

---

### Task 20: JavaScript frontend

**Files:**
- Create: `src/web/static/app.js`

- [ ] **Step 1: Build unified frontend JS**

This is the largest single file (~3000-4000 lines). Structure it in sections:

**Section 1: State & initialization**
```javascript
let currentMode = 'decompose';  // 'decompose' | 'model'
let agentOpen = false;
let currentProject = null;
let currentJobId = null;
let eventSource = null;
// ... initialization on DOMContentLoaded
```

**Section 2: Mode switching**
- `switchMode(mode)` — toggle visibility of decompose/model containers, update tab styling, update agent suggested prompts

**Section 3: Project management**
- `loadProjectList()` — fetch `/project/list`, populate dropdown
- `createProject()` — modal → POST `/project/new`
- `selectProject(id)` — POST `/project/select/{id}`, reload all views
- `renameProject()`, `deleteProject()`, `downloadProject()`, `importProject()`

**Section 4: Decompose mode** (adapted from reqdecomp's `app.js`)
- `handleDecompUpload(input)` — POST `/decompose/upload`
- `loadDigs()` — GET `/decompose/digs`
- `startDecompose()` — POST `/decompose/run`, start SSE stream
- `estimateDecompCost()` — POST `/decompose/estimate`
- `loadDecompResults()` — GET `/decompose/results`
- `expandDecompResult(digId)` — GET `/decompose/results/{digId}`
- `deleteDecompResult(digId)` — DELETE `/decompose/results/{digId}`
- `sendToModel(digIds)` — POST `/decompose/send-to-model`
- Queue status badges ("Queued" / "Not sent") per result row

**Section 5: Model mode** (adapted from MBSE's `app.js`)
- `loadModelQueue()` — GET `/model/queue`
- `handleModelUpload(input)` — POST `/model/upload`
- `dismissFromQueue(ids)` — POST `/model/dismiss`
- `restoreToQueue(ids)` — POST `/model/restore`
- `startModelBatch()` — POST `/model/run`, start SSE stream
- `renderModelTree(layers)` — render collapsible tree
- `renderLinks(links)`, `renderInstructions(instructions)`, `renderBatches(batches)`, `renderRawJson()`
- `regenLayer(layer)` — POST via chat agent
- `addElement(layer, collection)` — inline add form
- Coverage bar rendering
- Tab switching within model mode

**Section 6: Agent panel**
- `toggleAgent()` — slide panel in/out, resize main content
- `sendAgentMessage(text)` — POST `/model/chat`, render response
- `renderChatHistory(history)` — render chat bubbles
- `renderSuggestedPrompts(mode)` — mode-specific suggestions
- Clickable suggested prompts that populate input

**Section 7: Settings**
- `openSettings()`, `closeSettings()`, `saveSettings()`
- Model selector cards
- Auto-send toggle
- Update check and install

**Section 8: SSE streaming** (shared between decompose and model jobs)
- `startStream(jobId, onEvent)` — connect to `/decompose/stream/` or `/model/stream/`
- Event handlers: progress bars, phase updates, completion, errors
- `cancelJob()` — POST cancel endpoint

**Section 9: Export**
- `exportDecomposition()` — GET `/export/decomposition`
- `exportModel(fmt)` — GET `/export/model/{fmt}`
- `exportFullProject()` — GET `/export/full`

**Section 10: Utilities**
- `showToast(msg)`, `showError(msg)`, `el(id)` (DOM helper)
- Drag-drop handlers
- Auto-send toggle handler

- [ ] **Step 2: Verify app loads in browser**

Run: `cd /Users/jude/Documents/projects/Shipyard && shipyard --web --port 8222`
Open: `http://localhost:8222`
Expected: UI renders with mode tabs, project selector, empty state

- [ ] **Step 3: Commit**

```bash
git add src/web/static/app.js
git commit -m "feat: unified frontend with Decompose/Model modes and agent panel"
```

---

## Phase 6: Integration & Polish

### Task 21: Data flow (auto-send, queue, dismiss)

**Files:**
- Modify: `src/web/app.py` (decompose job handler)
- Test: `tests/test_data_flow.py`

- [ ] **Step 1: Write test for auto-send flow**

```python
# tests/test_data_flow.py
from src.core.models.core import ProjectModel, ProjectMeta
from src.core.models.decompose import RequirementNode, RequirementTree

def test_auto_send_adds_to_queue():
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.auto_send = True
    # Simulate adding a decomposition tree
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test", root=root)
    project.decomposition_trees["9584"] = tree

    # Auto-send should populate modeling queue
    from src.web.app import _sync_modeling_queue
    _sync_modeling_queue(project)
    assert len(project.modeling_queue) > 0

def test_dismiss_removes_from_queue():
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.modeling_queue = ["REQ-1", "REQ-2", "REQ-3"]
    project.dismissed_from_modeling = ["REQ-2"]
    # Effective queue should exclude dismissed
    effective = [r for r in project.modeling_queue if r not in project.dismissed_from_modeling]
    assert effective == ["REQ-1", "REQ-3"]

def test_auto_send_off_does_not_queue():
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.auto_send = False
    root = RequirementNode(
        level=1, level_name="Whole Ship", allocation="GTR",
        chapter_code="1.1", derived_name="Test",
        technical_requirement="The vessel shall float",
        rationale="Buoyancy", system_hierarchy_id="SH-001",
    )
    tree = RequirementTree(dig_id="9584", dig_text="Test", root=root)
    project.decomposition_trees["9584"] = tree
    from src.web.app import _sync_modeling_queue
    _sync_modeling_queue(project)
    assert len(project.modeling_queue) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_flow.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auto-send and queue sync**

Add to `src/web/app.py`:

```python
def _flatten_tree_to_requirements(tree: RequirementTree) -> list[Requirement]:
    """Flatten a decomposition tree to a flat list of Requirements."""
    reqs = []
    def _walk(node, dig_id):
        req_id = f"{dig_id}-L{node.level}"
        if node.children:
            for i, child in enumerate(node.children, 1):
                child_id = f"{dig_id}-L{child.level}.{i}"
                reqs.append(Requirement(id=child_id, text=child.technical_requirement, source_dig=dig_id))
                _walk(child, dig_id)
        else:
            reqs.append(Requirement(id=req_id, text=node.technical_requirement, source_dig=dig_id))
    if tree.root:
        reqs.append(Requirement(id=f"{tree.dig_id}-L1", text=tree.root.technical_requirement, source_dig=tree.dig_id))
        _walk(tree.root, tree.dig_id)
    return reqs

def _sync_modeling_queue(project: ProjectModel):
    """Sync modeling queue based on auto_send setting."""
    if not project.auto_send:
        return
    all_req_ids = []
    for dig_id, tree in project.decomposition_trees.items():
        reqs = _flatten_tree_to_requirements(tree)
        all_req_ids.extend(r.id for r in reqs)
    project.modeling_queue = all_req_ids
```

Call `_sync_modeling_queue()` after each decomposition completes.

- [ ] **Step 4: Run test**

Run: `pytest tests/test_data_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_data_flow.py
git commit -m "feat: auto-send data flow with queue sync and dismiss"
```

---

### Task 22: Edge cases

**Files:**
- Modify: `src/web/app.py`
- Modify: `src/web/static/app.js`
- Test: `tests/test_edge_cases.py`

- [ ] **Step 1: Write test for orphaned link detection**

```python
# tests/test_edge_cases.py
from src.core.models.core import ProjectModel, ProjectMeta, Requirement, Link

def test_detect_orphaned_links():
    from src.web.app import _detect_orphaned_links
    project = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    project.links = [
        Link(id="LNK-1", source="REQ-OLD", target="OE-001", type="satisfies", description="test"),
        Link(id="LNK-2", source="REQ-VALID", target="OE-002", type="satisfies", description="test"),
    ]
    project.requirements = [Requirement(id="REQ-VALID", text="Valid", source_dig="9584")]
    orphaned = _detect_orphaned_links(project)
    assert len(orphaned) == 1
    assert orphaned[0].id == "LNK-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_edge_cases.py -v`
Expected: FAIL

- [ ] **Step 3: Implement edge case handlers**

Add to `src/web/app.py`:

**Orphaned link detection:**
```python
def _detect_orphaned_links(project: ProjectModel) -> list[Link]:
    req_ids = {r.id for r in project.requirements}
    element_ids = set()
    for layer_data in project.layers.values():
        for collection in layer_data.values():
            if isinstance(collection, list):
                for elem in collection:
                    if isinstance(elem, dict) and "id" in elem:
                        element_ids.add(elem["id"])
    valid_ids = req_ids | element_ids
    return [l for l in project.links if l.source not in valid_ids and l.target not in valid_ids]
```

**Mode switch warning:** Add to `/model/settings` POST handler — if mode changes and layers are non-empty, return `{"warning": "Switching mode will clear existing model"}` and require `confirm: true` in a follow-up request.

**Concurrent operation guard:** Add `_active_job_id` global. Check before starting new jobs.

**Re-decomposition warning:** In `POST /decompose/run`, check if DIGs being re-decomposed have requirements with traceability links. Return warning if so.

- [ ] **Step 4: Run test**

Run: `pytest tests/test_edge_cases.py -v`
Expected: PASS

- [ ] **Step 5: Implement frontend edge case handling**

In `app.js`:
- Mode switch confirmation modal
- Re-decomposition warning modal
- Concurrent job confirmation dialog
- Orphaned link indicators in the Links tab

- [ ] **Step 6: Commit**

```bash
git add src/web/app.py src/web/static/app.js tests/test_edge_cases.py
git commit -m "feat: edge case handling - orphaned links, mode switch, concurrency"
```

---

### Task 23: CLI entry point and setup wizard

**Files:**
- Create: `src/main.py`
- Reference: `/Users/jude/Documents/projects/MBSE/src/main.py`

- [ ] **Step 1: Create main.py**

```python
# src/main.py
import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="Shipyard - Ship Requirements & MBSE Platform")
    parser.add_argument("--web", action="store_true", help="Start web server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--setup", action="store_true", help="Run setup wizard")
    args = parser.parse_args()

    if args.setup:
        _run_setup()
    elif args.web:
        _start_web(args.host, args.port)
    else:
        parser.print_help()

def _start_web(host: str, port: int):
    import webbrowser
    webbrowser.open(f"http://{host}:{port}")
    uvicorn.run("src.web.app:app", host=host, port=port, reload=False)

def _run_setup():
    # Interactive setup wizard — adapted from MBSE's setup
    # Prompts for: provider, API keys, default models, default mode
    # Writes to .env file
    from src.core.config import CWD
    env_path = CWD / ".env"
    print("Shipyard Setup Wizard")
    print("=" * 40)
    provider = input("Provider (anthropic/openrouter/local) [anthropic]: ").strip() or "anthropic"
    # ... (adapt from MBSE's setup wizard)
    print(f"Configuration saved to {env_path}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI works**

Run: `shipyard --help`
Expected: Shows help with `--web`, `--setup`, `--host`, `--port` options

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: CLI entry point with web server and setup wizard"
```

---

### Task 24: End-to-end smoke test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write end-to-end test**

```python
# tests/test_e2e.py
"""
End-to-end smoke test: create project, verify both modes accessible,
settings work, and basic API responses are correct.
"""
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)

def test_full_workflow():
    # 1. Create project
    resp = client.post("/project/new", json={"name": "E2E Test", "mode": "capella"})
    assert resp.status_code == 200
    project = resp.json()
    assert project["project"]["name"] == "E2E Test"
    assert project["auto_send"] is True

    # 2. Check decompose mode (no reference data yet)
    resp = client.get("/decompose/results")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/decompose/digs")
    assert resp.status_code == 200

    # 3. Check model mode (empty queue)
    resp = client.get("/model/queue")
    assert resp.status_code == 200
    assert resp.json() == []

    # 4. Check settings
    resp = client.get("/settings")
    assert resp.status_code == 200
    settings = resp.json()
    assert "provider" in settings

    # 5. Check models list
    resp = client.get("/settings/models")
    assert resp.status_code == 200
    assert len(resp.json()) > 0

    # 6. Toggle auto-send
    resp = client.post("/settings/auto-send", json={"enabled": False})
    assert resp.status_code == 200

    # 7. List projects
    resp = client.get("/project/list")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # 8. Check project batches (empty)
    resp = client.get("/project/batches")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_e2e.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: end-to-end smoke test for full workflow"
```

---

### Task 25: Push to GitHub

- [ ] **Step 1: Verify all tests pass**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Push to remote**

```bash
git push -u origin main
```

- [ ] **Step 3: Verify on GitHub**

Check https://github.com/jude-sph/Shipyard — confirm code is visible.
