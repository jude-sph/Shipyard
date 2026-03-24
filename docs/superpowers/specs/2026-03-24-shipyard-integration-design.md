# Shipyard — Integration Design Spec

**Date:** 2026-03-24
**Status:** Draft
**Repo:** https://github.com/jude-sph/Shipyard.git

## 1. Overview

Shipyard is a unified web application that combines two existing shipbuilding requirements tools into a single service:

- **reqdecomp** (at `Documents/projects/Requirements`) — Takes raw Design Instructions & Guidelines (DIGs) from a GTR-SDS Excel workbook and decomposes them into hierarchical formal "shall" requirements using LLMs, with verification & validation, semantic review, and refinement.
- **MBSE Generator** (at `Documents/projects/MBSE`) — Takes decomposed requirements and generates Model-Based Systems Engineering structures (Capella/Arcadia or IBM Rhapsody/SysML) through a 5-stage LLM pipeline, with a chat agent for modifications.

**The problem:** Engineers currently export decomposed requirements from reqdecomp as XLSX, then manually upload them to the MBSE app. This file juggling breaks the workflow when iterating — decompose some requirements, model them, go back and adjust, send the next batch.

**The solution:** A single app where both workflows share a project. Decomposed requirements automatically flow to the modeling side. The engineer switches between Decompose and Model modes freely, with a project-wide AI agent that understands both domains.

## 2. Architecture

### 2.1 Unified Pipeline Architecture

Four-layer structure with a shared core and two domain modules:

```
┌─────────────────────────────────────────────────────────────┐
│  Web Layer — Single FastAPI Server                          │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │ Unified Frontend     │  │ FastAPI Routes               │ │
│  │ (Vanilla JS)         │  │ /decompose/* /model/*        │ │
│  │ Mode: Decompose|Model│  │ /project/*   /settings/*     │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│           ▼                          ▼                      │
│  ┌──────────────────┐     ┌────────────────────┐           │
│  │ Decompose Module │     │ Model Module       │           │
│  │ loader            │     │ stages/analyze     │           │
│  │ decomposer        │     │ stages/clarify     │           │
│  │ verifier           │     │ stages/generate    │           │
│  │ validator          │     │ stages/link        │           │
│  │ refiner            │     │ stages/instruct    │           │
│  │ prompts/           │     │ agent/chat + tools │           │
│  │                    │     │ prompts/           │           │
│  └──────────────────┘     └────────────────────┘           │
├─────────────────────────────────────────────────────────────┤
│  Core Layer — Shared Infrastructure                         │
│  ┌──────────┐ ┌────────────┐ ┌────────┐ ┌───────────────┐ │
│  │LLM Client│ │Cost Tracker│ │ Config │ │Project Manager│ │
│  ├──────────┤ ├────────────┤ ├────────┤ ├───────────────┤ │
│  │Data Models│ │  Exporter  │ │ Parser │ │   Prompts     │ │
│  └──────────┘ └────────────┘ └────────┘ └───────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Project Data — project.json (single file)                  │
│  Sources · Decomposition trees · MBSE model · Links ·      │
│  Batch history · Chat history · Cost logs                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
src/
├── core/
│   ├── config.py              # Settings, model catalogue, pricing
│   ├── llm_client.py          # Unified LLM client (Anthropic/OpenRouter/Local)
│   ├── cost_tracker.py        # Token & cost tracking with JSONL logs
│   ├── project.py             # Project persistence, undo/redo, backups
│   ├── exporter.py            # JSON/XLSX/Text export for both pipelines
│   ├── parser.py              # Flexible XLSX/CSV requirement parser
│   └── models/
│       ├── core.py            # ProjectModel, Requirement, Link, BatchRecord
│       ├── decompose.py       # RequirementNode, RequirementTree, ValidationResult
│       ├── capella.py         # Arcadia element schemas (~45 classes)
│       └── rhapsody.py        # SysML element schemas (~15 classes)
│
├── decompose/
│   ├── loader.py              # Parse GTR-SDS.xlsx reference data
│   ├── decomposer.py          # Recursive LLM decomposition (L1→L4)
│   ├── verifier.py            # V&V generation per node
│   ├── validator.py           # Structural checks + semantic judge
│   ├── refiner.py             # Auto-fix from judge feedback
│   └── prompts/               # decompose, vv, judge, refine templates
│
├── model/
│   ├── pipeline.py            # 5-stage orchestration
│   ├── stages/
│   │   ├── analyze.py         # Flag ambiguous requirements
│   │   ├── clarify.py         # Apply user clarifications
│   │   ├── generate.py        # Layer-by-layer MBSE generation
│   │   ├── link.py            # Traceability link generation
│   │   └── instruct.py        # Tool-specific recreation instructions
│   ├── agent/
│   │   ├── chat.py            # Project-wide chat agent
│   │   └── tools.py           # Agent tools (7 consolidated tools)
│   └── prompts/               # Capella & Rhapsody generation templates
│
└── web/
    ├── app.py                 # FastAPI server — all routes
    ├── templates/
    │   ├── index.html         # Main SPA shell
    │   └── print.html         # Print-friendly view
    └── static/
        ├── app.js             # Unified frontend
        └── style.css          # Dark theme styling
```

### 2.3 Source Code Origin

- **Core layer:** Primarily from MBSE (more mature LLM client with local provider + tool calling support, cost tracker with JSONL logging, project persistence with undo/redo). Config merges both apps' model catalogues.
- **Decompose module:** From reqdecomp — loader, decomposer, verifier, validator, refiner, and prompts transplanted with minimal changes. The web routes and CLI are replaced by Shipyard's unified web layer.
- **Model module:** From MBSE — pipeline, stages, agent, and prompts carried over. Agent expanded with decomposition-aware tools.
- **Web layer:** New unified frontend. Structure and dark theme from MBSE, decompose UI patterns from reqdecomp.

## 3. Data Model

### 3.1 ProjectModel (single file: project.json)

```python
ProjectModel:
  # Project metadata
  project: ProjectMeta
    name: str                           # e.g., "Polar Icebreaker"
    mode: "capella" | "rhapsody"
    created: datetime
    modified: datetime

  # Source data (multiple files supported)
  sources: list[SourceFile]
    filename: str
    upload_time: datetime
    file_type: "reference" | "requirements"
    sha256: str
    # Original file bytes stored in projects/<project_id>/uploads/

  # Decomposition side
  reference_data: WorkbookData | None   # Parsed GTR-SDS reference data
  decomposition_trees: dict[str, RequirementTree]  # dig_id → full tree
  decomposition_settings: DecompSettings
    max_depth: int                      # 1-4, default 4
    max_breadth: int                    # default 3
    skip_vv: bool                       # default false
    skip_judge: bool                    # default false
    model: str                          # LLM model for decomposition

  # Data flow control
  auto_send: bool                       # default True
  modeling_queue: list[str]             # requirement IDs available for modeling
  dismissed_from_modeling: set[str]     # IDs hidden from modeling (not deleted)

  # Modeling side
  requirements: list[Requirement]       # flat list consumed by MBSE pipeline
  layers: dict[str, dict]              # generated MBSE model elements by layer
  links: list[Link]                    # traceability relationships
  instructions: dict                   # tool-specific recreation steps
  model_settings: ModelSettings
    selected_layers: list[str]
    model: str                          # LLM model for modeling

  # Shared
  batches: list[BatchRecord]           # all operations, tagged by type
    batch_type: "decompose" | "model" | "import"
    timestamp: datetime
    details: dict                       # type-specific metadata
    cost: CostSummary
    requirement_snapshot: list[str]     # req IDs used (for orphan detection)
  chat_history: list[dict]             # project-wide agent conversation
  cost_summary: CostSummary            # aggregated costs, broken down by pipeline
  undo_stack: list[snapshot]           # max 20
  redo_stack: list[snapshot]
```

### 3.2 Key Data Structures (from existing apps)

**RequirementNode** (decomposition hierarchy):
```python
RequirementNode:
  level: int                            # 1-4
  level_name: str                       # Whole Ship, Major System, Subsystem, Equipment
  allocation: str                       # GTR | SDS | GTR / SDS
  chapter_code: str
  derived_name: str
  technical_requirement: str            # IEEE 29481 "shall" statement
  rationale: str
  system_hierarchy_id: str
  acceptance_criteria: str | None
  verification_method: list[str]
  verification_event: list[str]
  test_case_descriptions: list[str]
  confidence_notes: str | None
  decomposition_complete: bool
  children: list[RequirementNode]
```

**Requirement** (flat, for MBSE pipeline):
```python
Requirement:
  id: str                               # e.g., "9584-L2.1"
  text: str                             # the "shall" statement
  source_dig: str                       # originating DIG ID
```

**Link** (traceability):
```python
Link:
  id: str                               # LNK-001, etc.
  source: str                           # requirement or element ID
  target: str                           # element ID
  type: str                             # satisfies, realizes, implements, etc.
  description: str
```

### 3.3 Project Storage

- **Server-side directory:** `projects/` contains one subdirectory per project
  - `projects/<project_id>/project.json` — single project file (all state)
  - `projects/<project_id>/uploads/` — original uploaded files
  - `projects/<project_id>/cost_log.jsonl` — detailed cost history
- **Auto-save:** After every batch operation (decompose or model)
- **Project selector:** Dropdown in the top bar listing all projects with last-modified timestamps
- **Download/Import:** For sharing and backup (compressed JSON option for large projects)

## 4. API Design

### 4.1 Project Management (`/project/*`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/project/list` | List all saved projects (name, modified, summary) |
| POST | `/project/new` | Create project (name, mode) |
| GET | `/project` | Get current project state |
| POST | `/project/select/{id}` | Switch to a different project |
| POST | `/project/rename` | Rename current project |
| POST | `/project/delete/{id}` | Delete a saved project |
| GET | `/project/download` | Download project as JSON |
| POST | `/project/import` | Import project from JSON file |
| POST | `/project/undo` | Undo last operation |
| POST | `/project/redo` | Redo last undo |
| GET | `/project/batches` | List batch history (filterable by type) |

### 4.2 Decomposition (`/decompose/*`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/decompose/upload` | Upload GTR-SDS.xlsx or additional source file |
| GET | `/decompose/digs` | List available DIGs from loaded reference data |
| POST | `/decompose/run` | Start decomposition job (DIG IDs, settings) |
| GET | `/decompose/stream/{job_id}` | SSE progress stream |
| POST | `/decompose/cancel/{job_id}` | Cancel running job |
| GET | `/decompose/results` | List all decomposed trees (metadata) |
| GET | `/decompose/results/{dig_id}` | Get full tree for a DIG |
| DELETE | `/decompose/results/{dig_id}` | Delete a decomposition |
| POST | `/decompose/estimate` | Dry-run cost estimate |
| POST | `/decompose/send-to-model` | Manually send requirement IDs to modeling queue |
| POST | `/decompose/settings` | Update decomposition model + depth/breadth |

### 4.3 Modeling (`/model/*`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/model/upload` | Direct upload of pre-decomposed requirements |
| GET | `/model/queue` | Get requirements available for modeling |
| POST | `/model/dismiss` | Hide requirements from modeling queue |
| POST | `/model/restore` | Restore dismissed requirements |
| POST | `/model/run` | Start MBSE pipeline job |
| GET | `/model/stream/{job_id}` | SSE progress stream |
| POST | `/model/cancel/{job_id}` | Cancel running job |
| POST | `/model/chat` | Chat with project-wide agent |
| POST | `/model/chat/clear` | Clear chat history |
| POST | `/model/retry-instructions` | Regenerate recreation instructions |
| POST | `/model/settings` | Update modeling model + layer selection |

### 4.4 Export (`/export/*`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/export/decomposition` | Export decomposed requirements (XLSX) |
| GET | `/export/model/{fmt}` | Export MBSE model (json/xlsx/text) |
| GET | `/export/full` | Export full project (JSON, optionally compressed) |

### 4.5 Settings (`/settings/*`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/settings` | Get current config |
| POST | `/settings` | Update API keys, provider, LLM provider (API/Local) |
| GET | `/settings/models` | List available models with pricing |
| POST | `/settings/auto-send` | Toggle auto-send on/off |
| GET | `/settings/cost-history` | Cost summary broken down by pipeline |
| GET | `/settings/check-updates` | Check for GitHub updates |
| POST | `/settings/update` | Pull latest and reinstall |

### 4.6 Utility

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve main UI |

## 5. Frontend Design

### 5.1 Navigation Structure

Persistent top bar across both modes:

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚓ Shipyard v1.0.0 │ [Decompose|Model] │ ▾ Polar Icebreaker ▾  │
│                     │                    │ Saved 16:45           │
│                  Auto-send: ON │ ● claude-sonnet-4-6 │ ⚙ Settings│ ◆ Agent │
└──────────────────────────────────────────────────────────────────┘
```

- **Mode switcher:** Decompose (green) / Model (amber) tabs
- **Project selector:** Dropdown listing saved projects, with New/Rename/Delete/Download/Import
- **Auto-send toggle:** Shows ON/OFF status, clickable to toggle
- **Active model indicator:** Shows current model name with provider dot
- **Settings:** Opens settings panel (API keys, provider, models, updates)
- **Agent toggle:** Opens/closes the agent side panel

### 5.2 Decompose Mode

```
┌─────────────────────────────────────────────────────────────┐
│ [Top Bar]                                                    │
├─────────────────────────────────────────────┬───────────────┤
│ INPUT                                        │               │
│ ┌─────────────────────────┐ ┌──────────┐   │  ◆ Agent      │
│ │ 📄 GTR-SDS.xlsx loaded  │ │ Depth: 3 │   │               │
│ │ [⬇Source] [⬇Results]    │ │ Breadth:2│   │  [Chat        │
│ │ [+Upload Another]       │ │ ☑V&V     │   │   history     │
│ └─────────────────────────┘ │ ☑Judge   │   │   and         │
│                              └──────────┘   │   suggested   │
│ [Search DIGs or blank for all] [▶Run] [Est] │   prompts]   │
│                                              │               │
│ RESULTS — 5 DIGS, 19 REQUIREMENTS           │               │
│ ┌──────────────────────────────────────────┐ │               │
│ │ DIG 9584  The Vessel must...  Queued     │ │               │
│ │           1 lvl · 1 node · $0.05   ⊕ ×  │ │               │
│ ├──────────────────────────────────────────┤ │               │
│ │ DIG 9646  With a clean hull...  Queued   │ │               │
│ │           3 lvl · 3 nodes · $0.19  ⊕ ×  │ │               │
│ ├──────────────────────────────────────────┤ │               │
│ │ DIG 9694  While in WMO...  Not sent      │ │               │
│ │           3 lvl · 3 nodes · $0.21  ⊕ ×  │ │               │
│ └──────────────────────────────────────────┘ │               │
│                                              │  [Ask input]  │
└──────────────────────────────────────────────┴───────────────┘
```

Key elements:
- **Upload area:** Drag-drop or click. Shows loaded file with DIG count. Download Source/Results XLSX buttons. "+ Upload Another" for multiple sources.
- **Controls:** Depth/breadth sliders, V&V and Judge checkboxes, model shown in top bar
- **DIG selector:** Search input — type DIG IDs (comma-separated) or leave blank for all
- **Results:** Compact rows with DIG ID, text preview, queue status badge ("Queued" / "Not sent"), levels, nodes, cost, expand (⊕) and delete (×) buttons
- **Agent panel:** Collapsible side panel (see Section 5.4)

### 5.3 Model Mode

```
┌──────────────────────────────────────────────────────────────┐
│ [Top Bar]                                                     │
├──────────┬───────────────────────────────────┬───────────────┤
│ MODE     │ Coverage: 15/19 (79%) ████░ 4 unc│               │
│[Cap|Rhap]│                                   │  ◆ Agent      │
│          │ [Model Tree|Links|Instr|JSON|Batch│               │
│ LAYERS   │                                   │  [Chat        │
│ ☑ OA     │ ▾ Logical Architecture (LA)       │   history     │
│ ☑ SA     │   8 elements        [✦ Regen]     │   and         │
│ ☑ LA     │   ▾ Components (2)                │   suggested   │
│ ☑ PA     │     LC-001 Propulsion & Manoeuv.  │   prompts]   │
│ ☐ EPBS   │     LC-002 Bridge & Command       │               │
│          │     + Add                          │               │
│ REQS     │   ▾ Functions (6)                  │               │
│ [Drop    │     LF-001 Generate Propulsive...  │               │
│  here]   │     LF-002 Control Azimuth Thru... │               │
│ 19 decomp│       component: LC-001            │               │
│ 0 direct │     + Add                          │               │
│          │                                    │               │
│[▶Add Bat]│ ▸ Physical Architecture (PA)       │               │
│          │   20 elements        [✦ Regen]     │  [Ask input]  │
│          │                          [⬇Export] │               │
└──────────┴───────────────────────────────────┴───────────────┘
```

Key elements:
- **Left sidebar:** Mode toggle (Capella/Rhapsody), layer checkboxes, requirements drop zone with counts (from decomposition vs direct upload), "Add Batch" button
- **Coverage bar:** Prominent at top — requirement count, percentage, progress bar, "N uncovered" badge
- **Content tabs:** Model Tree, Links, Instructions, Raw JSON, Batches
- **Model tree:** Collapsible layers with element count and "Regen" button per layer. Collections with element rows showing ID and name. Expandable element details. "+ Add" per collection.
- **Export dropdown:** JSON, XLSX, Text options
- **Agent panel:** Same collapsible side panel as Decompose mode

### 5.4 Agent Panel

The agent panel is identical in both modes — a collapsible side panel that slides in from the right.

**Behavior:**
- **Toggle:** "◆ Agent" button in top bar. Shows "◆ Agent ✕" when open.
- **Open:** Panel slides in, main content area shrinks to accommodate.
- **Closed:** Panel disappears completely. Main content expands to full width. No bottom bar, no minimized state.
- **Persistent:** Chat history preserved when toggling. Switching modes preserves the conversation.
- **Context-aware:** Suggested prompts change based on current mode.

**Panel contents:**
- Chat history (user messages and agent responses)
- Suggested prompts section at the bottom of chat area (mode-specific examples)
- Text input with Send button at the bottom

**Decompose mode suggestions:**
- "Re-run DIG 9694 with depth 4"
- "Show all validation warnings"
- "Which DIGs haven't been decomposed?"
- "Send DIG 9694 to modeling"
- "Why was DIG 9584 only 1 level deep?"
- "Edit requirement 9584-3 to use GTR allocation"

**Model mode suggestions:**
- "Show traceability from DIG 9584 to physical components"
- "Which requirements don't have traceability links yet?"
- "Add a logical component for ice detection sensors"
- "What's the coverage for the propulsion requirements?"
- "Re-decompose requirement 9584-3 with more detail"
- "Regenerate the Operational Analysis layer"
- "Compare the decomposition of DIG 9584 vs DIG 9646"

### 5.5 Update Notification

- **Settings page:** Contains "Check for Updates" and "Update" functionality
- **Notification banner:** Thin dismissible bar at the top of the page when an update is available: "Shipyard v1.1.0 is available. Update in Settings ✕"
- **Settings indicator:** Small dot on the Settings gear icon when an update is available

### 5.6 Empty States and Onboarding

- **New project:** Defaults to Decompose mode
- **Decompose empty state:** Upload area prominent with guidance: "Upload a GTR-SDS workbook to get started, or switch to Model to upload pre-decomposed requirements"
- **Model empty state:** Shows requirements drop zone and guidance: "Decompose requirements first, or upload pre-decomposed requirements (XLSX/CSV) directly"
- **No reference data in Decompose mode:** Clear message: "Upload a GTR-SDS reference workbook to enable decomposition" rather than a cryptic error

## 6. Data Flow

### 6.1 Auto-Send (Default)

```
Engineer uploads GTR-SDS.xlsx → reference data loaded
Engineer selects DIGs → runs decomposition
  → RequirementTrees stored in project
  → Flat requirements auto-added to modeling_queue
Engineer switches to Model mode
  → Sees requirements in queue (from decomposition)
  → Selects layers, clicks "Add Batch"
  → MBSE pipeline runs on queued requirements
```

### 6.2 Manual Send (Auto-Send OFF)

```
Engineer toggles auto-send OFF
Engineer decomposes DIGs → trees stored but NOT queued
Engineer reviews results, selects specific DIGs
Engineer clicks send (or uses agent: "Send DIG 9584 to modeling")
  → Selected requirements added to modeling_queue
Engineer switches to Model mode → sees only manually sent requirements
```

### 6.3 Direct Upload to Modeling

```
Engineer switches to Model mode
Engineer uploads pre-decomposed requirements XLSX/CSV
  → Parser auto-detects columns (id, text, source_dig)
  → Requirements added directly to modeling queue
  → No decomposition trees created (decompose mode unaffected)
```

### 6.4 Dismiss from Modeling

```
Engineer sees requirements in Model queue
Engineer dismisses some (hide from queue)
  → Removed from modeling_queue, added to dismissed_from_modeling
  → Still visible in Decompose mode with full tree
  → Can be restored via Model queue UI or agent
```

## 7. Agent Architecture

### 7.1 Design Principle

The agent does NOT receive the full project state in its context. Instead:

- **System prompt:** Describes the project structure, available tools, and the engineer's current mode. Includes summary counts only (e.g., "12 decomposed DIGs, 47 requirements, 83 model elements, 61 links, 4 uncovered").
- **Tool loop:** The agent reasons about what data it needs, calls read tools to fetch it, then acts or responds. It continues looping until it has enough information or needs engineer input.
- **Model selection:** The agent uses the decompose model for decomposition operations and the MBSE model for modeling operations. For read-only queries, no LLM call is needed beyond the agent's own reasoning.

### 7.2 Tools (7 Consolidated)

**Read tools (2):**

| Tool | Purpose |
|------|---------|
| `query_project(scope, filter?)` | Flexible read tool. Scope: "requirements", "elements", "links", "batches", "coverage", "validation", "reference", "summary". Filter narrows by DIG, layer, ID, status, etc. Replaces 10+ individual read tools. |
| `trace(id)` | Trace any ID (requirement or element) through the full chain: DIG → decomposition tree path → model elements → links. Returns the complete traceability story. |

**Write tools (5):**

| Tool | Purpose |
|------|---------|
| `modify_decomposition(action, params)` | Actions: "edit", "add", "remove", "re_decompose". All decomposition mutations through one tool. |
| `modify_model(action, params)` | Actions: "add_element", "edit_element", "remove_element", "add_link", "edit_link", "remove_link", "regenerate_layer", "clear_layer". All model mutations through one tool. |
| `manage_queue(action, req_ids)` | Actions: "send", "dismiss", "restore". Queue management. |
| `batch_modify(operations)` | Multiple modifications in one call. Wraps modify_decomposition and modify_model actions. |
| `validate(scope?)` | Run validation across decomposition, model, or both. Scope: "decomposition", "model", "all". Returns unified report. |

### 7.3 Tool Loop Example

**Engineer asks:** "Show traceability from DIG 9584 to physical components"

1. Agent calls `query_project(scope="requirements", filter={dig_id: "9584"})` → gets list of requirement IDs
2. Agent calls `trace("9584-L1")` → gets full chain for the root requirement
3. Agent calls `query_project(scope="elements", filter={layer: "PA"})` → gets physical components
4. Agent calls `query_project(scope="links", filter={type: "realizes"})` → gets relevant links
5. Agent synthesizes and responds with the full traceability chain

**Engineer asks:** "Fix the allocation on requirement 9584-L3.2"

1. Agent calls `query_project(scope="requirements", filter={id: "9584-L3.2"})` → sees current state
2. Agent calls `query_project(scope="reference", filter={type: "chapters"})` → checks valid chapter codes
3. Agent calls `modify_decomposition(action="edit", params={id: "9584-L3.2", allocation: "SDS", chapter_code: "4.3"})` → applies fix
4. Agent calls `validate(scope="decomposition")` → confirms the fix resolved the issue
5. Agent responds with confirmation

## 8. Configuration

### 8.1 Environment (.env)

```
PROVIDER=anthropic                    # "anthropic", "openrouter", or "local"
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
LOCAL_LLM_URL=http://localhost:11434/v1
DECOMPOSE_MODEL=claude-sonnet-4-6     # Model for decomposition
MBSE_MODEL=claude-opus-4-6           # Model for MBSE generation
DEFAULT_MODE=capella                   # "capella" or "rhapsody"
```

### 8.2 Settings Page

Consolidated settings (LLM Provider toggle and Update functionality both live here):

- **Provider:** API (Anthropic/OpenRouter) or Local toggle
- **API Keys:** Anthropic and OpenRouter key inputs (shared across both pipelines)
- **Decompose Model:** Model selector for decomposition pipeline
- **MBSE Model:** Model selector for MBSE pipeline
- **Default Mode:** Capella or Rhapsody
- **Auto-Send:** Toggle (also accessible from top bar)
- **Updates:** Check for updates, install updates
- **Cost History:** Breakdown by pipeline (decompose vs model)

### 8.3 Per-Workflow Model Selection

Both pipelines share API keys and provider config, but each has its own model selection. This allows engineers to use a cheaper model for decomposition (e.g., Haiku for straightforward decomposition) and a stronger model for MBSE generation (e.g., Opus for complex architectural reasoning).

## 9. Edge Cases & Error Handling

### 9.1 Orphaned Link Detection

When re-decomposing a DIG that has already been modeled:

1. Before re-decomposing, check if any requirement IDs from this DIG appear in traceability links
2. If so, warn the engineer: "DIG 9584 has 5 requirements with traceability links. Re-decomposing may change requirement IDs. Existing model links will be preserved but may reference outdated requirements."
3. After re-decomposition, scan for orphaned links (links whose source requirement ID no longer exists)
4. Surface orphaned links in the validation report and in the agent's context

### 9.2 Mode Switch Warning

Switching between Capella and Rhapsody invalidates existing model elements (different schemas):

1. If the model has generated elements, show confirmation: "Switching to Rhapsody will clear the existing Capella model (8 elements, 12 links). Decomposed requirements are preserved. Continue?"
2. On confirmation, clear model layers, links, and instructions. Preserve decomposition trees, requirements queue, batch history.
3. Batch history records the mode switch event.

### 9.3 Requirement Identity Across Re-Decomposition

Each model batch records a `requirement_snapshot` — the list of requirement IDs that were used. This allows:
- Detecting which batches are affected by re-decomposition
- Preserving historical traceability even if current requirements change
- Showing "this batch used requirements that have since been re-decomposed" in batch history

### 9.4 Reference Data Dependency

- Decompose mode requires a GTR-SDS reference workbook for decomposition to work
- If no reference data is loaded, the Decompose UI shows a clear empty state rather than error
- Model mode does NOT require reference data — it works with flat requirements from any source
- If the engineer switches to Decompose mode without reference data: upload area is prominent with guidance text

### 9.5 Concurrent Operations

- Only one pipeline job (decompose or model) can run at a time
- Starting a second job shows confirmation: "A decomposition job is already running. Cancel it and start modeling?"
- The agent can still respond to read-only queries while a job is running
- The agent cannot perform write operations while a job is running (to avoid conflicts)

### 9.6 LLM Failures

- Retry with exponential backoff (3 attempts: 2s, 5s, 10s — same as both apps)
- Partial results preserved on failure — the engineer sees what completed
- SSE stream emits error events with descriptive messages
- Agent operations that fail are reported in chat with the error context

### 9.7 Cost Tracking

- Costs are tracked per-call with pipeline attribution ("decompose" or "model")
- Cost history endpoint returns breakdown by pipeline
- Top bar shows aggregate running cost for the project
- Each batch record includes its cost summary

### 9.8 Validation Unification

The `validate` agent tool and any "validate project" action runs both:
1. **Decomposition validation:** Structural checks (shall statements, valid chapter codes, hierarchy IDs, V&V array lengths) + semantic judge review
2. **Model validation:** Coverage analysis, link integrity (no orphaned references), element completeness

Results are presented as a unified report with sections for each domain.

### 9.9 Export Disambiguation

Three distinct export paths:
- **Export Decomposition:** Flattened XLSX of requirement trees (same as reqdecomp's export)
- **Export Model:** MBSE model as JSON, XLSX (elements per layer), or text (human-readable)
- **Export Full Project:** Complete project.json (optionally compressed) for backup/sharing

## 10. Deployment

### 10.1 Installation

```bash
git clone https://github.com/jude-sph/Shipyard.git
cd Shipyard
pip install -e .
```

### 10.2 Configuration

```bash
shipyard --setup    # Interactive wizard for .env configuration
```

### 10.3 Running

```bash
shipyard --web                    # Start on default port 8000
shipyard --web --port 8111        # Custom port
shipyard --web --host 0.0.0.0     # Bind to all interfaces
```

### 10.4 Project Storage

Projects are stored in the working directory under `projects/`:
```
projects/
├── polar-icebreaker/
│   ├── project.json
│   ├── uploads/
│   │   └── GTR-SDS.xlsx
│   └── cost_log.jsonl
├── patrol-vessel/
│   ├── project.json
│   └── ...
```

## 11. Supported Models

Both pipelines support the full model catalogue (inherited from both apps):

**Anthropic Direct:** Claude Sonnet 4.6, Claude Haiku 4.5, Claude Opus 4.6
**OpenRouter:** Gemini 2.5 Flash/Pro, DeepSeek V3/R1, GPT-4o/Mini, Qwen 3 variants, Llama, and others
**Local:** Any OpenAI-compatible local LLM (Ollama, LM Studio, etc.)

Each model has pricing data for cost estimation. OpenRouter returns actual costs; Anthropic and local use estimates from the pricing table.

## 12. Modeling Methodologies

### 12.1 Capella (Arcadia)

5 layers, each with multiple element collections:
- **Operational Analysis (OA):** Entities, capabilities, scenarios, activities, processes, interactions, communication means, data, interaction items, modes & states
- **System Needs Analysis (SA):** Functions, exchanges, system definitions, external actors, capabilities, functional chains, scenarios, data, exchanged items, modes & states
- **Logical Architecture (LA):** Components, functions, capabilities, interfaces, exchanges, data, capability realizations
- **Physical Architecture (PA):** Components, functions, interfaces, exchanges, data, links
- **EPBS:** Configuration items, build items, development items

### 12.2 Rhapsody (SysML)

6 diagram types:
- **Requirements Diagram:** Requirements with priority and status
- **Block Definition Diagram (BDD):** Blocks with properties and ports
- **Internal Block Diagram (IBD):** Parts and connectors
- **Activity Diagram:** Actions with inputs/outputs
- **Sequence Diagram:** Lifelines and messages
- **State Machine Diagram:** States and transitions

## 13. Wireframes

Interactive wireframes for the full UI are available in the project's brainstorm directory:

- `.superpowers/brainstorm/` — HTML mockups showing:
  - Architecture overview diagram
  - Decompose mode (with agent open)
  - Model mode (agent open and agent closed states)
  - Agent panel behavior (collapsible, consistent across modes)
  - Update notification banner
  - Project selector
