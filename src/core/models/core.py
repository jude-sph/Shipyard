from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class CostEntry(BaseModel):
    call_type: str
    stage: str = ""
    level: int = 0
    input_tokens: int
    output_tokens: int
    cost_usd: float


class CostSummary(BaseModel):
    breakdown: list[CostEntry] = Field(default_factory=list)

    @computed_field
    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.breakdown)

    @computed_field
    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.breakdown)

    @computed_field
    @property
    def total_cost_usd(self) -> float:
        return round(sum(e.cost_usd for e in self.breakdown), 10)

    @computed_field
    @property
    def api_calls(self) -> int:
        return len(self.breakdown)


class Requirement(BaseModel):
    id: str
    text: str
    source_dig: str


class Link(BaseModel):
    id: str
    source: str
    target: str
    type: str
    description: str


class InstructionStep(BaseModel):
    step: int
    action: str
    detail: str
    layer: str


class Meta(BaseModel):
    source_file: str
    mode: Literal["capella", "rhapsody"]
    selected_layers: list[str]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    llm_provider: str
    llm_model: str
    cost: CostSummary | None = None


class MBSEModel(BaseModel):
    meta: Meta | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    layers: dict[str, Any] = Field(default_factory=dict)
    links: list[Link] = Field(default_factory=list)
    instructions: dict = Field(default_factory=dict)


class ProjectMeta(BaseModel):
    name: str = "Untitled Project"
    mode: Literal["capella", "rhapsody"] = "capella"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BatchRecord(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    batch_type: Literal["decompose", "model", "import"] = "model"
    source_file: str
    requirement_ids: list[str]
    layers_generated: list[str]
    model: str
    cost: float
    requirement_snapshot: list[str] = Field(default_factory=list)


class SourceFile(BaseModel):
    filename: str
    upload_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_type: Literal["reference", "requirements"]
    sha256: str


class DecompSettings(BaseModel):
    max_depth: int = 4
    max_breadth: int = 3
    skip_vv: bool = False
    skip_judge: bool = False
    model: str = "claude-sonnet-4-6"


class ModelSettings(BaseModel):
    selected_layers: list[str] = Field(default_factory=list)
    model: str = "claude-sonnet-4-6"


class ProjectModel(MBSEModel):
    """Extends MBSEModel with project metadata and batch history."""
    project: ProjectMeta = Field(default_factory=ProjectMeta)
    batches: list[BatchRecord] = Field(default_factory=list)
    chat_history: list[dict] = Field(default_factory=list)
    sources: list[SourceFile] = Field(default_factory=list)
    reference_data: dict | None = None
    decomposition_trees: dict[str, Any] = Field(default_factory=dict)
    decomposition_settings: DecompSettings = Field(default_factory=DecompSettings)
    auto_send: bool = True
    modeling_queue: list[str] = Field(default_factory=list)
    dismissed_from_modeling: list[str] = Field(default_factory=list)
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    cost_summary: CostSummary | None = None
