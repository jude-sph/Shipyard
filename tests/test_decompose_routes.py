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


def test_decompose_results_empty(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/decompose/results")
    assert resp.status_code == 200
    assert resp.json() == []


def test_decompose_digs_no_reference(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.get("/decompose/digs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_send_to_model(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.post("/decompose/send-to-model", json={"req_ids": ["REQ-1", "REQ-2"]})
    assert resp.status_code == 200


def test_decompose_settings(client):
    client.post("/project/new", json={"name": "Test", "mode": "capella"})
    resp = client.post("/decompose/settings", json={"max_depth": 3, "model": "claude-haiku-4-5"})
    assert resp.status_code == 200
    project = client.get("/project").json()
    assert project["decomposition_settings"]["max_depth"] == 3
