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
from fastapi.staticfiles import StaticFiles

from src.core import config
from src.core.config import MODEL_CATALOGUE, MODEL_PRICING, DECOMPOSE_MODEL, MBSE_MODEL
from src.core.models.core import ProjectModel
from src.core.project import (
    new_project,
    save_project,
    load_project,
    list_projects,
    delete_project,
    push_undo,
    pop_undo,
    push_redo,
    pop_redo,
)

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent

app = FastAPI(title="Shipyard")

# Mount static files only if the directory exists
_static_dir = WEB_DIR / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


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


def _slugify(name: str) -> str:
    import re
    slug = re.sub(r'[^a-z0-9]+', name.lower(), '').strip('-')
    # Use the same logic as project module
    from src.core.project import _slugify as project_slugify
    return project_slugify(name)


def _require_project() -> ProjectModel:
    """Return current_project or raise 404."""
    if current_project is None:
        raise HTTPException(404, "No active project. Create or select a project first.")
    return current_project


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@app.get("/")
async def index():
    """Root endpoint. Returns JSON status (templates not yet available)."""
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
    env_path = config.PACKAGE_ROOT / ".env"
    lines = [
        "# Shipyard Configuration",
        f"PROVIDER={body.get('provider', config.PROVIDER)}",
        f"MODEL={body.get('model', config.MODEL)}",
        f"DEFAULT_MODE={body.get('default_mode', config.DEFAULT_MODE)}",
        f"DECOMPOSE_MODEL={body.get('decompose_model', config.DECOMPOSE_MODEL)}",
        f"MBSE_MODEL={body.get('mbse_model', config.MBSE_MODEL)}",
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
    enabled = body.get("enabled", True)

    push_undo(project)
    project.auto_send = enabled
    save_project(project)
    current_project = project

    return {"auto_send": project.auto_send}


@app.get("/settings/cost-history")
async def cost_history():
    """Read cost_log.jsonl if it exists."""
    log_path = config.OUTPUT_DIR / "cost_log.jsonl"
    if not log_path.exists():
        return {"runs": [], "total_spend": 0.0, "avg_per_run": 0.0, "total_runs": 0}

    runs = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    total_spend = sum(r.get("totals", {}).get("cost_usd", 0.0) for r in runs)
    avg_per_run = (total_spend / len(runs)) if runs else 0.0

    return {
        "runs": runs,
        "total_runs": len(runs),
        "total_spend": round(total_spend, 6),
        "avg_per_run": round(avg_per_run, 6),
    }


@app.get("/settings/check-updates")
async def check_updates():
    """Git-based update check."""
    import subprocess
    pkg_root = str(config.PACKAGE_ROOT)
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
    try:
        pull = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True,
            cwd=str(config.PACKAGE_ROOT), timeout=30,
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

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "-q"],
            capture_output=True, text=True,
            cwd=str(config.PACKAGE_ROOT), timeout=60,
        )

        return {
            "status": "ok",
            "message": "Updated! Restart the server to apply changes.",
            "updated": True,
            "details": pull.stdout.strip(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def start_server(port: int = 8000):
    """Start the web server."""
    import uvicorn
    print(f"\n  Shipyard web interface starting...")
    print(f"  Open http://localhost:{port} in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
