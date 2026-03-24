from __future__ import annotations

from pydantic import BaseModel, Field


# ── Operational Analysis (OA) ──────────────────────────────────────────────


class OperationalEntity(BaseModel):
    id: str
    name: str
    type: str = "OperationalEntity"
    actors: list[str] = Field(default_factory=list)


class OperationalCapability(BaseModel):
    id: str
    name: str
    involved_entities: list[str] = Field(default_factory=list)


class ScenarioStep(BaseModel):
    from_entity: str
    to_entity: str
    message: str
    sequence: int


class Scenario(BaseModel):
    id: str
    name: str
    steps: list[ScenarioStep] = Field(default_factory=list)


class OperationalActivity(BaseModel):
    id: str
    name: str
    entity: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class OperationalProcess(BaseModel):
    id: str
    name: str
    capability_ref: str = ""
    activity_refs: list[str] = Field(default_factory=list)


class OperationalInteraction(BaseModel):
    id: str
    name: str
    source_entity: str
    target_entity: str
    exchanged_items: list[str] = Field(default_factory=list)


class CommunicationMean(BaseModel):
    id: str
    name: str
    source_entity: str
    target_entity: str


class OperationalData(BaseModel):
    id: str
    name: str
    description: str = ""


class InteractionItem(BaseModel):
    id: str
    name: str
    description: str = ""


class OperationalModeState(BaseModel):
    id: str
    name: str
    type: str = "State"
    transitions: list[dict] = Field(default_factory=list)


class OperationalAnalysisLayer(BaseModel):
    entities: list[OperationalEntity] = Field(default_factory=list)
    capabilities: list[OperationalCapability] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    activities: list[OperationalActivity] = Field(default_factory=list)
    operational_processes: list[OperationalProcess] = Field(default_factory=list)
    operational_interactions: list[OperationalInteraction] = Field(default_factory=list)
    communication_means: list[CommunicationMean] = Field(default_factory=list)
    operational_data: list[OperationalData] = Field(default_factory=list)
    interaction_items: list[InteractionItem] = Field(default_factory=list)
    modes_and_states: list[OperationalModeState] = Field(default_factory=list)


# ── System Needs Analysis (SA) ─────────────────────────────────────────────


class SystemFunction(BaseModel):
    id: str
    name: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class SystemFunctionalExchange(BaseModel):
    id: str
    name: str
    source: str
    target: str


class SystemDefinition(BaseModel):
    id: str
    name: str
    description: str = ""


class ExternalActor(BaseModel):
    id: str
    name: str
    type: str = "System"


class SpecifiedCapability(BaseModel):
    id: str
    name: str
    involved_functions: list[str] = Field(default_factory=list)
    involved_chains: list[str] = Field(default_factory=list)


class SystemFunctionalChain(BaseModel):
    id: str
    name: str
    function_refs: list[str] = Field(default_factory=list)
    exchange_refs: list[str] = Field(default_factory=list)


class SpecifiedScenario(BaseModel):
    id: str
    name: str
    steps: list[ScenarioStep] = Field(default_factory=list)


class SpecifiedData(BaseModel):
    id: str
    name: str
    description: str = ""


class SystemExchangedItem(BaseModel):
    id: str
    name: str
    description: str = ""


class SystemModeState(BaseModel):
    id: str
    name: str
    type: str = "State"
    transitions: list[dict] = Field(default_factory=list)


class SystemNeedsAnalysisLayer(BaseModel):
    functions: list[SystemFunction] = Field(default_factory=list)
    exchanges: list[SystemFunctionalExchange] = Field(default_factory=list)
    system_definitions: list[SystemDefinition] = Field(default_factory=list)
    external_actors: list[ExternalActor] = Field(default_factory=list)
    specified_capabilities: list[SpecifiedCapability] = Field(default_factory=list)
    functional_chains: list[SystemFunctionalChain] = Field(default_factory=list)
    specified_scenarios: list[SpecifiedScenario] = Field(default_factory=list)
    specified_data: list[SpecifiedData] = Field(default_factory=list)
    exchanged_items: list[SystemExchangedItem] = Field(default_factory=list)
    modes_and_states: list[SystemModeState] = Field(default_factory=list)


# Backward-compatibility alias
SystemAnalysisLayer = SystemNeedsAnalysisLayer


# ── Logical Architecture (LA) ──────────────────────────────────────────────


class LogicalComponent(BaseModel):
    id: str
    name: str
    functions: list[str] = Field(default_factory=list)


class LogicalFunction(BaseModel):
    id: str
    name: str
    component: str


class NotionalCapability(BaseModel):
    id: str
    name: str
    involved_functions: list[str] = Field(default_factory=list)
    involved_chains: list[str] = Field(default_factory=list)


class LogicalFunctionalChain(BaseModel):
    id: str
    name: str
    function_refs: list[str] = Field(default_factory=list)
    exchange_refs: list[str] = Field(default_factory=list)


class NotionalScenario(BaseModel):
    id: str
    name: str
    steps: list[ScenarioStep] = Field(default_factory=list)


class LogicalFunctionalExchange(BaseModel):
    id: str
    name: str
    source_function: str
    target_function: str
    exchanged_items: list[str] = Field(default_factory=list)


class LogicalExchangedItem(BaseModel):
    id: str
    name: str
    description: str = ""


class LogicalComponentExchange(BaseModel):
    id: str
    name: str
    source_component: str
    target_component: str


class LogicalInterface(BaseModel):
    id: str
    name: str
    component_exchange_ref: str = ""
    exchange_items: list[str] = Field(default_factory=list)


class LogicalModeState(BaseModel):
    id: str
    name: str
    type: str = "State"
    transitions: list[dict] = Field(default_factory=list)


class LogicalArchitectureLayer(BaseModel):
    components: list[LogicalComponent] = Field(default_factory=list)
    functions: list[LogicalFunction] = Field(default_factory=list)
    notional_capabilities: list[NotionalCapability] = Field(default_factory=list)
    functional_chains: list[LogicalFunctionalChain] = Field(default_factory=list)
    notional_scenarios: list[NotionalScenario] = Field(default_factory=list)
    functional_exchanges: list[LogicalFunctionalExchange] = Field(default_factory=list)
    exchanged_items: list[LogicalExchangedItem] = Field(default_factory=list)
    component_exchanges: list[LogicalComponentExchange] = Field(default_factory=list)
    interfaces: list[LogicalInterface] = Field(default_factory=list)
    modes_and_states: list[LogicalModeState] = Field(default_factory=list)


# ── Physical Architecture (PA) ─────────────────────────────────────────────


class PhysicalComponent(BaseModel):
    id: str
    name: str
    type: str
    logical_components: list[str] = Field(default_factory=list)


class PhysicalFunction(BaseModel):
    id: str
    name: str
    physical_component: str


class PhysicalLink(BaseModel):
    id: str
    name: str
    source: str
    target: str


class DesignedCapability(BaseModel):
    id: str
    name: str
    involved_functions: list[str] = Field(default_factory=list)
    involved_chains: list[str] = Field(default_factory=list)


class PhysicalFunctionalChain(BaseModel):
    id: str
    name: str
    function_refs: list[str] = Field(default_factory=list)
    exchange_refs: list[str] = Field(default_factory=list)


class DesignScenario(BaseModel):
    id: str
    name: str
    steps: list[ScenarioStep] = Field(default_factory=list)


class PhysicalFunctionalExchange(BaseModel):
    id: str
    name: str
    source_function: str
    target_function: str
    exchanged_items: list[str] = Field(default_factory=list)


class PhysicalExchangedItem(BaseModel):
    id: str
    name: str
    description: str = ""


class PhysicalComponentExchange(BaseModel):
    id: str
    name: str
    source_component: str
    target_component: str


class HostingComponent(BaseModel):
    id: str
    name: str
    hosted_components: list[str] = Field(default_factory=list)


class DesignedInterface(BaseModel):
    id: str
    name: str
    component_exchange_ref: str = ""
    exchange_items: list[str] = Field(default_factory=list)


class PhysicalModeState(BaseModel):
    id: str
    name: str
    type: str = "State"
    transitions: list[dict] = Field(default_factory=list)


class PhysicalArchitectureLayer(BaseModel):
    components: list[PhysicalComponent] = Field(default_factory=list)
    functions: list[PhysicalFunction] = Field(default_factory=list)
    links: list[PhysicalLink] = Field(default_factory=list)
    designed_capabilities: list[DesignedCapability] = Field(default_factory=list)
    functional_chains: list[PhysicalFunctionalChain] = Field(default_factory=list)
    design_scenarios: list[DesignScenario] = Field(default_factory=list)
    functional_exchanges: list[PhysicalFunctionalExchange] = Field(default_factory=list)
    exchanged_items: list[PhysicalExchangedItem] = Field(default_factory=list)
    component_exchanges: list[PhysicalComponentExchange] = Field(default_factory=list)
    hosting_components: list[HostingComponent] = Field(default_factory=list)
    interfaces: list[DesignedInterface] = Field(default_factory=list)
    modes_and_states: list[PhysicalModeState] = Field(default_factory=list)


# ── EPBS (End Product Breakdown Structure) ─────────────────────────────────


class ConfigurationItem(BaseModel):
    id: str
    name: str
    type: str = "HW"
    description: str = ""
    physical_component_refs: list[str] = Field(default_factory=list)


class PBSNode(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    ci_ref: str = ""


class EPBSLayer(BaseModel):
    configuration_items: list[ConfigurationItem] = Field(default_factory=list)
    pbs_structure: list[PBSNode] = Field(default_factory=list)
