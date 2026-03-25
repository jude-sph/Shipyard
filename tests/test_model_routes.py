import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("src.core.config.PROJECTS_DIR", tmp_path)
    import src.web.app as app_module
    app_module.current_project = None
    app_module.current_project_name = None
    app_module.jobs = {}
    from src.web.app import app
    return TestClient(app)


def test_model_queue_empty(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/model/queue")
    assert resp.status_code == 200
    assert resp.json() == []


def test_model_dismiss_and_restore(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.post("/model/dismiss", json={"req_ids": ["REQ-1"]})
    assert resp.status_code == 200


def test_model_settings(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.post("/model/settings", json={"model": "claude-opus-4-6", "layers": ["operational_analysis"]})
    assert resp.status_code == 200
    project = client.get("/project").json()
    assert project["model_settings"]["model"] == "claude-opus-4-6"


def test_chat_clear(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.post("/model/chat/clear")
    assert resp.status_code == 200


def test_export_full(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/export/full")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"]["name"] == "Test"
