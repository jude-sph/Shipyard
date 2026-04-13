"""FastAPI web backend for the Shipyard MBSE System."""
import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.core import config
from src.core.config import (
    MODEL_CATALOGUE, MODEL_PRICING, DECOMPOSE_MODEL, MBSE_MODEL,
    CAPELLA_LAYERS, RHAPSODY_DIAGRAMS,
)
from src.core.models.core import ProjectModel, Requirement, SourceFile
from src.core.models.decompose import RequirementTree
from src.core.project import (
    new_project,
    save_project,
    load_project,
    list_projects,
    delete_project,
    push_undo,
    pop_undo,
    pop_redo,
)

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent

app = FastAPI(title="Shipyard")

# Mount static files — create directory if missing so mount always works
_static_dir = WEB_DIR / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Jinja2 templates
_templates_dir = WEB_DIR / "templates"
templates = Jinja2Templates(directory=_templates_dir) if _templates_dir.exists() else None


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

@dataclass
class Job:
    id: str
    status: str = "pending"  # pending, running, complete, failed, cancelled
    job_type: str = "model"  # "decompose" or "model"
    settings: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    cancelled: bool = False
    task: asyncio.Task | None = None

    def emit(self, event: dict):
        self.events.append(event)


current_project: ProjectModel | None = None
current_project_name: str | None = None
jobs: dict[str, Job] = {}
_active_job_id: str | None = None

# Auto-load if there's a saved project
_projects = list_projects()
if _projects:
    # Load the most recently modified project
    _projects.sort(key=lambda p: p.get("modified", ""), reverse=True)
    _slug = Path(_projects[0]["path"]).parent.name
    current_project = load_project(_slug)
    if current_project:
        current_project_name = current_project.project.name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_config():
    """Reload config from .env after settings change."""
    from dotenv import load_dotenv
    env_path = config.PACKAGE_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
    cwd_env = config.CWD / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env, override=True)
    config.PROVIDER = os.getenv("PROVIDER", "anthropic")
    config.MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
    config.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    config.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    config.DECOMPOSE_MODEL = os.getenv("DECOMPOSE_MODEL", "claude-sonnet-4-6")
    config.MBSE_MODEL = os.getenv("MBSE_MODEL", "claude-sonnet-4-6")
    config.LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434")


def _require_project() -> ProjectModel:
    """Return current_project or raise 404."""
    if current_project is None:
        raise HTTPException(404, "No active project. Create or select a project first.")
    return current_project


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@app.get("/")
async def index(request: Request):
    """Root endpoint. Renders the SPA shell or returns JSON status."""
    if templates is not None:
        try:
            project_data = (
                json.loads(current_project.model_dump_json())
                if current_project else None
            )
            settings_data = {
                "provider": config.PROVIDER,
                "model": config.MODEL,
                "decompose_model": config.DECOMPOSE_MODEL,
                "mbse_model": config.MBSE_MODEL,
                "default_mode": config.DEFAULT_MODE,
                "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
                "has_openrouter_key": bool(config.OPENROUTER_API_KEY),
                "local_url": config.LOCAL_LLM_URL,
                "auto_send": True,
            }
            return templates.TemplateResponse(request, "index.html", {
                "model_catalogue": json.dumps(MODEL_CATALOGUE),
                "capella_layers": json.dumps(CAPELLA_LAYERS),
                "rhapsody_diagrams": json.dumps(RHAPSODY_DIAGRAMS),
                "settings": json.dumps(settings_data),
                "project": json.dumps(project_data),
            })
        except Exception as exc:
            logger.warning(f"Template rendering failed: {exc}")  # Fall through to JSON fallback
    return {
        "app": "Shipyard",
        "status": "running",
        "has_project": current_project is not None,
        "project_name": current_project_name,
    }


# ---------------------------------------------------------------------------
# Project routes
# ---------------------------------------------------------------------------

@app.get("/project/list")
async def project_list():
    """List all saved projects."""
    return list_projects()


@app.post("/project/new")
async def create_project(request: Request):
    """Create a new project and set it as current."""
    global current_project, current_project_name
    body = await request.json()
    name = body.get("name", "Untitled Project")
    mode = body.get("mode", config.DEFAULT_MODE)

    project = new_project(mode=mode, name=name)
    save_project(project)

    current_project = project
    current_project_name = name

    return json.loads(project.model_dump_json())


@app.get("/project")
async def get_project():
    """Get current project state."""
    project = _require_project()
    return json.loads(project.model_dump_json())


@app.post("/project/select/{project_id}")
async def select_project(project_id: str):
    """Switch to a different project by slug."""
    global current_project, current_project_name
    project = load_project(project_id)
    if project is None:
        raise HTTPException(404, f"Project '{project_id}' not found")
    current_project = project
    current_project_name = project.project.name
    return json.loads(project.model_dump_json())


@app.post("/project/save")
async def save_current_project():
    """Explicit save of the current project."""
    project = _require_project()
    save_project(project)
    return {"status": "ok"}


@app.post("/project/rename")
async def rename_project(request: Request):
    """Rename the current project."""
    global current_project, current_project_name
    project = _require_project()
    body = await request.json()
    new_name = body.get("new_name", project.project.name)

    old_name = project.project.name
    project.project.name = new_name
    save_project(project)
    current_project_name = new_name

    # Clean up old directory if name changed (slug changed)
    if old_name != new_name:
        delete_project(old_name)

    return {"name": new_name}


@app.post("/project/delete/{project_id}")
async def delete_project_route(project_id: str):
    """Delete a project by slug."""
    global current_project, current_project_name
    deleted = delete_project(project_id)
    if not deleted:
        raise HTTPException(404, f"Project '{project_id}' not found")
    # If we deleted the current project, clear it
    if current_project is not None:
        from src.core.project import _slugify as project_slugify
        if project_slugify(current_project.project.name) == project_id:
            current_project = None
            current_project_name = None
    return {"status": "deleted", "project_id": project_id}


@app.get("/project/download")
async def download_project():
    """Download the current project as a JSON file."""
    project = _require_project()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".json", mode="w", encoding="utf-8"
    ) as tmp:
        data = json.loads(project.model_dump_json())
        json.dump(data, tmp, indent=2, default=str)
        tmp_path = Path(tmp.name)

    project_name = project.project.name or "project"
    filename = project_name.lower().replace(" ", "-") + ".json"
    return FileResponse(tmp_path, filename=filename, media_type="application/json")


@app.post("/project/import")
async def import_project(file: UploadFile = File(...)):
    """Import a project from an uploaded JSON file."""
    global current_project, current_project_name

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Please upload a .json project file")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        raw = tmp_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        project = ProjectModel.model_validate(data)
        save_project(project)
        current_project = project
        current_project_name = project.project.name
        return json.loads(project.model_dump_json())
    except Exception as exc:
        raise HTTPException(400, f"Failed to import project: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/project/undo")
async def undo():
    """Undo the last mutation on the current project."""
    global current_project
    project = _require_project()
    restored = pop_undo(project)
    if restored is None:
        raise HTTPException(400, "Nothing to undo")
    current_project = restored
    save_project(current_project)
    return json.loads(current_project.model_dump_json())


@app.post("/project/redo")
async def redo():
    """Redo the last undone mutation on the current project."""
    global current_project
    project = _require_project()
    restored = pop_redo(project)
    if restored is None:
        raise HTTPException(400, "Nothing to redo")
    current_project = restored
    save_project(current_project)
    return json.loads(current_project.model_dump_json())


@app.get("/project/batches")
async def get_batches(type: str | None = None):
    """List batches for the current project, optionally filtered by type."""
    project = _require_project()
    batches = [b.model_dump() for b in project.batches]
    if type:
        batches = [b for b in batches if b.get("batch_type") == type]
    return batches


# ---------------------------------------------------------------------------
# Settings routes
# ---------------------------------------------------------------------------

@app.get("/settings")
async def get_settings():
    """Get current configuration."""
    return {
        "provider": config.PROVIDER,
        "model": config.MODEL,
        "decompose_model": config.DECOMPOSE_MODEL,
        "mbse_model": config.MBSE_MODEL,
        "default_mode": config.DEFAULT_MODE,
        "has_anthropic_key": bool(config.ANTHROPIC_API_KEY),
        "has_openrouter_key": bool(config.OPENROUTER_API_KEY),
    }


@app.post("/settings")
async def update_settings(request: Request):
    """Update API keys, provider — write to .env file."""
    body = await request.json()
    # Write to CWD .env (takes precedence), fall back to package root
    env_path = config.CWD / ".env" if (config.CWD / ".env").exists() else config.PACKAGE_ROOT / ".env"

    from src.core.llm_client import _provider_for_model

    decompose_model = body.get('decompose_model', config.DECOMPOSE_MODEL)
    mbse_model = body.get('mbse_model', config.MBSE_MODEL)
    provider = body.get('provider', _provider_for_model(mbse_model))

    lines = [
        "# Shipyard Configuration",
        f"PROVIDER={provider}",
        f"MODEL={body.get('model', mbse_model)}",
        f"DEFAULT_MODE={body.get('default_mode', config.DEFAULT_MODE)}",
        f"DECOMPOSE_MODEL={decompose_model}",
        f"MBSE_MODEL={mbse_model}",
        f"LOCAL_LLM_URL={body.get('local_url', config.LOCAL_LLM_URL)}",
        "",
    ]
    ak = body.get("anthropic_key", "").strip() or config.ANTHROPIC_API_KEY
    if ak:
        lines.append(f"ANTHROPIC_API_KEY={ak}")
    ork = body.get("openrouter_key", "").strip() or config.OPENROUTER_API_KEY
    if ork:
        lines.append(f"OPENROUTER_API_KEY={ork}")
    lines.append("")
    env_path.write_text("\n".join(lines), encoding="utf-8")
    _reload_config()

    # Sync per-project model settings with global settings
    if current_project:
        if body.get('mbse_model'):
            current_project.model_settings.model = mbse_model
        if body.get('decompose_model'):
            current_project.decomposition_settings.model = decompose_model
        save_project(current_project)

    return {
        "status": "ok",
        "provider": config.PROVIDER,
        "model": config.MODEL,
        "default_mode": config.DEFAULT_MODE,
    }


@app.get("/settings/models")
async def list_models():
    """Return the MODEL_CATALOGUE."""
    return MODEL_CATALOGUE


@app.post("/settings/auto-send")
async def toggle_auto_send(request: Request):
    """Toggle auto_send on the current project."""
    global current_project
    project = _require_project()
    body = await request.json()
    enabled = body.get("auto_send", body.get("enabled", True))

    push_undo(project)
    project.auto_send = enabled
    save_project(project)
    current_project = project

    return {"auto_send": project.auto_send}


@app.get("/settings/cost-history")
async def cost_history():
    """Return cost breakdown grouped by pipeline (decompose vs model)."""
    project = current_project
    zeros = {
        "decompose": {"total_cost": 0.0, "api_calls": 0},
        "model": {"total_cost": 0.0, "api_calls": 0},
        "total": {"total_cost": 0.0, "api_calls": 0},
    }
    if project is None or not project.batches:
        return zeros

    breakdown: dict = {
        "decompose": {"total_cost": 0.0, "api_calls": 0},
        "model": {"total_cost": 0.0, "api_calls": 0},
    }

    for batch in project.batches:
        bt = batch.batch_type if batch.batch_type in ("decompose", "model") else "model"
        breakdown[bt]["total_cost"] += batch.cost
        breakdown[bt]["api_calls"] += 1

    decompose_cost = round(breakdown["decompose"]["total_cost"], 6)
    model_cost = round(breakdown["model"]["total_cost"], 6)
    decompose_calls = breakdown["decompose"]["api_calls"]
    model_calls = breakdown["model"]["api_calls"]

    return {
        "decompose": {"total_cost": decompose_cost, "api_calls": decompose_calls},
        "model": {"total_cost": model_cost, "api_calls": model_calls},
        "total": {
            "total_cost": round(decompose_cost + model_cost, 6),
            "api_calls": decompose_calls + model_calls,
        },
    }


@app.get("/settings/check-updates")
async def check_updates():
    """Git-based update check."""
    import subprocess
    pkg_root = str(config.PACKAGE_ROOT.parent)
    try:
        git_check = subprocess.run(
            ["git", "--version"], capture_output=True, text=True
        )
        if git_check.returncode != 0:
            return {"behind": 0, "available": False, "error": "Git is not installed"}

        is_repo = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=pkg_root,
        )
        if is_repo.returncode != 0:
            return {
                "behind": 0,
                "available": False,
                "error": "Not a git repository.",
            }

        remote = subprocess.run(
            ["git", "remote"], capture_output=True, text=True, cwd=pkg_root,
        )
        if not remote.stdout.strip():
            return {
                "behind": 0,
                "available": False,
                "error": "No git remote configured.",
            }

        fetch = subprocess.run(
            ["git", "fetch", "--quiet"],
            capture_output=True, text=True, cwd=pkg_root, timeout=15,
        )
        if fetch.returncode != 0:
            return {
                "behind": 0,
                "available": False,
                "error": "Could not reach remote.",
            }

        result = subprocess.run(
            ["git", "rev-list", "HEAD..@{u}", "--count"],
            capture_output=True, text=True, cwd=pkg_root, timeout=10,
        )
        if result.returncode != 0:
            return {
                "behind": 0,
                "available": False,
                "error": "No upstream branch set.",
            }

        behind = int(result.stdout.strip())
        commits = []
        if behind > 0:
            log = subprocess.run(
                ["git", "log", "HEAD..@{u}", "--pretty=format:%s"],
                capture_output=True, text=True, cwd=pkg_root, timeout=10,
            )
            if log.returncode == 0 and log.stdout.strip():
                commits = [
                    line
                    for line in log.stdout.strip().splitlines()
                    if line.strip()
                ]
        return {"behind": behind, "available": behind > 0, "commits": commits}
    except Exception as exc:
        return {"behind": 0, "available": False, "error": str(exc)}


@app.post("/settings/update")
async def update_software():
    """Git pull + pip install."""
    import subprocess
    # Use repo root (parent of src/) for both git and pip
    repo_root = str(config.PACKAGE_ROOT.parent)
    try:
        pull = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True,
            cwd=repo_root, timeout=30,
        )
        if pull.returncode != 0:
            return {
                "status": "error",
                "message": "Git pull failed: " + pull.stderr.strip(),
            }

        if "Already up to date" in pull.stdout:
            return {
                "status": "ok",
                "message": "Already up to date.",
                "updated": False,
            }

        logger.info(f"Running pip install with: {sys.executable} in {repo_root}")
        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True, text=True,
            cwd=repo_root, timeout=60,
        )
        logger.info(f"pip install returncode: {pip_result.returncode}")
        if pip_result.stdout:
            logger.info(f"pip stdout: {pip_result.stdout[-500:]}")
        if pip_result.stderr:
            logger.warning(f"pip stderr: {pip_result.stderr[-500:]}")
        if pip_result.returncode != 0:
            logger.warning(f"pip install failed: {pip_result.stderr}")
            return {
                "status": "ok",
                "message": "Code updated but pip install failed. Run 'pip install -e .' manually, then restart.",
                "updated": True,
                "details": pip_result.stderr.strip(),
            }

        return {
            "status": "ok",
            "message": "Updated! Restart the server to apply changes.",
            "updated": True,
            "details": pull.stdout.strip(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Decompose helpers
# ---------------------------------------------------------------------------

def _flatten_tree_to_requirements(tree: RequirementTree) -> list[Requirement]:
    """Flatten a decomposition tree to a flat list of Requirements."""
    reqs = []

    def _walk(node, dig_id, path=""):
        node_path = f"{path}.{node.level}" if path else f"L{node.level}"
        req_id = f"{dig_id}-{node_path}"
        reqs.append(Requirement(id=req_id, text=node.technical_requirement, source_dig=dig_id))
        for i, child in enumerate(node.children, 1):
            _walk(child, dig_id, f"{node_path}.{i}")

    if tree.root:
        _walk(tree.root, tree.dig_id)
    return reqs


def _sync_modeling_queue(project):
    """Update modeling queue and flat requirements list from decomposition trees."""
    if not project.auto_send:
        return
    all_reqs = []
    for dig_id, tree_data in project.decomposition_trees.items():
        tree = RequirementTree.model_validate(tree_data) if isinstance(tree_data, dict) else tree_data
        all_reqs.extend(_flatten_tree_to_requirements(tree))
    # Update requirements list with decomposed reqs (keep any direct uploads)
    decomp_ids = {r.id for r in all_reqs}
    existing_direct = [r for r in project.requirements if r.id not in decomp_ids]
    project.requirements = existing_direct + all_reqs
    project.modeling_queue = [r.id for r in all_reqs]


def _detect_orphaned_links(project):
    """Find links whose source and target both don't exist in requirements or elements."""
    req_ids = {r.id for r in project.requirements}
    element_ids = set()
    for layer_data in project.layers.values():
        if isinstance(layer_data, dict):
            for collection in layer_data.values():
                if isinstance(collection, list):
                    for elem in collection:
                        if isinstance(elem, dict) and "id" in elem:
                            element_ids.add(elem["id"])
    valid_ids = req_ids | element_ids
    return [l for l in project.links if l.source not in valid_ids and l.target not in valid_ids]


# ---------------------------------------------------------------------------
# Decompose routes
# ---------------------------------------------------------------------------

@app.post("/decompose/upload")
async def decompose_upload(file: UploadFile = File(...)):
    """Upload GTR-SDS.xlsx or additional source file."""
    global current_project
    project = _require_project()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    from src.core.project import _slugify as project_slugify
    slug = project_slugify(project.project.name)
    uploads_dir = config.PROJECTS_DIR / slug / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    dest = uploads_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Compute SHA-256
    import hashlib
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()

    # Load workbook data
    from src.decompose.loader import load_workbook_data
    try:
        wb_data = load_workbook_data(dest)
    except Exception as exc:
        raise HTTPException(400, f"Failed to load workbook: {exc}")

    # Store reference data in project
    import dataclasses
    project.reference_data = dataclasses.asdict(wb_data)

    # Add source file record
    project.sources.append(SourceFile(
        filename=file.filename,
        file_type="reference",
        sha256=sha,
    ))

    push_undo(project)
    save_project(project)
    current_project = project

    return {
        "filename": file.filename,
        "digs_loaded": len(wb_data.digs),
        "sha256": sha,
    }


@app.get("/decompose/digs")
async def decompose_digs():
    """List available DIGs from loaded reference data."""
    project = _require_project()
    if not project.reference_data:
        return []
    digs = project.reference_data.get("digs", {})
    return list(digs.values())


@app.post("/decompose/run")
async def decompose_run(request: Request):
    """Start decomposition job (async)."""
    global current_project, _active_job_id
    project = _require_project()
    body = await request.json()
    dig_ids = body.get("dig_ids", [])
    # Frontend sends settings at top level, not nested under "settings"
    settings = body.get("settings", None) or body

    if not project.reference_data:
        raise HTTPException(400, "No reference data loaded. Upload a workbook first.")

    # Empty dig_ids means "all DIGs"
    if not dig_ids:
        dig_ids = list(project.reference_data.get("digs", {}).keys())
    if not dig_ids:
        raise HTTPException(400, "No reference data loaded. Upload a workbook first.")

    # Concurrent operation guard (Section 9.5)
    if _active_job_id and _active_job_id in jobs and jobs[_active_job_id].status == "running":
        active_job = jobs[_active_job_id]
        return JSONResponse(status_code=409, content={
            "error": "job_active",
            "job_id": _active_job_id,
            "job_type": active_job.job_type,
            "message": "A job is already running.",
        })

    # Check for orphaned links before starting (Section 9.1)
    warning = None
    affected_digs = []
    for did in dig_ids:
        if did in project.decomposition_trees:
            tree_data = project.decomposition_trees[did]
            tree = RequirementTree.model_validate(tree_data) if isinstance(tree_data, dict) else tree_data
            tree_reqs = _flatten_tree_to_requirements(tree)
            tree_req_ids = {r.id for r in tree_reqs}
            link_count = sum(1 for l in project.links if l.source in tree_req_ids or l.target in tree_req_ids)
            if link_count > 0:
                affected_digs.append({"dig_id": did, "link_count": link_count})
    if affected_digs:
        warning = {
            "warning": "orphaned_links",
            "affected_digs": affected_digs,
            "message": ", ".join(
                f"DIG {d['dig_id']} has {d['link_count']} requirements with traceability links"
                for d in affected_digs
            ) + ". Re-decomposing may change requirement IDs.",
        }

    job_id = str(uuid.uuid4())
    job = Job(id=job_id, job_type="decompose", settings={"dig_ids": dig_ids, **settings})
    jobs[job_id] = job
    _active_job_id = job_id

    async def _run():
        global _active_job_id
        from src.decompose.loader import WorkbookData
        from src.decompose.decomposer import decompose_dig
        from src.decompose.verifier import apply_vv_to_tree
        from src.decompose.validator import validate_tree_structure, run_semantic_judge
        from src.decompose.refiner import refine_tree
        from src.core.cost_tracker import CostTracker

        try:
            job.status = "running"
            total_digs = len(dig_ids)
            job.emit({"type": "started", "job_id": job_id, "dig_ids": dig_ids, "total_digs": total_digs})

            ref_data = WorkbookData(**project.reference_data)
            max_depth = settings.get("max_depth", project.decomposition_settings.max_depth)
            max_breadth = settings.get("max_breadth", project.decomposition_settings.max_breadth)
            skip_vv = settings.get("skip_vv", project.decomposition_settings.skip_vv)
            skip_judge = settings.get("skip_judge", project.decomposition_settings.skip_judge)
            decompose_model = config.DECOMPOSE_MODEL
            tracker = CostTracker(model=decompose_model)
            total_nodes = 0

            for idx, dig_id in enumerate(dig_ids, 1):
                if job.cancelled:
                    job.emit({"type": "cancelled"})
                    job.status = "cancelled"
                    _active_job_id = None
                    return

                dig_info = project.reference_data.get("digs", {}).get(dig_id)
                if not dig_info:
                    job.emit({"type": "warning", "message": f"DIG {dig_id} not found"})
                    continue

                dig_text = dig_info["dig_text"]
                job.emit({"type": "dig_started", "dig_id": dig_id, "dig_text": dig_text, "index": idx, "total": total_digs})
                job.emit({"type": "phase", "dig_id": dig_id, "phase": "decompose", "detail": f"Building requirement tree (depth {max_depth})"})
                tree = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: decompose_dig(dig_id, dig_text, ref_data, max_depth, max_breadth, skip_vv, tracker, model=decompose_model)
                )
                job.emit({"type": "cost", "total_cost": tracker.get_summary().total_cost_usd})

                if not skip_vv:
                    job.emit({"type": "phase", "dig_id": dig_id, "phase": "vv", "detail": "Generating verification & validation criteria"})
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: apply_vv_to_tree(tree, ref_data, tracker, model=decompose_model)
                    )
                    job.emit({"type": "cost", "total_cost": tracker.get_summary().total_cost_usd})

                job.emit({"type": "phase", "dig_id": dig_id, "phase": "validate", "detail": "Checking tree structure"})
                issues = validate_tree_structure(tree, ref_data, max_depth, max_breadth)

                if not skip_judge:
                    job.emit({"type": "phase", "dig_id": dig_id, "phase": "judge", "detail": "Semantic quality review"})
                    review = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: run_semantic_judge(tree, tracker, model=decompose_model)
                    )
                    job.emit({"type": "cost", "total_cost": tracker.get_summary().total_cost_usd})
                    if review.issues:
                        job.emit({"type": "phase", "dig_id": dig_id, "phase": "refine", "detail": f"Addressing {len(review.issues)} issue(s)"})
                        tree = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: refine_tree(tree, review, ref_data, tracker, model=decompose_model)
                        )
                        job.emit({"type": "cost", "total_cost": tracker.get_summary().total_cost_usd})

                num_nodes = tree.count_nodes()
                total_nodes += num_nodes
                project.decomposition_trees[dig_id] = json.loads(tree.model_dump_json())
                job.emit({"type": "dig_complete", "dig_id": dig_id, "nodes": num_nodes})

            _sync_modeling_queue(project)

            # Detect orphaned links after decomposition (Section 9.1)
            orphaned = _detect_orphaned_links(project)
            if orphaned:
                job.emit({"type": "warning", "message": f"{len(orphaned)} traceability links now reference requirements that no longer exist."})

            save_project(project)

            job.status = "complete"
            job.emit({"type": "complete", "total_digs": total_digs, "total_nodes": total_nodes})
        except Exception as exc:
            job.status = "failed"
            job.emit({"type": "error", "message": str(exc)})
        finally:
            _active_job_id = None

    job.task = asyncio.create_task(_run())
    result = {"job_id": job_id}
    if warning:
        result["warning"] = warning
    return result


@app.get("/decompose/stream/{job_id}")
async def decompose_stream(job_id: str):
    """SSE progress stream for decomposition job."""
    async def event_generator():
        job = jobs.get(job_id)
        if not job:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return
        last_idx = 0
        while True:
            while last_idx < len(job.events):
                event = job.events[last_idx]
                yield f"data: {json.dumps(event)}\n\n"
                last_idx += 1
                if event.get("type") in ("complete", "error", "cancelled"):
                    return
            if job.status in ("complete", "failed", "cancelled"):
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/decompose/cancel/{job_id}")
async def decompose_cancel(job_id: str):
    """Cancel a running decomposition job."""
    global _active_job_id
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.cancelled = True
    if _active_job_id == job_id:
        _active_job_id = None
    return {"status": "cancelling", "job_id": job_id}


@app.get("/decompose/results")
async def decompose_results():
    """List all decomposed trees (metadata)."""
    project = _require_project()
    results = []
    for dig_id, tree_data in project.decomposition_trees.items():
        tree = RequirementTree.model_validate(tree_data) if isinstance(tree_data, dict) else tree_data
        results.append({
            "dig_id": dig_id,
            "dig_text": tree.dig_text,
            "num_nodes": tree.count_nodes(),
            "max_depth": tree.max_depth(),
            "cost": tree.cost.total_cost_usd if tree.cost else 0.0,
            "queued": dig_id in [mid.split("-")[0] for mid in project.modeling_queue] if project.modeling_queue else False,
        })
    return results


@app.get("/decompose/results/{dig_id}")
async def decompose_result(dig_id: str):
    """Get full tree for a DIG."""
    project = _require_project()
    tree_data = project.decomposition_trees.get(dig_id)
    if tree_data is None:
        raise HTTPException(404, f"No decomposition found for DIG {dig_id}")
    return tree_data


@app.delete("/decompose/results/{dig_id}")
async def decompose_delete(dig_id: str):
    """Delete a decomposition."""
    global current_project
    project = _require_project()
    if dig_id not in project.decomposition_trees:
        raise HTTPException(404, f"No decomposition found for DIG {dig_id}")

    push_undo(project)
    del project.decomposition_trees[dig_id]
    _sync_modeling_queue(project)
    save_project(project)
    current_project = project
    return {"status": "deleted", "dig_id": dig_id}


@app.post("/decompose/estimate")
async def decompose_estimate(request: Request):
    """Dry-run cost estimate based on num DIGs, depth, and model pricing."""
    project = _require_project()
    body = await request.json()
    dig_ids = body.get("dig_ids", [])
    max_depth = body.get("max_depth", project.decomposition_settings.max_depth)
    max_breadth = body.get("max_breadth", project.decomposition_settings.max_breadth)
    model = body.get("model", config.DECOMPOSE_MODEL)

    # Empty dig_ids means "all DIGs"
    if not dig_ids and project.reference_data:
        dig_ids = list(project.reference_data.get("digs", {}).keys())

    pricing = MODEL_PRICING.get(model, {})
    input_rate = pricing.get("input_per_mtok", 0.0)
    output_rate = pricing.get("output_per_mtok", 0.0)

    num_digs = len(dig_ids)
    # Estimate: each DIG generates ~max_depth levels, each level ~max_breadth nodes
    # Each node: ~800 input tokens, ~600 output tokens for decompose + ~400/300 for V&V
    est_nodes_per_dig = sum(max_breadth ** i for i in range(max_depth))
    total_nodes = num_digs * est_nodes_per_dig
    est_input = total_nodes * 1200
    est_output = total_nodes * 900

    min_cost = (est_input * input_rate + est_output * output_rate) / 1_000_000
    max_cost = min_cost * 1.5  # 50% buffer

    return {
        "digs": num_digs,
        "num_digs": num_digs,
        "estimated_nodes": total_nodes,
        "max_total_calls": total_nodes,
        "total_calls": total_nodes,
        "model": model,
        "est_cost_usd": round(max_cost, 4),
        "estimated_min_cost": round(min_cost, 4),
        "estimated_max_cost": round(max_cost, 4),
    }


@app.post("/decompose/send-to-model")
async def decompose_send_to_model(request: Request):
    """Manually send requirement IDs to modeling queue."""
    global current_project
    project = _require_project()
    body = await request.json()
    req_ids = body.get("req_ids", [])

    push_undo(project)
    # Add to modeling queue (dedup)
    existing = set(project.modeling_queue)
    for rid in req_ids:
        if rid not in existing:
            project.modeling_queue.append(rid)
            existing.add(rid)

    save_project(project)
    current_project = project
    return {"status": "ok", "queue_size": len(project.modeling_queue)}


@app.post("/decompose/settings")
async def decompose_settings(request: Request):
    """Update decompose model + depth/breadth."""
    global current_project
    project = _require_project()
    body = await request.json()

    push_undo(project)
    if "model" in body:
        project.decomposition_settings.model = body["model"]
    if "max_depth" in body:
        project.decomposition_settings.max_depth = body["max_depth"]
    if "max_breadth" in body:
        project.decomposition_settings.max_breadth = body["max_breadth"]
    if "skip_vv" in body:
        project.decomposition_settings.skip_vv = body["skip_vv"]
    if "skip_judge" in body:
        project.decomposition_settings.skip_judge = body["skip_judge"]

    save_project(project)
    current_project = project
    return {"status": "ok", "decomposition_settings": json.loads(project.decomposition_settings.model_dump_json())}


# ---------------------------------------------------------------------------
# Model routes
# ---------------------------------------------------------------------------

@app.post("/model/upload")
async def model_upload(file: UploadFile = File(...)):
    """Direct upload of pre-decomposed requirements."""
    global current_project
    project = _require_project()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    from src.core.project import _slugify as project_slugify
    slug = project_slugify(project.project.name)
    uploads_dir = config.PROJECTS_DIR / slug / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    dest = uploads_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Compute SHA-256 and parse requirements off the event loop
    import hashlib
    from src.core.parser import parse_requirements_file

    loop = asyncio.get_event_loop()

    sha = await loop.run_in_executor(
        None, lambda: hashlib.sha256(dest.read_bytes()).hexdigest()
    )

    try:
        reqs = await loop.run_in_executor(None, parse_requirements_file, dest)
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse requirements: {exc}")

    push_undo(project)

    # Add to project
    project.requirements.extend(reqs)
    new_ids = [r.id for r in reqs]
    project.modeling_queue.extend(new_ids)

    project.sources.append(SourceFile(
        filename=file.filename,
        file_type="requirements",
        sha256=sha,
    ))

    save_project(project)
    current_project = project

    return {
        "filename": file.filename,
        "requirements_loaded": len(reqs),
        "sha256": sha,
    }


@app.get("/model/data")
async def model_data():
    """Return current project model data (layers, requirements, links)."""
    project = _require_project()
    return {
        "layers": project.layers,
        "requirements": [json.loads(r.model_dump_json()) for r in project.requirements],
        "links": [json.loads(l.model_dump_json()) for l in project.links],
        "instructions": project.instructions,
    }


@app.get("/model/queue")
async def model_queue():
    """Get requirements available for modeling."""
    project = _require_project()
    dismissed = set(project.dismissed_from_modeling)
    queue_set = set(project.modeling_queue)
    result = []
    for r in project.requirements:
        if r.id in queue_set and r.id not in dismissed:
            result.append(json.loads(r.model_dump_json()))
    return result


@app.post("/model/dismiss")
async def model_dismiss(request: Request):
    """Hide requirements from modeling queue."""
    global current_project
    project = _require_project()
    body = await request.json()
    req_ids = body.get("req_ids", [])

    push_undo(project)
    existing = set(project.dismissed_from_modeling)
    for rid in req_ids:
        if rid not in existing:
            project.dismissed_from_modeling.append(rid)
            existing.add(rid)

    save_project(project)
    current_project = project
    return {"status": "ok", "dismissed_count": len(project.dismissed_from_modeling)}


@app.post("/model/restore")
async def model_restore(request: Request):
    """Restore dismissed requirements."""
    global current_project
    project = _require_project()
    body = await request.json()
    req_ids = set(body.get("req_ids", []))

    push_undo(project)
    project.dismissed_from_modeling = [
        rid for rid in project.dismissed_from_modeling if rid not in req_ids
    ]

    save_project(project)
    current_project = project
    return {"status": "ok", "dismissed_count": len(project.dismissed_from_modeling)}


@app.post("/model/estimate")
async def model_estimate(request: Request):
    """Dry-run cost estimate for MBSE model generation."""
    project = _require_project()
    body = await request.json()
    req_ids = body.get("req_ids", body.get("selected_requirements", []))
    layers = body.get("layers", body.get("selected_layers", project.model_settings.selected_layers))
    model = body.get("model", config.MBSE_MODEL)

    pricing = MODEL_PRICING.get(model, {})
    input_rate = pricing.get("input_per_mtok", 0.0)
    output_rate = pricing.get("output_per_mtok", 0.0)

    num_reqs = len(req_ids) if isinstance(req_ids, list) else 0
    num_layers = len(layers) if isinstance(layers, list) else 0
    # Each requirement × layer ≈ 1 API call (~1200 input, ~800 output tokens)
    total_calls = num_reqs * max(num_layers, 1)
    est_input = total_calls * 1200
    est_output = total_calls * 800

    min_cost = (est_input * input_rate + est_output * output_rate) / 1_000_000
    max_cost = min_cost * 1.5

    return {
        "model": model,
        "total_calls": total_calls,
        "estimated_min_cost": round(min_cost, 4),
        "estimated_max_cost": round(max_cost, 4),
    }


@app.post("/model/run")
async def model_run(request: Request):
    """Start MBSE pipeline job."""
    global current_project, _active_job_id
    project = _require_project()
    body = await request.json()
    req_ids = body.get("req_ids", [])
    layers = body.get("layers", project.model_settings.selected_layers)
    mode = body.get("mode", project.project.mode)

    if not req_ids:
        raise HTTPException(400, "No requirement IDs provided")
    if not layers:
        raise HTTPException(400, "No layers selected")

    # Concurrent operation guard (Section 9.5)
    if _active_job_id and _active_job_id in jobs and jobs[_active_job_id].status == "running":
        active_job = jobs[_active_job_id]
        return JSONResponse(status_code=409, content={
            "error": "job_active",
            "job_id": _active_job_id,
            "job_type": active_job.job_type,
            "message": "A job is already running.",
        })

    job_id = str(uuid.uuid4())
    job = Job(id=job_id, job_type="model", settings={"req_ids": req_ids, "layers": layers, "mode": mode})
    jobs[job_id] = job
    _active_job_id = job_id

    async def _run():
        global _active_job_id
        from src.model.pipeline import run_pipeline, merge_batch_into_project
        from src.core.cost_tracker import CostTracker

        try:
            job.status = "running"
            job.emit({"type": "started", "job_id": job_id})

            # Get requirements from project
            req_map = {r.id: r for r in project.requirements}
            reqs = [req_map[rid] for rid in req_ids if rid in req_map]

            if not reqs:
                job.emit({"type": "error", "message": "No matching requirements found"})
                job.status = "failed"
                return

            model_name = config.MBSE_MODEL

            def _emit(event):
                job.emit(event)

            skip_instruct = body.get("skip_instruct", False)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_pipeline(
                    requirements=reqs,
                    mode=mode,
                    selected_layers=layers,
                    model=model_name,
                    provider=config.PROVIDER,
                    emit=_emit,
                    existing_model=project if project.layers else None,
                    skip_instruct=skip_instruct,
                ),
            )

            merge_batch_into_project(
                project=project,
                new_requirements=result.requirements,
                new_layers=result.layers,
                new_links=result.links,
                new_instructions=result.instructions,
                source_file="web-upload",
                layers_generated=layers,
                model_name=model_name,
                cost=result.meta.cost.total_cost_usd if result.meta and result.meta.cost else 0.0,
            )

            save_project(project)
            current_project = project
            job.status = "complete"
            job.emit({"type": "complete"})
        except Exception as exc:
            job.status = "failed"
            job.emit({"type": "error", "message": str(exc)})
        finally:
            _active_job_id = None

    job.task = asyncio.create_task(_run())
    return {"job_id": job_id}


@app.get("/model/stream/{job_id}")
async def model_stream(job_id: str):
    """SSE progress stream for model job."""
    async def event_generator():
        job = jobs.get(job_id)
        if not job:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return
        last_idx = 0
        while True:
            while last_idx < len(job.events):
                event = job.events[last_idx]
                yield f"data: {json.dumps(event)}\n\n"
                last_idx += 1
                if event.get("type") in ("complete", "error", "cancelled"):
                    return
            if job.status in ("complete", "failed", "cancelled"):
                return
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/model/cancel/{job_id}")
async def model_cancel(job_id: str):
    """Cancel a running model job."""
    global _active_job_id
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.cancelled = True
    if _active_job_id == job_id:
        _active_job_id = None
    return {"status": "cancelling", "job_id": job_id}


@app.post("/model/chat")
async def model_chat(request: Request):
    """Chat with project-wide agent."""
    global current_project
    project = _require_project()
    body = await request.json()
    message = body.get("message", "")

    if not message.strip():
        raise HTTPException(400, "Empty message")

    from src.model.agent.chat import chat_with_agent
    from src.core.cost_tracker import CostTracker

    tracker = CostTracker(model=config.MBSE_MODEL)

    try:
        response_text, updated_history = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chat_with_agent(
                project=project,
                user_message=message,
                conversation_history=project.chat_history,
                tracker=tracker,
                mode="model",
            ),
        )
        project.chat_history = updated_history
        save_project(project)
        current_project = project
        return {"response": response_text}
    except Exception as exc:
        raise HTTPException(500, f"Chat failed: {exc}")


@app.post("/model/chat/clear")
async def model_chat_clear():
    """Clear chat history."""
    global current_project
    project = _require_project()
    project.chat_history = []
    save_project(project)
    current_project = project
    return {"status": "ok"}


@app.post("/model/retry-instructions")
async def model_retry_instructions(request: Request):
    """Regenerate recreation instructions."""
    global current_project
    project = _require_project()

    if not project.layers:
        raise HTTPException(400, "No model layers to generate instructions for")

    from src.model.stages import generate_instructions
    from src.core.cost_tracker import CostTracker
    from src.core.llm_client import create_client

    mbse_model = config.MBSE_MODEL
    tracker = CostTracker(model=mbse_model)

    try:
        def _emit(event):
            pass  # No SSE for retry

        instructions = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_instructions(
                project.project.mode,
                {"layers": project.layers},
                tracker,
                client=create_client(model=mbse_model),
                emit=_emit,
                model=mbse_model,
            ),
        )
        push_undo(project)
        project.instructions = instructions
        save_project(project)
        current_project = project
        return {"status": "ok", "instructions": instructions}
    except Exception as exc:
        raise HTTPException(500, f"Failed to regenerate instructions: {exc}")


@app.post("/model/settings")
async def model_settings(request: Request):
    """Update modeling model + layer selection."""
    global current_project
    project = _require_project()
    body = await request.json()

    push_undo(project)
    if "model" in body:
        project.model_settings.model = body["model"]
    if "layers" in body:
        project.model_settings.selected_layers = body["layers"]

    save_project(project)
    current_project = project
    return {"status": "ok", "model_settings": json.loads(project.model_settings.model_dump_json())}


@app.put("/model/element")
async def update_element(request: Request):
    """Rename or update a model element."""
    global current_project
    project = _require_project()
    body = await request.json()
    layer_key = body.get("layer")
    coll_key = body.get("collection")
    elem_id = body.get("id")
    updates = body.get("updates", {})

    if not layer_key or not coll_key or not elem_id:
        raise HTTPException(400, "layer, collection, and id are required")

    layer = project.layers.get(layer_key)
    if not layer or coll_key not in layer:
        raise HTTPException(404, f"Layer '{layer_key}/{coll_key}' not found")

    push_undo(project)
    coll = layer[coll_key]
    found = False
    for elem in coll:
        if isinstance(elem, dict) and elem.get("id") == elem_id:
            elem.update(updates)
            found = True
            break
    if not found:
        raise HTTPException(404, f"Element '{elem_id}' not found")

    save_project(project)
    current_project = project
    return {"status": "ok"}


@app.delete("/model/element")
async def delete_element_endpoint(request: Request):
    """Delete a model element."""
    global current_project
    project = _require_project()
    body = await request.json()
    layer_key = body.get("layer")
    coll_key = body.get("collection")
    elem_id = body.get("id")

    if not layer_key or not coll_key or not elem_id:
        raise HTTPException(400, "layer, collection, and id are required")

    layer = project.layers.get(layer_key)
    if not layer or coll_key not in layer:
        raise HTTPException(404, f"Layer '{layer_key}/{coll_key}' not found")

    push_undo(project)
    original_len = len(layer[coll_key])
    layer[coll_key] = [e for e in layer[coll_key] if not (isinstance(e, dict) and e.get("id") == elem_id)]
    if len(layer[coll_key]) == original_len:
        raise HTTPException(404, f"Element '{elem_id}' not found")

    save_project(project)
    current_project = project
    return {"status": "ok"}


@app.post("/model/element")
async def add_element_endpoint(request: Request):
    """Add a new element to a model layer."""
    global current_project
    project = _require_project()
    body = await request.json()
    layer_key = body.get("layer")
    coll_key = body.get("collection")
    element = body.get("element")

    if not layer_key or not coll_key or not element:
        raise HTTPException(400, "layer, collection, and element are required")

    if layer_key not in project.layers:
        project.layers[layer_key] = {}
    if coll_key not in project.layers[layer_key]:
        project.layers[layer_key][coll_key] = []

    push_undo(project)
    project.layers[layer_key][coll_key].append(element)

    save_project(project)
    current_project = project
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Export routes
# ---------------------------------------------------------------------------

@app.get("/export/decomposition")
async def export_decomposition():
    """Export decomposed requirements as XLSX."""
    project = _require_project()
    if not project.decomposition_trees:
        raise HTTPException(400, "No decomposition trees to export")

    from src.core.exporter import export_trees_to_xlsx

    trees = []
    for tree_data in project.decomposition_trees.values():
        tree = RequirementTree.model_validate(tree_data) if isinstance(tree_data, dict) else tree_data
        trees.append(tree)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp_path = Path(tmp.name)

    export_trees_to_xlsx(trees, tmp_path)
    project_name = project.project.name or "project"
    filename = project_name.lower().replace(" ", "-") + "-decomposition.xlsx"
    return FileResponse(tmp_path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/export/model/capella")
async def export_capella(mode: str = "project"):
    """Export MBSE model as native Capella project."""
    project = _require_project()

    if not project.layers:
        raise HTTPException(400, "No model layers to export")

    if project.project.mode != "capella":
        raise HTTPException(400, "Capella export only available for Capella-mode projects")

    from src.core.capella_export import export_capella_project, export_capella_fragment

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            if mode == "fragment":
                result = export_capella_fragment(project, tmp_path)
                media_type = "application/xml"
            else:
                result = export_capella_project(project, tmp_path)
                media_type = "application/zip"

            return FileResponse(
                result,
                filename=result.name,
                media_type=media_type,
            )
    except Exception as exc:
        logger.error(f"Capella export failed: {exc}")
        raise HTTPException(500, f"Export failed: {exc}")


@app.get("/export/model/{fmt}")
async def export_model(fmt: str):
    """Export MBSE model (json/xlsx/text)."""
    project = _require_project()

    from src.core.exporter import export_json, export_xlsx, export_text

    project_name = project.project.name or "project"
    base_name = project_name.lower().replace(" ", "-") + "-model"

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}") as tmp:
        tmp_path = Path(tmp.name)

    if fmt == "json":
        export_json(project, tmp_path)
        media_type = "application/json"
        filename = base_name + ".json"
    elif fmt == "xlsx":
        export_xlsx(project, tmp_path)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = base_name + ".xlsx"
    elif fmt == "text":
        export_text(project, tmp_path)
        media_type = "text/plain"
        filename = base_name + ".txt"
    else:
        raise HTTPException(400, f"Unsupported format: {fmt}. Use json, xlsx, or text.")

    return FileResponse(tmp_path, filename=filename, media_type=media_type)


@app.get("/export/full")
async def export_full():
    """Export full project JSON."""
    project = _require_project()
    return json.loads(project.model_dump_json())


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def start_server(port: int = 8000):
    """Start the web server."""
    import uvicorn
    print(f"\n  Shipyard web interface starting...")
    print(f"  Open http://localhost:{port} in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
