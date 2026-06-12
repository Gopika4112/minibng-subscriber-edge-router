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
def reset_packet_pipeline() -> None:
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


def create_active_subscriber_with_route() -> None:
    main.subscriber_manager.create_subscriber("sub-1")
    main.route_table.add_route(
        prefix="0.0.0.0/0",
        interface="internet0",
        next_hop="203.0.113.1",
    )


def test_active_subscriber_with_nat_and_matching_route_is_forwarded() -> None:
    create_active_subscriber_with_route()

    response = request("POST", "/simulate-packet", json=packet_payload())

    assert response.status_code == 200
    assert response.json()["decision"] == "FORWARDED"
    assert response.json()["trace"][-1] == {
        "step": "forwarding_decision",
        "status": "PASS",
        "reason": "Packet forwarded",
        "metadata": {},
    }


def test_unknown_subscriber_is_dropped_with_subscriber_lookup_fail() -> None:
    response = request("POST", "/simulate-packet", json=packet_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "DROPPED"
    assert body["original_source_ip"] is None
    assert body["trace"][0] == {
        "step": "subscriber_lookup",
        "status": "FAIL",
        "reason": "Subscriber not found",
        "metadata": {},
    }


def test_blocked_subscriber_is_dropped_with_status_fail() -> None:
    main.subscriber_manager.create_subscriber("sub-1")
    main.subscriber_manager.block_subscriber("sub-1")
    main.route_table.add_route(prefix="0.0.0.0/0", interface="internet0")

    response = request("POST", "/simulate-packet", json=packet_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "DROPPED"
    assert body["trace"][1]["step"] == "subscriber_status"
    assert body["trace"][1]["status"] == "FAIL"
    assert body["trace"][1]["reason"] == "Subscriber is blocked"


def test_active_subscriber_without_route_is_dropped_with_route_lookup_fail() -> None:
    main.subscriber_manager.create_subscriber("sub-1")

    response = request("POST", "/simulate-packet", json=packet_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "DROPPED"
    assert body["trace"][4] == {
        "step": "route_lookup",
        "status": "FAIL",
        "reason": "No matching route found",
        "metadata": {},
    }


def test_invalid_destination_ip_is_dropped_with_nat_translation_fail() -> None:
    create_active_subscriber_with_route()

    response = request(
        "POST",
        "/simulate-packet",
        json=packet_payload(destination_ip="not-an-ip"),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "DROPPED"
    assert body["trace"][3]["step"] == "nat_translation"
    assert body["trace"][3]["status"] == "FAIL"
    assert "not-an-ip" in body["trace"][3]["reason"]


def test_unsupported_protocol_is_dropped_with_policy_check_fail() -> None:
    create_active_subscriber_with_route()

    response = request(
        "POST",
        "/simulate-packet",
        json=packet_payload(protocol="ICMP"),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["decision"] == "DROPPED"
    assert body["trace"][2] == {
        "step": "policy_check",
        "status": "FAIL",
        "reason": "Unsupported protocol",
        "metadata": {},
    }


def test_repeated_same_packet_reuses_same_nat_mapping() -> None:
    create_active_subscriber_with_route()

    first_response = request("POST", "/simulate-packet", json=packet_payload())
    second_response = request("POST", "/simulate-packet", json=packet_payload())

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["translated_source_ip"] == "100.64.0.10"
    assert second_response.json()["translated_source_ip"] == "100.64.0.10"
    assert (
        first_response.json()["translated_source_port"]
        == second_response.json()["translated_source_port"]
    )
    assert main.nat_engine.active_count() == 1


def test_trace_contains_all_six_steps_in_order() -> None:
    create_active_subscriber_with_route()

    response = request("POST", "/simulate-packet", json=packet_payload())

    assert [step["step"] for step in response.json()["trace"]] == [
        "subscriber_lookup",
        "subscriber_status",
        "policy_check",
        "nat_translation",
        "route_lookup",
        "forwarding_decision",
    ]


def test_forwarded_response_includes_nat_and_route_details() -> None:
    create_active_subscriber_with_route()

    response = request("POST", "/simulate-packet", json=packet_payload())

    body = response.json()
    assert body["original_source_ip"] == "10.10.0.1"
    assert body["translated_source_ip"] == "100.64.0.10"
    assert body["translated_source_port"] == 30000
    assert body["outgoing_interface"] == "internet0"
    assert body["next_hop"] == "203.0.113.1"
    assert body["matched_prefix"] == "0.0.0.0/0"


def test_policy_block_causes_packet_drop() -> None:
    create_active_subscriber_with_route()
    main.policy_engine.set_policy(subscriber_id="sub-1", allowed=False)

    response = request("POST", "/simulate-packet", json=packet_payload())

    body = response.json()
    assert body["decision"] == "DROPPED"
    assert body["trace"][2] == {
        "step": "policy_check",
        "status": "FAIL",
        "reason": "Subscriber policy blocks all traffic",
        "metadata": {},
    }


def test_policy_block_increments_policy_blocked_drop_reason() -> None:
    create_active_subscriber_with_route()
    main.policy_engine.set_policy(subscriber_id="sub-1", allowed=False)

    request("POST", "/simulate-packet", json=packet_payload())

    assert main.metrics_store.drops_by_reason == {"policy_blocked": 1}


def test_nat_and_route_lookup_are_skipped_when_policy_blocks() -> None:
    create_active_subscriber_with_route()
    main.policy_engine.set_policy(subscriber_id="sub-1", allowed=False)

    response = request("POST", "/simulate-packet", json=packet_payload())

    trace = response.json()["trace"]
    assert trace[3]["step"] == "nat_translation"
    assert trace[3]["status"] == "SKIPPED"
    assert trace[4]["step"] == "route_lookup"
    assert trace[4]["status"] == "SKIPPED"
