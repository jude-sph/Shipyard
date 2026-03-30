import copy
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.core import config
from src.core.models.core import ProjectModel, ProjectMeta, Meta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'untitled'


def _resolve_projects_dir(projects_dir: Path | None) -> Path:
    return Path(projects_dir) if projects_dir is not None else config.PROJECTS_DIR


def _project_dir(name_or_slug: str, projects_dir: Path) -> Path:
    """Return the project directory for a given name or slug."""
    slug = _slugify(name_or_slug)
    return projects_dir / slug


def _project_json_path(name_or_slug: str, projects_dir: Path) -> Path:
    return _project_dir(name_or_slug, projects_dir) / "project.json"


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------

def new_project(mode: str, name: str = "Untitled Project", projects_dir: Path | None = None) -> ProjectModel:
    """Create a new ProjectModel in memory (does not save to disk)."""
    return ProjectModel(
        project=ProjectMeta(name=name, mode=mode),
        batches=[],
        meta=Meta(
            source_file="project",
            mode=mode,
            selected_layers=[],
            llm_provider=config.PROVIDER,
            llm_model=config.MODEL,
        ),
        requirements=[],
        layers={},
        links=[],
        instructions={
            "tool": "Capella 7.0" if mode == "capella" else "IBM Rhapsody 10.0",
            "steps": [],
        },
    )


def save_project(project: ProjectModel, projects_dir: Path | None = None) -> Path:
    """Save a project to projects/<slug>/project.json, updating last_modified."""
    projects_dir = _resolve_projects_dir(projects_dir)
    project.project.last_modified = datetime.now(timezone.utc)
    slug = _slugify(project.project.name)
    project_dir = projects_dir / slug
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "project.json"
    data = project.model_dump(mode="python")
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def load_project(name_or_slug: str, projects_dir: Path | None = None) -> ProjectModel | None:
    """Load a project by name or slug from projects/<slug>/project.json."""
    projects_dir = _resolve_projects_dir(projects_dir)
    path = _project_json_path(name_or_slug, projects_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectModel.model_validate(data)
    except Exception:
        return None


def list_projects(projects_dir: Path | None = None) -> list[dict]:
    """Scan the projects directory and return a list of project summaries."""
    projects_dir = _resolve_projects_dir(projects_dir)
    if not projects_dir.exists():
        return []
    results = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        json_path = project_dir / "project.json"
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            project_meta = data.get("project", {})
            results.append({
                "name": project_meta.get("name", project_dir.name),
                "mode": project_meta.get("mode", "capella"),
                "modified": project_meta.get("last_modified"),
                "path": str(json_path),
            })
        except Exception:
            continue
    return results


def delete_project(name_or_slug: str, projects_dir: Path | None = None) -> bool:
    """Delete the project directory for the given name or slug. Returns True if deleted."""
    projects_dir = _resolve_projects_dir(projects_dir)
    project_dir = _project_dir(name_or_slug, projects_dir)
    if not project_dir.exists():
        return False
    shutil.rmtree(project_dir)
    return True


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_project(name_or_slug: str, projects_dir: Path | None = None) -> Path | None:
    """Copy the project's project.json to a timestamped backup file in the same directory."""
    projects_dir = _resolve_projects_dir(projects_dir)
    path = _project_json_path(name_or_slug, projects_dir)
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.parent / f"project-backup-{timestamp}.json"
    import shutil as _shutil
    _shutil.copy2(path, backup_path)
    return backup_path


# ---------------------------------------------------------------------------
# Undo / Redo  (in-memory snapshot stack, max 20)
# ---------------------------------------------------------------------------

_MAX_SNAPSHOTS = 20

# Keyed by project name for simplicity; in a real server the caller would
# own the stacks.  These module-level dicts work for single-process use.
_undo_stacks: dict[str, list[dict]] = {}
_redo_stacks: dict[str, list[dict]] = {}


def _snapshot(project: ProjectModel) -> dict:
    return project.model_dump(mode="python")


def push_undo(project: ProjectModel) -> None:
    """Push a snapshot of the current project state onto the undo stack."""
    key = project.project.name
    stack = _undo_stacks.setdefault(key, [])
    stack.append(_snapshot(project))
    if len(stack) > _MAX_SNAPSHOTS:
        stack.pop(0)
    # Clear redo on new action
    _redo_stacks[key] = []


def pop_undo(project: ProjectModel) -> ProjectModel | None:
    """Restore the most recent undo snapshot, pushing current state to redo."""
    key = project.project.name
    stack = _undo_stacks.get(key, [])
    if not stack:
        return None
    # Push current to redo before restoring
    redo_stack = _redo_stacks.setdefault(key, [])
    redo_stack.append(_snapshot(project))
    if len(redo_stack) > _MAX_SNAPSHOTS:
        redo_stack.pop(0)
    return ProjectModel.model_validate(stack.pop())


def push_redo(project: ProjectModel) -> None:
    """Push a snapshot onto the redo stack (used when undoing)."""
    key = project.project.name
    stack = _redo_stacks.setdefault(key, [])
    stack.append(_snapshot(project))
    if len(stack) > _MAX_SNAPSHOTS:
        stack.pop(0)


def pop_redo(project: ProjectModel) -> ProjectModel | None:
    """Restore the most recent redo snapshot."""
    key = project.project.name
    stack = _redo_stacks.get(key, [])
    if not stack:
        return None
    return ProjectModel.model_validate(stack.pop())
