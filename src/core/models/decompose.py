from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RequirementNode(BaseModel):
    level: int
    level_name: str
    allocation: str
    chapter_code: str
    derived_name: str
    technical_requirement: str
    rationale: str
    system_hierarchy_id: str
    acceptance_criteria: str | None = None
    verification_method: list[str] = Field(default_factory=list)
    verification_event: list[str] = Field(default_factory=list)
    test_case_descriptions: list[str] = Field(default_factory=list)
    confidence_notes: str | None = None
    decomposition_complete: bool = False
    children: list[RequirementNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_vv_arrays(self) -> RequirementNode:
        methods = self.verification_method
        events = self.verification_event
        cases = self.test_case_descriptions
        lengths = [len(methods), len(events), len(cases)]
        non_zero = [l for l in lengths if l > 0]
        if non_zero and len(set(non_zero)) > 1:
            raise ValueError(
                f"V&V array length mismatch: methods={len(methods)}, "
                f"events={len(events)}, test_cases={len(cases)}"
            )
        return self

    @model_validator(mode="after")
    def validate_tbd_has_notes(self) -> RequirementNode:
        if "[TBD]" in self.technical_requirement and not self.confidence_notes:
            raise ValueError(
                "technical_requirement contains [TBD] but confidence_notes is empty"
            )
        return self

    @model_validator(mode="after")
    def validate_allocation(self) -> RequirementNode:
        valid = {"GTR", "SDS", "GTR / SDS"}
        if self.allocation not in valid:
            # Coerce common LLM misformats before rejecting
            upper = self.allocation.upper().strip()
            if "GTR" in upper and "SDS" in upper:
                self.allocation = "GTR / SDS"
            elif "GTR" in upper:
                self.allocation = "GTR"
            elif "SDS" in upper:
                self.allocation = "SDS"
            else:
                self.allocation = "Information Not Found"
        return self


class ValidationIssue(BaseModel):
    severity: str
    message: str
    node_path: str


class ValidationResult(BaseModel):
    structural_errors: list[ValidationIssue] = Field(default_factory=list)
    semantic_review: SemanticReview | None = None


class SemanticReview(BaseModel):
    status: str
    issues: list[ValidationIssue] = Field(default_factory=list)


class RequirementTree(BaseModel):
    dig_id: str
    dig_text: str
    root: RequirementNode | None = None
    validation: ValidationResult | None = None
    cost: CostSummary | None = None

    def count_nodes(self) -> int:
        if not self.root:
            return 0

        def _count(node: RequirementNode) -> int:
            return 1 + sum(_count(c) for c in node.children)

        return _count(self.root)

    def max_depth(self) -> int:
        if not self.root:
            return 0

        def _depth(node: RequirementNode) -> int:
            if not node.children:
                return 1
            return 1 + max(_depth(c) for c in node.children)

        return _depth(self.root)


class CostSummary(BaseModel):
    breakdown: list = Field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(e.input_tokens for e in self.breakdown)

    @property
    def total_output_tokens(self) -> int:
        return sum(e.output_tokens for e in self.breakdown)

    @property
    def total_cost_usd(self) -> float:
        return sum(e.cost_usd for e in self.breakdown)

    @property
    def api_calls(self) -> int:
        return len(self.breakdown)
