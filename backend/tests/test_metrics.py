import asyncio
from typing import Any

import httpx
import pytest

from backend.app import main
from backend.app.metrics import MetricsStore
from backend.app.nat_engine import CGNATEngine
from backend.app.packet_simulator import PacketSimulator
from backend.app.policy_engine import PolicyEngine
from backend.app.route_table import RouteTable
from backend.app.subscriber_manager import SubscriberManager


@pytest.fixture(autouse=True)
def reset_metrics_pipeline() -> None:
    main.subscriber_manager = SubscriberManager()
    main.nat_engine = CGNATEngine()
    main.route_table = RouteTable()
    main.metrics_store = MetricsStore()
    main.policy_engine = PolicyEngine()
    main.packet_simulator = PacketSimulator(
        subscriber_manager=main.subscriber_manager,
        nat_engine=main.nat_engine,
        route_table=main.route_table,
        policy_engine=main.policy_engine,
        metrics_store=main.metrics_store,
    )


def request(method: str, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def packet_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "subscriber_id": "sub-1",
        "source_port": 50000,
        "destination_ip": "8.8.8.8",
        "destination_port": 443,
        "protocol": "TCP",
    }
    payload.update(overrides)
    return payload


def create_forwarding_state() -> None:
    main.subscriber_manager.create_subscriber("sub-1")
    main.route_table.add_route(
        prefix="0.0.0.0/0",
        interface="internet0",
        next_hop="203.0.113.1",
    )


def test_initial_metrics_are_zero() -> None:
    response = request("GET", "/metrics")

    assert response.status_code == 200
    assert response.json() == {
        "packets_total": 0,
        "packets_forwarded": 0,
        "packets_dropped": 0,
        "drops_by_reason": {},
        "nat_translations_active": 0,
        "subscribers_active": 0,
        "subscribers_blocked": 0,
        "routes_installed": 0,
    }


def test_forwarded_packet_increments_total_and_forwarded() -> None:
    create_forwarding_state()

    request("POST", "/simulate-packet", json=packet_payload())
    response = request("GET", "/metrics")

    assert response.json()["packets_total"] == 1
    assert response.json()["packets_forwarded"] == 1
    assert response.json()["packets_dropped"] == 0


def test_dropped_unknown_subscriber_increments_total_and_dropped() -> None:
    request("POST", "/simulate-packet", json=packet_payload())

    response = request("GET", "/metrics")

    assert response.json()["packets_total"] == 1
    assert response.json()["packets_forwarded"] == 0
    assert response.json()["packets_dropped"] == 1


def test_drops_by_reason_contains_subscriber_not_found() -> None:
    request("POST", "/simulate-packet", json=packet_payload())

    response = request("GET", "/metrics")

    assert response.json()["drops_by_reason"] == {"subscriber_not_found": 1}


def test_blocked_subscriber_drop_records_subscriber_blocked_reason() -> None:
    main.subscriber_manager.create_subscriber("sub-1")
    main.subscriber_manager.block_subscriber("sub-1")
    main.route_table.add_route(prefix="0.0.0.0/0", interface="internet0")

    request("POST", "/simulate-packet", json=packet_payload())

    response = request("GET", "/metrics")
    assert response.json()["packets_dropped"] == 1
    assert response.json()["drops_by_reason"] == {"subscriber_blocked": 1}


def test_metrics_reset_clears_packet_and_drop_counters() -> None:
    create_forwarding_state()
    request("POST", "/simulate-packet", json=packet_payload())
    request("POST", "/simulate-packet", json=packet_payload(subscriber_id="unknown"))

    reset_response = request("POST", "/metrics/reset")
    metrics_response = request("GET", "/metrics")

    assert reset_response.status_code == 200
    assert reset_response.json() == {"message": "Metrics reset"}
    assert metrics_response.json()["packets_total"] == 0
    assert metrics_response.json()["packets_forwarded"] == 0
    assert metrics_response.json()["packets_dropped"] == 0
    assert metrics_response.json()["drops_by_reason"] == {}


def test_metrics_snapshot_includes_active_nat_translation_count() -> None:
    create_forwarding_state()

    request("POST", "/simulate-packet", json=packet_payload())

    response = request("GET", "/metrics")
    assert response.json()["nat_translations_active"] == 1


def test_metrics_snapshot_includes_active_and_blocked_subscriber_counts() -> None:
    main.subscriber_manager.create_subscriber("active-sub")
    main.subscriber_manager.create_subscriber("blocked-sub")
    main.subscriber_manager.block_subscriber("blocked-sub")

    response = request("GET", "/metrics")

    assert response.json()["subscribers_active"] == 1
    assert response.json()["subscribers_blocked"] == 1


def test_metrics_snapshot_includes_installed_route_count() -> None:
    main.route_table.add_route(prefix="10.10.0.0/24", interface="access0")
    main.route_table.add_route(prefix="0.0.0.0/0", interface="internet0")

    response = request("GET", "/metrics")

    assert response.json()["routes_installed"] == 2
