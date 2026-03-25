from src.core.models.core import ProjectModel, ProjectMeta, Requirement
from src.model.agent.chat import _build_system_prompt, _build_summary


def test_build_summary():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    p.requirements = [Requirement(id="REQ-1", text="Ship shall float", source_dig="9584")]
    summary = _build_summary(p)
    assert "Test" in summary
    assert "1" in summary  # 1 requirement
    assert "capella" in summary


def test_build_summary_empty():
    p = ProjectModel(project=ProjectMeta(name="Empty", mode="rhapsody"))
    summary = _build_summary(p)
    assert "0 decomposed DIGs" in summary
    assert "0 requirements" in summary


def test_build_system_prompt():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    prompt = _build_system_prompt(p, mode="decompose")
    assert "Shipyard" in prompt
    assert "decompose" in prompt.lower()


def test_build_system_prompt_model_mode():
    p = ProjectModel(project=ProjectMeta(name="Test", mode="capella"))
    prompt = _build_system_prompt(p, mode="model")
    assert "model" in prompt.lower()


def test_chat_import():
    from src.model.agent.chat import chat_with_agent
    assert chat_with_agent is not None
