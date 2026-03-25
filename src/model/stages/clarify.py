from src.core.models.core import Requirement


def apply_clarifications(requirements: list[Requirement], clarifications: dict[str, str]) -> list[Requirement]:
    """Stage 2: Apply user clarification responses to requirements.

    clarifications: dict mapping requirement ID to user's clarification text.
    Returns updated requirements list with clarifications appended to text.
    """
    updated = []
    for req in requirements:
        if req.id in clarifications:
            updated.append(req.model_copy(update={
                "text": f"{req.text} [Clarification: {clarifications[req.id]}]"
            }))
        else:
            updated.append(req)
    return updated
