"""
End-to-end smoke test: create project, verify both modes accessible,
settings work, and basic API responses are correct.
"""
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

def test_full_workflow(client):
    # 1. Create project
    resp = client.post("/project/new", json={"name": "E2E Test", "mode": "capella"})
    assert resp.status_code == 200
    project = resp.json()
    assert project["project"]["name"] == "E2E Test"
    assert project["auto_send"] is True

    # 2. Check decompose mode (no reference data yet)
    resp = client.get("/decompose/results")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/decompose/digs")
    assert resp.status_code == 200

    # 3. Check model mode (empty queue)
    resp = client.get("/model/queue")
    assert resp.status_code == 200
    assert resp.json() == []

    # 4. Check settings
    resp = client.get("/settings")
    assert resp.status_code == 200
    settings = resp.json()
    assert "provider" in settings

    # 5. Check models list
    resp = client.get("/settings/models")
    assert resp.status_code == 200
    assert len(resp.json()) > 0

    # 6. Toggle auto-send
    resp = client.post("/settings/auto-send", json={"enabled": False})
    assert resp.status_code == 200

    # 7. Verify auto-send changed
    resp = client.get("/project")
    assert resp.json()["auto_send"] is False

    # 8. Toggle back
    resp = client.post("/settings/auto-send", json={"enabled": True})
    assert resp.status_code == 200

    # 9. List projects
    resp = client.get("/project/list")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # 10. Check project batches (empty)
    resp = client.get("/project/batches")
    assert resp.status_code == 200
    assert resp.json() == []

    # 11. Send requirements to model manually
    resp = client.post("/decompose/send-to-model", json={"req_ids": ["REQ-1", "REQ-2"]})
    assert resp.status_code == 200

    # 12. Update decompose settings
    resp = client.post("/decompose/settings", json={"max_depth": 3, "skip_vv": True})
    assert resp.status_code == 200
    project = client.get("/project").json()
    assert project["decomposition_settings"]["max_depth"] == 3
    assert project["decomposition_settings"]["skip_vv"] is True

    # 13. Update model settings
    resp = client.post("/model/settings", json={"model": "claude-opus-4-6", "layers": ["operational_analysis", "logical_architecture"]})
    assert resp.status_code == 200
    project = client.get("/project").json()
    assert project["model_settings"]["model"] == "claude-opus-4-6"

    # 14. Dismiss and restore from queue
    resp = client.post("/model/dismiss", json={"req_ids": ["REQ-1"]})
    assert resp.status_code == 200

    resp = client.post("/model/restore", json={"req_ids": ["REQ-1"]})
    assert resp.status_code == 200

    # 15. Clear chat
    resp = client.post("/model/chat/clear")
    assert resp.status_code == 200

    # 16. Export full project
    resp = client.get("/export/full")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project"]["name"] == "E2E Test"

    # 17. Create second project and switch
    resp = client.post("/project/new", json={"name": "Second Ship", "mode": "rhapsody"})
    assert resp.status_code == 200
    assert client.get("/project").json()["project"]["name"] == "Second Ship"

    # Switch back
    resp = client.post("/project/select/e2e-test")
    assert resp.status_code == 200
    assert client.get("/project").json()["project"]["name"] == "E2E Test"

    # 18. Download project
    resp = client.get("/project/download")
    assert resp.status_code == 200
