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
def reset_policy_pipeline() -> None:
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


def test_setting_policy() -> None:
    response = request(
        "POST",
        "/policies",
        json={
            "subscriber_id": "sub-1",
            "allowed": True,
            "allowed_protocols": ["tcp"],
            "allowed_destination_ports": [80, 443],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "subscriber_id": "sub-1",
        "allowed": True,
        "allowed_protocols": ["TCP"],
        "allowed_destination_ports": [80, 443],
    }


def test_listing_policies() -> None:
    request("POST", "/policies", json={"subscriber_id": "sub-1"})
    request(
        "POST",
        "/policies",
        json={"subscriber_id": "sub-2", "allowed": False},
    )

    response = request("GET", "/policies")

    assert response.status_code == 200
    assert response.json() == [
        {
            "subscriber_id": "sub-1",
            "allowed": True,
            "allowed_protocols": None,
            "allowed_destination_ports": None,
        },
        {
            "subscriber_id": "sub-2",
            "allowed": False,
            "allowed_protocols": None,
            "allowed_destination_ports": None,
        },
    ]


def test_getting_policy() -> None:
    request("POST", "/policies", json={"subscriber_id": "sub-1", "allowed": False})

    response = request("GET", "/policies/sub-1")

    assert response.status_code == 200
    assert response.json()["subscriber_id"] == "sub-1"
    assert response.json()["allowed"] is False


def test_deleting_policy() -> None:
    request("POST", "/policies", json={"subscriber_id": "sub-1"})

    response = request("DELETE", "/policies/sub-1")

    assert response.status_code == 200
    assert response.json() == {"message": "Policy deleted"}
    assert request("GET", "/policies").json() == []


def test_getting_unknown_policy_returns_404() -> None:
    response = request("GET", "/policies/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Policy not found"}


def test_invalid_protocol_returns_400() -> None:
    response = request(
        "POST",
        "/policies",
        json={"subscriber_id": "sub-1", "allowed_protocols": ["ICMP"]},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported protocol"}


def test_invalid_port_returns_400() -> None:
    response = request(
        "POST",
        "/policies",
        json={"subscriber_id": "sub-1", "allowed_destination_ports": [70000]},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid port"}


def test_evaluate_default_allow_when_no_policy_exists() -> None:
    decision = main.policy_engine.evaluate(
        subscriber_id="sub-1",
        protocol="tcp",
        destination_port=443,
    )

    assert decision.allowed is True
    assert decision.reason == "No policy configured; default allow"


def test_policy_blocks_all_traffic() -> None:
    main.policy_engine.set_policy(subscriber_id="sub-1", allowed=False)

    decision = main.policy_engine.evaluate(
        subscriber_id="sub-1",
        protocol="TCP",
        destination_port=443,
    )

    assert decision.allowed is False
    assert decision.reason == "Subscriber policy blocks all traffic"


def test_protocol_restriction_blocks_unsupported_protocol_for_subscriber() -> None:
    main.policy_engine.set_policy(
        subscriber_id="sub-1",
        allowed_protocols=["TCP"],
    )

    decision = main.policy_engine.evaluate(
        subscriber_id="sub-1",
        protocol="UDP",
        destination_port=443,
    )

    assert decision.allowed is False
    assert decision.reason == "Protocol not allowed by policy"


def test_destination_port_restriction_blocks_unsupported_destination_port() -> None:
    main.policy_engine.set_policy(
        subscriber_id="sub-1",
        allowed_destination_ports=[443],
    )

    decision = main.policy_engine.evaluate(
        subscriber_id="sub-1",
        protocol="TCP",
        destination_port=80,
    )

    assert decision.allowed is False
    assert decision.reason == "Destination port not allowed by policy"


def test_allowed_policy_permits_traffic() -> None:
    main.policy_engine.set_policy(
        subscriber_id="sub-1",
        allowed_protocols=["TCP"],
        allowed_destination_ports=[443],
    )

    decision = main.policy_engine.evaluate(
        subscriber_id="sub-1",
        protocol="tcp",
        destination_port=443,
    )

    assert decision.allowed is True
    assert decision.reason == "Policy allows traffic"
