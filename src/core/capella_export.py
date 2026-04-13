"""Capella model export via capellambse.

Copies a blank Capella template, populates it with data from
project.layers, and produces either a zipped project or a standalone
.capella fragment.
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid as uuid_mod
import zipfile
from pathlib import Path
from typing import Any

import capellambse
from lxml import etree

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Layer key aliases — the project may use slightly different names.
_OA_KEYS = {"operational_analysis"}
_SA_KEYS = {"system_needs_analysis", "system_analysis"}
_LA_KEYS = {"logical_architecture"}
_PA_KEYS = {"physical_architecture"}
_EPBS_KEYS = {"epbs"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_name(item: dict) -> str:
    """Extract a display name from a layer element dict."""
    return item.get("name", item.get("id", "Unknown"))


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "export"


# ---------------------------------------------------------------------------
# Template handling
# ---------------------------------------------------------------------------

def _copy_template(dest_dir: Path, project_name: str) -> Path:
    """Copy blank template files to *dest_dir*/<slug>/, renaming to match
    the project name.  Returns the project directory path."""
    slug = _slugify(project_name)
    proj_dir = dest_dir / slug
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Copy and rename the three model files
    for ext in (".capella", ".aird", ".afm"):
        src = _TEMPLATE_DIR / f"blank{ext}"
        if src.exists():
            shutil.copy2(src, proj_dir / f"blank{ext}")

    # Copy .project and patch the <name> tag
    dot_project_src = _TEMPLATE_DIR / ".project"
    if dot_project_src.exists():
        content = dot_project_src.read_text(encoding="utf-8")
        content = content.replace(
            "<name>shipyard-export</name>",
            f"<name>{project_name}</name>",
        )
        (proj_dir / ".project").write_text(content, encoding="utf-8")

    return proj_dir


# ---------------------------------------------------------------------------
# Layer populators
# ---------------------------------------------------------------------------

def _populate_oa(model: capellambse.MelodyModel, layer_data: dict[str, Any]) -> None:
    """Create Operational Analysis elements: entities, capabilities, activities."""
    # Entities
    for item in layer_data.get("entities", []):
        try:
            model.oa.entity_pkg.entities.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("OA entity creation failed for %r: %s", item, exc)

    # Capabilities
    for item in layer_data.get("capabilities", []):
        try:
            model.oa.capability_pkg.capabilities.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("OA capability creation failed for %r: %s", item, exc)

    # Activities (stored as OperationalActivities in Capella)
    for item in layer_data.get("activities", []):
        try:
            model.oa.function_pkg.activities.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("OA activity creation failed for %r: %s", item, exc)


def _populate_sa(model: capellambse.MelodyModel, layer_data: dict[str, Any]) -> None:
    """Create System Needs Analysis elements: functions, external actors."""
    # Functions
    for item in layer_data.get("functions", []):
        try:
            model.sa.function_pkg.functions.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("SA function creation failed for %r: %s", item, exc)

    # External actors (components with is_actor=True)
    for item in layer_data.get("external_actors", []):
        try:
            model.sa.component_pkg.components.create(
                name=_item_name(item), is_actor=True,
            )
        except Exception as exc:
            logger.warning("SA actor creation failed for %r: %s", item, exc)


def _populate_la(model: capellambse.MelodyModel, layer_data: dict[str, Any]) -> None:
    """Create Logical Architecture elements: components, functions."""
    # Components
    for item in layer_data.get("components", []):
        try:
            model.la.component_pkg.components.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("LA component creation failed for %r: %s", item, exc)

    # Functions
    for item in layer_data.get("functions", []):
        try:
            model.la.function_pkg.functions.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("LA function creation failed for %r: %s", item, exc)


def _populate_pa(model: capellambse.MelodyModel, layer_data: dict[str, Any]) -> None:
    """Create Physical Architecture elements: components, functions."""
    # Components
    for item in layer_data.get("components", []):
        try:
            model.pa.component_pkg.components.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("PA component creation failed for %r: %s", item, exc)

    # Functions
    for item in layer_data.get("functions", []):
        try:
            model.pa.function_pkg.functions.create(name=_item_name(item))
        except Exception as exc:
            logger.warning("PA function creation failed for %r: %s", item, exc)


def _populate_epbs(model: capellambse.MelodyModel, layer_data: dict[str, Any]) -> None:
    """Create EPBS configuration items.

    capellambse 0.8.x does not support ``configuration_items.create()``
    because ConfigurationItem has no xmltag.  We fall back to direct XML
    element construction which works correctly and round-trips through
    model.save() / reload.
    """
    ci_pkg_elem = model.epbs.configuration_item_pkg._element

    for item in layer_data.get("configuration_items", []):
        try:
            name = _item_name(item)
            ci_elem = etree.SubElement(ci_pkg_elem, "ownedConfigurationItems")
            ci_elem.set(
                "{http://www.w3.org/2001/XMLSchema-instance}type",
                "org.polarsys.capella.core.data.epbs:ConfigurationItem",
            )
            ci_elem.set("id", str(uuid_mod.uuid4()))
            ci_elem.set("name", name)
            model._loader.idcache_index(ci_elem)
        except Exception as exc:
            logger.warning("EPBS CI creation failed for %r: %s", item, exc)

    # Also handle pbs_structure items as CIs
    for item in layer_data.get("pbs_structure", []):
        try:
            name = _item_name(item)
            ci_elem = etree.SubElement(ci_pkg_elem, "ownedConfigurationItems")
            ci_elem.set(
                "{http://www.w3.org/2001/XMLSchema-instance}type",
                "org.polarsys.capella.core.data.epbs:ConfigurationItem",
            )
            ci_elem.set("id", str(uuid_mod.uuid4()))
            ci_elem.set("name", name)
            model._loader.idcache_index(ci_elem)
        except Exception as exc:
            logger.warning("EPBS pbs_structure CI creation failed for %r: %s", item, exc)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_LAYER_HANDLERS: dict[str, Any] = {}
for _keys, _handler in [
    (_OA_KEYS, _populate_oa),
    (_SA_KEYS, _populate_sa),
    (_LA_KEYS, _populate_la),
    (_PA_KEYS, _populate_pa),
    (_EPBS_KEYS, _populate_epbs),
]:
    for _k in _keys:
        _LAYER_HANDLERS[_k] = _handler


def _populate_model(
    model: capellambse.MelodyModel,
    layers: dict[str, Any],
) -> None:
    """Dispatch each project layer to the appropriate populator."""
    for layer_key, layer_data in layers.items():
        handler = _LAYER_HANDLERS.get(layer_key)
        if handler is None:
            logger.info("No Capella handler for layer %r — skipping", layer_key)
            continue
        if not isinstance(layer_data, dict):
            logger.warning("Layer %r data is not a dict — skipping", layer_key)
            continue
        logger.info("Populating Capella layer: %s", layer_key)
        handler(model, layer_data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_capella_project(project: Any, output_path: Path) -> Path:
    """Export *project* as a zipped Capella project.

    Parameters
    ----------
    project : ProjectModel
        A loaded project with a ``layers`` dict.
    output_path : Path
        Directory where the .zip will be written.

    Returns
    -------
    Path
        Path to the created zip file.
    """
    project_name = getattr(
        getattr(project, "project", None), "name", "Shipyard Export"
    )
    slug = _slugify(project_name)
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Copy template
    proj_dir = _copy_template(output_path, project_name)

    # 2. Load with capellambse (use the .aird entry point)
    aird_path = proj_dir / "blank.aird"
    model = capellambse.MelodyModel(str(aird_path))

    # 3. Populate layers
    layers = getattr(project, "layers", {}) or {}
    _populate_model(model, layers)

    # 4. Save
    model.save()

    # 5. Zip the project directory
    zip_path = output_path / f"{slug}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in proj_dir.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=f"{slug}/{file.relative_to(proj_dir)}")

    logger.info("Capella project exported to %s", zip_path)
    return zip_path


def export_capella_fragment(project: Any, output_path: Path) -> Path:
    """Export *project* as a standalone .capella file.

    Parameters
    ----------
    project : ProjectModel
        A loaded project with a ``layers`` dict.
    output_path : Path
        Directory where the .capella file will be written.

    Returns
    -------
    Path
        Path to the created .capella file.
    """
    project_name = getattr(
        getattr(project, "project", None), "name", "Shipyard Export"
    )
    slug = _slugify(project_name)
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Copy template to a temporary working directory
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        proj_dir = _copy_template(Path(tmpdir), project_name)

        # 2. Load with capellambse
        aird_path = proj_dir / "blank.aird"
        model = capellambse.MelodyModel(str(aird_path))

        # 3. Populate layers
        layers = getattr(project, "layers", {}) or {}
        _populate_model(model, layers)

        # 4. Save
        model.save()

        # 5. Copy out just the .capella file
        capella_src = proj_dir / "blank.capella"
        capella_dest = output_path / f"{slug}.capella"
        shutil.copy2(capella_src, capella_dest)

    logger.info("Capella fragment exported to %s", capella_dest)
    return capella_dest
