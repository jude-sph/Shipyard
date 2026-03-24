from __future__ import annotations

from pydantic import BaseModel, Field


# ── Requirements Diagram ───────────────────────────────────────────────────


class SysMLRequirement(BaseModel):
    id: str
    name: str
    text: str
    priority: str = "medium"
    status: str = "draft"
    source_req: str | None = None


class RequirementsDiagramLayer(BaseModel):
    requirements: list[SysMLRequirement] = Field(default_factory=list)


# ── Block Definition Diagram (BDD) ─────────────────────────────────────────


class Block(BaseModel):
    id: str
    name: str
    type: str = "Block"
    properties: list[str] = Field(default_factory=list)
    ports: list[str] = Field(default_factory=list)


class BlockDefinitionLayer(BaseModel):
    blocks: list[Block] = Field(default_factory=list)


# ── Internal Block Diagram (IBD) ───────────────────────────────────────────


class IBDPart(BaseModel):
    id: str
    name: str
    type: str = "Part"
    block_ref: str


class IBDConnector(BaseModel):
    id: str
    name: str
    source: str
    target: str


class InternalBlockLayer(BaseModel):
    parts: list[IBDPart] = Field(default_factory=list)
    connectors: list[IBDConnector] = Field(default_factory=list)


# ── Activity Diagram ───────────────────────────────────────────────────────


class SysMLAction(BaseModel):
    id: str
    name: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class ActivityDiagramLayer(BaseModel):
    actions: list[SysMLAction] = Field(default_factory=list)


# ── Sequence Diagram ───────────────────────────────────────────────────────


class Lifeline(BaseModel):
    id: str
    name: str
    represents: str


class SequenceMessage(BaseModel):
    id: str
    from_lifeline: str
    to_lifeline: str
    message: str
    sequence: int


class SequenceDiagramLayer(BaseModel):
    lifelines: list[Lifeline] = Field(default_factory=list)
    messages: list[SequenceMessage] = Field(default_factory=list)


# ── State Machine ──────────────────────────────────────────────────────────


class SMState(BaseModel):
    id: str
    name: str
    type: str = "State"  # can also be "Initial" or "Final"


class SMTransition(BaseModel):
    id: str
    source: str
    target: str
    trigger: str | None = None
    guard: str | None = None


class StateMachineLayer(BaseModel):
    states: list[SMState] = Field(default_factory=list)
    transitions: list[SMTransition] = Field(default_factory=list)
