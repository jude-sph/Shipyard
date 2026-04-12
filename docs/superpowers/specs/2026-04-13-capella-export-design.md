# Capella Native Export — Design Spec

**Date:** 2026-04-13
**Status:** Approved

## Summary

Export Shipyard MBSE models to native Capella `.melodymodeller` files that can be opened directly in Eclipse Capella. Two modes: complete project (zipped folder) or model fragment (single file for import into existing projects).

## Scope

- Capella export only (Rhapsody deferred to future work)
- Semantic model only (no `.aird` diagram layouts — capellambse cannot persist these)
- All 5 Capella layers: OA, SA, LA, PA, EPBS
- Cross-layer links exported as Capella traceability relationships

## Dependencies

- `capellambse` Python package (pure Python, no Java/Capella installation required)

## Architecture

### New Files

**`src/core/capella_export.py`** (~200-300 lines)

Single module responsible for converting Shipyard's layer data into a capellambse model and writing it to disk.

Public API:
```python
def export_capella_project(project: ProjectModel, output_path: Path) -> Path:
    """Export as a complete Capella project (zipped folder).
    Returns path to the zip file."""

def export_capella_fragment(project: ProjectModel, output_path: Path) -> Path:
    """Export as a .melodymodeller fragment file.
    Returns path to the file."""
```

### Layer Mapping

Each Shipyard layer maps to Capella's metamodel:

| Shipyard Layer | Capella Architecture | Key Mappings |
|---|---|---|
| `operational_analysis` | Operational Analysis | entities → OperationalEntities, capabilities → OperationalCapabilities, interactions → CommunicationMeans, activities → OperationalActivities |
| `system_needs_analysis` | System Analysis | functions → SystemFunctions, exchanges → FunctionalExchanges, actors → Actors, system_definitions → System |
| `logical_architecture` | Logical Architecture | components → LogicalComponents, functions → LogicalFunctions, exchanges → FunctionalExchanges |
| `physical_architecture` | Physical Architecture | components → PhysicalComponents, functions → PhysicalFunctions, links → PhysicalLinks |
| `epbs` | EPBS | configuration_items → ConfigurationItems |

### Link Mapping

Shipyard link types map to Capella relationship types:

| Shipyard Link Type | Capella Relationship |
|---|---|
| `satisfies` | AbstractTrace (requirement to function) |
| `realizes` | Realization (cross-layer) |
| `implements` | Realization |
| `allocates` | ComponentFunctionalAllocation |
| `traces` | AbstractTrace |

### Backend Changes

**`src/web/app.py`** — one new endpoint:

```
GET /export/model/capella?mode=project|fragment
```

- `mode=project` (default): returns a `.zip` file containing the Capella project folder
- `mode=fragment`: returns a single `.melodymodeller` file

Response: `FileResponse` with appropriate content-disposition header.

### Frontend Changes

**`src/web/static/app.js`** — add to `exportProject()` or as a new function:

Two new buttons in the export dropdown menu:
- "Export Capella Project" → downloads zip
- "Export Capella Fragment" → downloads .melodymodeller

Only shown when `selectedToolMode === 'capella'`.

**`src/web/templates/index.html`** — add buttons to export menu.

## Data Flow

```
User clicks "Export Capella Project"
  → GET /export/model/capella?mode=project
  → app.py reads current_project
  → calls export_capella_project(project, tmp_path)
    → creates capellambse empty model
    → iterates project.layers, maps each to capellambse objects
    → iterates project.links, creates traceability relationships
    → writes .melodymodeller to tmp directory
    → zips the project folder
  → returns FileResponse with zip
  → browser downloads shipyard-export.zip
```

## Error Handling

- No layers generated → HTTP 400 "No model layers to export"
- capellambse not installed → HTTP 500 with clear message to install dependency
- Empty layer (no elements) → skip that layer silently
- Element mapping failure → log warning, skip element, continue with rest

## What the User Gets

### Complete Project (zip)
```
shipyard-export/
  shipyard-export.melodymodeller    # semantic model
  .project                          # Eclipse project metadata
```

User unzips, opens in Capella via File → Import → Existing Projects.

### Fragment
```
shipyard-export.melodymodeller      # single file
```

User imports via Capella's fragment import mechanism.

## Out of Scope

- `.aird` diagram layout generation (capellambse limitation)
- Rhapsody export (separate future spec)
- Round-trip import (Capella → Shipyard)
- Requirements viewpoint export (only model elements)
