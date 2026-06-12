from fastapi import FastAPI, HTTPException

from backend.app.metrics import MetricsStore
from backend.app.models import (
    MetricsSnapshot,
    NATCreate,
    NATTranslation,
    PacketSimulationRequest,
    PacketSimulationResponse,
    Policy,
    PolicyCreate,
    Route,
    RouteCreate,
    RouteLookupResult,
    Subscriber,
    SubscriberCreate,
)
from backend.app.nat_engine import CGNATEngine
from backend.app.packet_simulator import PacketSimulator
from backend.app.policy_engine import PolicyEngine
from backend.app.route_table import RouteTable
from backend.app.subscriber_manager import SubscriberManager

app = FastAPI(title="MiniBNG")
subscriber_manager = SubscriberManager()
route_table = RouteTable()
nat_engine = CGNATEngine()
metrics_store = MetricsStore()
policy_engine = PolicyEngine()
packet_simulator = PacketSimulator(
    subscriber_manager=subscriber_manager,
    nat_engine=nat_engine,
    route_table=route_table,
    policy_engine=policy_engine,
    metrics_store=metrics_store,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Return a basic service banner."""
    return {"message": "MiniBNG backend is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the backend health status."""
    return {"status": "ok"}


@app.post("/subscribers", response_model=Subscriber)
async def create_subscriber(request: SubscriberCreate) -> Subscriber:
    try:
        return subscriber_manager.create_subscriber(
            subscriber_id=request.subscriber_id,
            plan=request.plan,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/subscribers", response_model=list[Subscriber])
async def list_subscribers() -> list[Subscriber]:
    return subscriber_manager.list_subscribers()


@app.get("/subscribers/{subscriber_id}", response_model=Subscriber)
async def get_subscriber(subscriber_id: str) -> Subscriber:
    try:
        return subscriber_manager.get_subscriber(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found") from exc


@app.post("/subscribers/{subscriber_id}/block", response_model=Subscriber)
async def block_subscriber(subscriber_id: str) -> Subscriber:
    try:
        return subscriber_manager.block_subscriber(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found") from exc


@app.post("/subscribers/{subscriber_id}/unblock", response_model=Subscriber)
async def unblock_subscriber(subscriber_id: str) -> Subscriber:
    try:
        return subscriber_manager.unblock_subscriber(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found") from exc


@app.delete("/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str) -> dict[str, str]:
    try:
        subscriber_manager.delete_subscriber(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Subscriber not found") from exc

    return {"message": "Subscriber deleted"}


@app.post("/routes", response_model=Route)
async def add_route(request: RouteCreate) -> Route:
    try:
        return route_table.add_route(
            prefix=request.prefix,
            interface=request.interface,
            next_hop=request.next_hop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/routes", response_model=list[Route])
async def list_routes() -> list[Route]:
    return route_table.list_routes()


@app.get("/routes/lookup/{destination_ip}", response_model=RouteLookupResult)
async def lookup_route(destination_ip: str) -> RouteLookupResult:
    try:
        return route_table.lookup(destination_ip)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="No matching route found") from exc


@app.delete("/routes/{prefix:path}")
async def delete_route(prefix: str) -> dict[str, str]:
    try:
        route_table.delete_route(prefix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Route not found") from exc

    return {"message": "Route deleted"}


@app.post("/policies", response_model=Policy)
async def set_policy(request: PolicyCreate) -> Policy:
    try:
        return policy_engine.set_policy(
            subscriber_id=request.subscriber_id,
            allowed=request.allowed,
            allowed_protocols=request.allowed_protocols,
            allowed_destination_ports=request.allowed_destination_ports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/policies", response_model=list[Policy])
async def list_policies() -> list[Policy]:
    return policy_engine.list_policies()


@app.get("/policies/{subscriber_id}", response_model=Policy)
async def get_policy(subscriber_id: str) -> Policy:
    try:
        return policy_engine.get_policy(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Policy not found") from exc


@app.delete("/policies/{subscriber_id}")
async def delete_policy(subscriber_id: str) -> dict[str, str]:
    try:
        policy_engine.delete_policy(subscriber_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Policy not found") from exc

    return {"message": "Policy deleted"}


@app.post("/nat", response_model=NATTranslation)
async def create_nat_translation(request: NATCreate) -> NATTranslation:
    try:
        return nat_engine.create_translation(
            private_ip=request.private_ip,
            private_port=request.private_port,
            destination_ip=request.destination_ip,
            destination_port=request.destination_port,
            protocol=request.protocol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc


@app.get("/nat", response_model=list[NATTranslation])
async def list_nat_translations() -> list[NATTranslation]:
    return nat_engine.list_translations()


@app.delete("/nat")
async def clear_nat_table() -> dict[str, str]:
    nat_engine.clear()
    return {"message": "NAT table cleared"}


@app.get("/nat/count")
async def get_nat_count() -> dict[str, int]:
    return {"active_translations": nat_engine.active_count()}


@app.delete("/nat/{public_ip}/{public_port}/{protocol}")
async def delete_nat_translation(
    public_ip: str,
    public_port: int,
    protocol: str,
) -> dict[str, str]:
    try:
        nat_engine.delete_translation(
            public_ip=public_ip,
            public_port=public_port,
            protocol=protocol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NAT translation not found") from exc

    return {"message": "NAT translation deleted"}


@app.post("/simulate-packet", response_model=PacketSimulationResponse)
async def simulate_packet(
    request: PacketSimulationRequest,
) -> PacketSimulationResponse:
    return packet_simulator.simulate(request)


@app.get("/metrics", response_model=MetricsSnapshot)
async def get_metrics() -> MetricsSnapshot:
    subscribers = subscriber_manager.list_subscribers()
    subscribers_active = sum(1 for subscriber in subscribers if subscriber.status == "ACTIVE")
    subscribers_blocked = sum(1 for subscriber in subscribers if subscriber.status == "BLOCKED")

    return metrics_store.snapshot(
        nat_translations_active=nat_engine.active_count(),
        subscribers_active=subscribers_active,
        subscribers_blocked=subscribers_blocked,
        routes_installed=len(route_table.list_routes()),
    )


@app.post("/metrics/reset")
async def reset_metrics() -> dict[str, str]:
    metrics_store.reset()
    return {"message": "Metrics reset"}
