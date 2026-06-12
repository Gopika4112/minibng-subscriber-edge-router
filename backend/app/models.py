from typing import Any

from pydantic import BaseModel, Field


class SubscriberCreate(BaseModel):
    """Request body for creating a subscriber session."""

    subscriber_id: str
    plan: str = "basic"


class Subscriber(BaseModel):
    """Subscriber session state tracked by MiniBNG."""

    subscriber_id: str
    ip_address: str
    plan: str
    status: str


class RouteCreate(BaseModel):
    """Request body for adding a static route."""

    prefix: str
    next_hop: str | None = None
    interface: str


class Route(BaseModel):
    """Static route stored by MiniBNG."""

    prefix: str
    next_hop: str | None
    interface: str


class RouteLookupResult(BaseModel):
    """Result of a longest prefix match route lookup."""

    destination_ip: str
    matched_prefix: str
    next_hop: str | None
    interface: str


class NATCreate(BaseModel):
    """Request body for creating a CGNAT translation."""

    private_ip: str
    private_port: int
    destination_ip: str
    destination_port: int
    protocol: str = "TCP"


class NATTranslation(BaseModel):
    """Active CGNAT translation entry."""

    private_ip: str
    private_port: int
    public_ip: str
    public_port: int
    destination_ip: str
    destination_port: int
    protocol: str
    state: str


class PacketSimulationRequest(BaseModel):
    """Input packet fields for the explainable forwarding simulation."""

    subscriber_id: str
    source_port: int
    destination_ip: str
    destination_port: int
    protocol: str = "TCP"


class TraceStep(BaseModel):
    """One explainable step in the packet decision pipeline."""

    step: str
    status: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PacketSimulationResponse(BaseModel):
    """Final packet decision with NAT, route, and trace details."""

    decision: str
    subscriber_id: str
    original_source_ip: str | None
    translated_source_ip: str | None
    translated_source_port: int | None
    destination_ip: str
    destination_port: int
    protocol: str
    outgoing_interface: str | None
    next_hop: str | None
    matched_prefix: str | None
    trace: list[TraceStep]


class MetricsSnapshot(BaseModel):
    """Router-style counters and current control-plane object counts."""

    packets_total: int
    packets_forwarded: int
    packets_dropped: int
    drops_by_reason: dict[str, int]
    nat_translations_active: int
    subscribers_active: int
    subscribers_blocked: int
    routes_installed: int


class PolicyCreate(BaseModel):
    """Request body for setting subscriber traffic policy."""

    subscriber_id: str
    allowed: bool = True
    allowed_protocols: list[str] | None = None
    allowed_destination_ports: list[int] | None = None


class Policy(BaseModel):
    """Subscriber-aware policy applied before NAT and route lookup."""

    subscriber_id: str
    allowed: bool
    allowed_protocols: list[str] | None
    allowed_destination_ports: list[int] | None


class PolicyDecision(BaseModel):
    """Result of evaluating a subscriber policy for a packet."""

    allowed: bool
    reason: str
