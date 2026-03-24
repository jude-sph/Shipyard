from pathlib import Path
from src.core.project import new_project, save_project, load_project, list_projects, delete_project


def test_new_project(tmp_path):
    project = new_project("capella", "Test Ship", projects_dir=tmp_path)
    assert project.project.name == "Test Ship"
    assert project.project.mode == "capella"
    assert project.auto_send is True


def test_save_and_load(tmp_path):
    project = new_project("capella", "Test Ship", projects_dir=tmp_path)
    save_project(project, projects_dir=tmp_path)
    loaded = load_project("Test Ship", projects_dir=tmp_path)
    assert loaded is not None
    assert loaded.project.name == "Test Ship"


def test_list_projects(tmp_path):
    p1 = new_project("capella", "Ship A", projects_dir=tmp_path)
    save_project(p1, projects_dir=tmp_path)
    p2 = new_project("rhapsody", "Ship B", projects_dir=tmp_path)
    save_project(p2, projects_dir=tmp_path)
    projects = list_projects(projects_dir=tmp_path)
    assert len(projects) == 2
    names = {p["name"] for p in projects}
    assert "Ship A" in names
    assert "Ship B" in names


def test_delete_project(tmp_path):
    p = new_project("capella", "Doomed Ship", projects_dir=tmp_path)
    save_project(p, projects_dir=tmp_path)
    assert len(list_projects(projects_dir=tmp_path)) == 1
    delete_project("Doomed Ship", projects_dir=tmp_path)
    assert len(list_projects(projects_dir=tmp_path)) == 0


def test_load_by_slug(tmp_path):
    p = new_project("capella", "My Cool Ship!", projects_dir=tmp_path)
    save_project(p, projects_dir=tmp_path)
    loaded = load_project("my-cool-ship", projects_dir=tmp_path)
    assert loaded is not None
    assert loaded.project.name == "My Cool Ship!"
