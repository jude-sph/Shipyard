# Capella Native Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export Shipyard MBSE models as native Capella `.capella` project files that can be opened directly in Eclipse Capella.

**Architecture:** Bundle a minimal blank Capella project template. On export, copy the template, load it with `capellambse`, populate it with Shipyard model data using capellambse's create/append API, save, and zip. Two modes: complete project (zip) or fragment (single file).

**Tech Stack:** capellambse (Python, already installed), lxml (transitive dependency of capellambse)

---

### Task 1: Create blank Capella template

**Files:**
- Create: `src/core/templates/blank.capella`
- Create: `src/core/templates/.project`

The template is a minimal valid Capella project with empty OA/SA/LA/PA/EPBS layers. We derive it from the coffee-machine example by cloning, loading, and examining the structure.

- [ ] **Step 1: Generate minimal blank template**

Run this script to create the template files:

```bash
python3 -c "
import subprocess, tempfile, shutil, os
from pathlib import Path

tmp = tempfile.mkdtemp()
subprocess.run(['git', 'clone', '--depth=1', 'https://github.com/DSD-DBS/coffee-machine.git', tmp + '/cm'], capture_output=True)

import capellambse
model = capellambse.MelodyModel(tmp + '/cm')

# Save as our template base - we'll use the .capella file as-is
# (it has the correct XML structure with empty-ish layers)
src_capella = None
for f in os.listdir(tmp + '/cm'):
    if f.endswith('.capella'):
        src_capella = tmp + '/cm/' + f
        break

# Copy to our templates dir
templates_dir = Path('src/core/templates')
templates_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(src_capella, templates_dir / 'blank.capella')

# Create .project template
project_xml = '''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<projectDescription>
  <name>shipyard-export</name>
  <comment></comment>
  <projects></projects>
  <buildSpec></buildSpec>
  <natures></natures>
</projectDescription>'''
(templates_dir / '.project').write_text(project_xml)

print('Template files created')
shutil.rmtree(tmp)
"
```

- [ ] **Step 2: Verify template loads with capellambse**

```bash
python3 -c "
import capellambse
model = capellambse.MelodyModel('src/core/templates')
print('Template loaded:', model.name)
print('OA:', model.oa)
print('SA:', model.sa)
print('LA:', model.la)
print('PA:', model.pa)
print('EPBS:', model.epbs)
"
```

Expected: Model loads without error, all 5 layers accessible.

- [ ] **Step 3: Commit**

```bash
git add src/core/templates/
git commit -m "feat: add blank Capella project template for export"
```

---

### Task 2: Implement capella_export.py — OA layer mapping

**Files:**
- Create: `src/core/capella_export.py`

Start with the OA layer since it's the most straightforward mapping.

- [ ] **Step 1: Create the export module with OA mapping**

```python
"""Export Shipyard models to native Capella format."""
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

import capellambse

from src.core.models.core import ProjectModel

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _copy_template(dest_dir: Path, project_name: str) -> Path:
    """Copy blank template to dest_dir and rename files."""
    proj_dir = dest_dir / project_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Copy .capella file with project name
    src_capella = _TEMPLATE_DIR / "blank.capella"
    dst_capella = proj_dir / f"{project_name}.capella"
    shutil.copy2(src_capella, dst_capella)

    # Create .project with correct name
    project_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
  <name>{project_name}</name>
  <comment></comment>
  <projects></projects>
  <buildSpec></buildSpec>
  <natures></natures>
</projectDescription>"""
    (proj_dir / ".project").write_text(project_xml, encoding="utf-8")

    return proj_dir


def _populate_oa(model: capellambse.MelodyModel, layer_data: dict) -> None:
    """Populate Operational Analysis layer."""
    entities = layer_data.get("entities", [])
    capabilities = layer_data.get("capabilities", [])
    activities = layer_data.get("activities", [])

    for ent in entities:
        try:
            model.oa.entity_pkg.entities.create(name=ent.get("name", ent.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create OA entity '{ent.get('id')}': {exc}")

    for cap in capabilities:
        try:
            model.oa.capability_pkg.capabilities.create(name=cap.get("name", cap.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create OA capability '{cap.get('id')}': {exc}")

    for act in activities:
        try:
            # Activities are functions in Capella OA
            model.oa.function_pkg.functions.create(name=act.get("name", act.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create OA activity '{act.get('id')}': {exc}")

    logger.info(f"OA: {len(entities)} entities, {len(capabilities)} capabilities, {len(activities)} activities")


def export_capella_project(project: ProjectModel, output_path: Path) -> Path:
    """Export as a complete Capella project (zipped folder)."""
    project_name = (project.project.name or "shipyard-export").replace(" ", "-").lower()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proj_dir = _copy_template(tmp_path, project_name)

        # Load with capellambse
        model = capellambse.MelodyModel(str(proj_dir))
        model.name = project.project.name or "Shipyard Export"

        # Populate layers
        layers = project.layers or {}
        if "operational_analysis" in layers:
            _populate_oa(model, layers["operational_analysis"])

        model.save()

        # Zip the project folder
        zip_path = output_path / f"{project_name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in proj_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(tmp_path))

        return zip_path


def export_capella_fragment(project: ProjectModel, output_path: Path) -> Path:
    """Export as a single .capella fragment file."""
    project_name = (project.project.name or "shipyard-export").replace(" ", "-").lower()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proj_dir = _copy_template(tmp_path, project_name)

        model = capellambse.MelodyModel(str(proj_dir))
        model.name = project.project.name or "Shipyard Export"

        layers = project.layers or {}
        if "operational_analysis" in layers:
            _populate_oa(model, layers["operational_analysis"])

        model.save()

        # Return just the .capella file
        capella_file = proj_dir / f"{project_name}.capella"
        dest = output_path / f"{project_name}.capella"
        shutil.copy2(capella_file, dest)
        return dest
```

- [ ] **Step 2: Test OA export manually**

```bash
python3 -c "
from pathlib import Path
from src.core.capella_export import export_capella_project
from src.core.project import load_project

project = load_project('untitled-project')
if project and project.layers.get('operational_analysis'):
    result = export_capella_project(project, Path('/tmp'))
    print(f'Exported to: {result} ({result.stat().st_size} bytes)')
else:
    print('No OA layer data to test with')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/core/capella_export.py
git commit -m "feat: capella export module with OA layer mapping"
```

---

### Task 3: Add SA, LA, PA, EPBS layer mappings

**Files:**
- Modify: `src/core/capella_export.py`

- [ ] **Step 1: Add SA layer mapping**

Add to `capella_export.py`:

```python
def _populate_sa(model: capellambse.MelodyModel, layer_data: dict) -> None:
    """Populate System Analysis layer."""
    functions = layer_data.get("functions", [])
    actors = layer_data.get("external_actors", [])

    for func in functions:
        try:
            model.sa.function_pkg.functions.create(name=func.get("name", func.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create SA function '{func.get('id')}': {exc}")

    for actor in actors:
        try:
            model.sa.component_pkg.components.create(
                name=actor.get("name", actor.get("id", "Unknown")),
                is_actor=True,
            )
        except Exception as exc:
            logger.warning(f"Failed to create SA actor '{actor.get('id')}': {exc}")

    logger.info(f"SA: {len(functions)} functions, {len(actors)} actors")
```

- [ ] **Step 2: Add LA layer mapping**

```python
def _populate_la(model: capellambse.MelodyModel, layer_data: dict) -> None:
    """Populate Logical Architecture layer."""
    components = layer_data.get("components", [])
    functions = layer_data.get("functions", [])

    for comp in components:
        try:
            model.la.component_pkg.components.create(name=comp.get("name", comp.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create LA component '{comp.get('id')}': {exc}")

    for func in functions:
        try:
            model.la.function_pkg.functions.create(name=func.get("name", func.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create LA function '{func.get('id')}': {exc}")

    logger.info(f"LA: {len(components)} components, {len(functions)} functions")
```

- [ ] **Step 3: Add PA layer mapping**

```python
def _populate_pa(model: capellambse.MelodyModel, layer_data: dict) -> None:
    """Populate Physical Architecture layer."""
    components = layer_data.get("components", [])
    functions = layer_data.get("functions", [])
    links = layer_data.get("links", [])

    for comp in components:
        try:
            model.pa.component_pkg.components.create(name=comp.get("name", comp.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create PA component '{comp.get('id')}': {exc}")

    for func in functions:
        try:
            model.pa.function_pkg.functions.create(name=func.get("name", func.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create PA function '{func.get('id')}': {exc}")

    logger.info(f"PA: {len(components)} components, {len(functions)} functions, {len(links)} links")
```

- [ ] **Step 4: Add EPBS layer mapping**

```python
def _populate_epbs(model: capellambse.MelodyModel, layer_data: dict) -> None:
    """Populate EPBS layer."""
    cis = layer_data.get("configuration_items", [])

    for ci in cis:
        try:
            model.epbs.component_pkg.components.create(name=ci.get("name", ci.get("id", "Unknown")))
        except Exception as exc:
            logger.warning(f"Failed to create EPBS CI '{ci.get('id')}': {exc}")

    logger.info(f"EPBS: {len(cis)} configuration items")
```

- [ ] **Step 5: Wire all layers into export functions**

Update both `export_capella_project` and `export_capella_fragment` to call all populate functions:

```python
        # In both export functions, replace the single OA call with:
        if "operational_analysis" in layers:
            _populate_oa(model, layers["operational_analysis"])
        if "system_needs_analysis" in layers:
            _populate_sa(model, layers["system_needs_analysis"])
        if "logical_architecture" in layers:
            _populate_la(model, layers["logical_architecture"])
        if "physical_architecture" in layers:
            _populate_pa(model, layers["physical_architecture"])
        if "epbs" in layers:
            _populate_epbs(model, layers["epbs"])
```

- [ ] **Step 6: Test with full model**

```bash
python3 -c "
from pathlib import Path
from src.core.capella_export import export_capella_project
from src.core.project import load_project

project = load_project('untitled-project')
if project and project.layers:
    print('Layers:', list(project.layers.keys()))
    result = export_capella_project(project, Path('/tmp'))
    print(f'Exported to: {result} ({result.stat().st_size} bytes)')

    # Verify by loading the exported model
    import zipfile, tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(result) as zf:
            zf.extractall(tmp)
        import capellambse, os
        for d in os.listdir(tmp):
            model = capellambse.MelodyModel(os.path.join(tmp, d))
            print(f'Verified: {model.name}')
            print(f'  SA functions: {len(model.sa.all_functions)}')
            print(f'  LA components: {len(model.la.all_components)}')
            print(f'  PA components: {len(model.pa.all_components)}')
"
```

- [ ] **Step 7: Commit**

```bash
git add src/core/capella_export.py
git commit -m "feat: add SA, LA, PA, EPBS layer mappings to Capella export"
```

---

### Task 4: Add backend endpoint

**Files:**
- Modify: `src/web/app.py`

- [ ] **Step 1: Add the export endpoint**

Add after the existing `/export/model/{fmt}` endpoint in `app.py`:

```python
@app.get("/export/model/capella")
async def export_capella(mode: str = "project"):
    """Export MBSE model as native Capella project."""
    project = _require_project()

    if not project.layers:
        raise HTTPException(400, "No model layers to export")

    if project.project.mode != "capella":
        raise HTTPException(400, "Capella export only available for Capella-mode projects")

    from src.core.capella_export import export_capella_project, export_capella_fragment

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            if mode == "fragment":
                result = export_capella_fragment(project, tmp_path)
                media_type = "application/xml"
                filename = result.name
            else:
                result = export_capella_project(project, tmp_path)
                media_type = "application/zip"
                filename = result.name

            return FileResponse(
                result,
                filename=filename,
                media_type=media_type,
            )
        except ImportError:
            raise HTTPException(500, "capellambse is not installed. Run: pip install capellambse")
        except Exception as exc:
            logger.error(f"Capella export failed: {exc}")
            raise HTTPException(500, f"Export failed: {exc}")
```

Add `import tempfile` to the top of app.py if not already present.

- [ ] **Step 2: Test the endpoint**

```bash
# Start server if not running
curl -s -o /tmp/test-capella.zip http://127.0.0.1:8000/export/model/capella
ls -la /tmp/test-capella.zip
unzip -l /tmp/test-capella.zip
```

- [ ] **Step 3: Commit**

```bash
git add src/web/app.py
git commit -m "feat: add GET /export/model/capella endpoint"
```

---

### Task 5: Add frontend buttons

**Files:**
- Modify: `src/web/templates/index.html`
- Modify: `src/web/static/app.js`

- [ ] **Step 1: Add export buttons to the dropdown menu**

In `index.html`, add after the "Export Text" button inside `#export-menu`:

```html
<div class="export-divider" id="capella-export-divider" style="display:none"></div>
<button id="capella-project-btn" style="display:none" onclick="exportCapella('project')">Export Capella Project</button>
<button id="capella-fragment-btn" style="display:none" onclick="exportCapella('fragment')">Export Capella Fragment</button>
```

- [ ] **Step 2: Add exportCapella function and visibility toggle**

In `app.js`, add near the existing `exportProject` function:

```javascript
function exportCapella(mode) {
    window.open('/export/model/capella?mode=' + mode, '_blank');
    $('export-menu').classList.add('hidden');
}

function updateCapellaExportVisibility() {
    var show = selectedToolMode === 'capella';
    var divider = $('capella-export-divider');
    var projBtn = $('capella-project-btn');
    var fragBtn = $('capella-fragment-btn');
    if (divider) divider.style.display = show ? '' : 'none';
    if (projBtn) projBtn.style.display = show ? '' : 'none';
    if (fragBtn) fragBtn.style.display = show ? '' : 'none';
}
```

Call `updateCapellaExportVisibility()` from `applyToolMode()` after `selectedToolMode` is set, and from `DOMContentLoaded` after init.

- [ ] **Step 3: Test in browser**

1. Open Shipyard in Capella mode
2. Click Export dropdown — should show "Export Capella Project" and "Export Capella Fragment"
3. Switch to Rhapsody mode — Capella buttons should disappear
4. Switch back to Capella — buttons reappear
5. Click "Export Capella Project" — should download a zip file

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html src/web/static/app.js
git commit -m "feat: add Capella export buttons to export dropdown"
```

---

### Task 6: Add capellambse to dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependency**

Add `"capellambse>=0.8.0"` to the dependencies list in `pyproject.toml`.

- [ ] **Step 2: Reinstall**

```bash
pip install -e .
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add capellambse dependency for Capella native export"
```

---

### Task 7: End-to-end test and version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: Full end-to-end test**

1. Start server: `shipyard --web`
2. Create or load a Capella project with model data
3. Click Export → Export Capella Project
4. Download the zip
5. Unzip and verify with capellambse:

```bash
python3 -c "
import capellambse, sys
model = capellambse.MelodyModel(sys.argv[1])
print(f'Model: {model.name}')
print(f'OA entities: {len(model.oa.all_entities)}')
print(f'SA functions: {len(model.sa.all_functions)}')
print(f'LA components: {len(model.la.all_components)}')
print(f'PA components: {len(model.pa.all_components)}')
" /path/to/unzipped/project
```

6. Click Export → Export Capella Fragment
7. Verify the .capella file downloaded

- [ ] **Step 2: Bump version**

Update version to next patch in both `pyproject.toml` and `index.html`.

- [ ] **Step 3: Commit and push**

```bash
git add -A
git commit -m "v1.6.0: Capella native export"
git push
```
