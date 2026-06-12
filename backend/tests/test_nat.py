import asyncio
from typing import Any

import httpx
import pytest

from backend.app import main
from backend.app.nat_engine import CGNATEngine


@pytest.fixture(autouse=True)
def reset_nat_engine() -> None:
    main.nat_engine = CGNATEngine()


def request(method: str, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def nat_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "private_ip": "10.10.0.2",
        "private_port": 50000,
        "destination_ip": "8.8.8.8",
        "destination_port": 443,
        "protocol": "TCP",
    }
    payload.update(overrides)
    return payload


def test_create_nat_translation() -> None:
    response = request("POST", "/nat", json=nat_payload())

    assert response.status_code == 200
    assert response.json() == {
        "private_ip": "10.10.0.2",
        "private_port": 50000,
        "public_ip": "100.64.0.10",
        "public_port": 30000,
        "destination_ip": "8.8.8.8",
        "destination_port": 443,
        "protocol": "TCP",
        "state": "ACTIVE",
    }


def test_list_nat_translations() -> None:
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.2"))
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.3"))

    response = request("GET", "/nat")

    assert response.status_code == 200
    assert response.json() == [
        {
            "private_ip": "10.10.0.2",
            "private_port": 50000,
            "public_ip": "100.64.0.10",
            "public_port": 30000,
            "destination_ip": "8.8.8.8",
            "destination_port": 443,
            "protocol": "TCP",
            "state": "ACTIVE",
        },
        {
            "private_ip": "10.10.0.3",
            "private_port": 50000,
            "public_ip": "100.64.0.10",
            "public_port": 30001,
            "destination_ip": "8.8.8.8",
            "destination_port": 443,
            "protocol": "TCP",
            "state": "ACTIVE",
        },
    ]


def test_same_private_flow_reuses_existing_translation() -> None:
    first_response = request("POST", "/nat", json=nat_payload())
    second_response = request("POST", "/nat", json=nat_payload(protocol="tcp"))

    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert request("GET", "/nat/count").json() == {"active_translations": 1}


def test_different_private_flows_get_different_public_ports() -> None:
    first_response = request("POST", "/nat", json=nat_payload(private_ip="10.10.0.2"))
    second_response = request("POST", "/nat", json=nat_payload(private_ip="10.10.0.3"))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["public_port"] == 30000
    assert second_response.json()["public_port"] == 30001


def test_delete_nat_translation() -> None:
    create_response = request("POST", "/nat", json=nat_payload())
    translation = create_response.json()

    delete_response = request(
        "DELETE",
        f"/nat/{translation['public_ip']}/{translation['public_port']}/{translation['protocol']}",
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "NAT translation deleted"}
    assert request("GET", "/nat").json() == []


def test_deleting_unknown_nat_translation_returns_404() -> None:
    response = request("DELETE", "/nat/100.64.0.10/30000/TCP")

    assert response.status_code == 404
    assert response.json() == {"detail": "NAT translation not found"}


def test_clear_nat_table() -> None:
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.2"))
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.3"))

    response = request("DELETE", "/nat")

    assert response.status_code == 200
    assert response.json() == {"message": "NAT table cleared"}
    assert request("GET", "/nat").json() == []


def test_active_count() -> None:
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.2"))
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.3"))

    response = request("GET", "/nat/count")

    assert response.status_code == 200
    assert response.json() == {"active_translations": 2}


def test_invalid_private_ip_returns_400() -> None:
    response = request("POST", "/nat", json=nat_payload(private_ip="not-an-ip"))

    assert response.status_code == 400
    assert "not-an-ip" in response.json()["detail"]


def test_invalid_destination_ip_returns_400() -> None:
    response = request("POST", "/nat", json=nat_payload(destination_ip="not-an-ip"))

    assert response.status_code == 400
    assert "not-an-ip" in response.json()["detail"]


def test_invalid_private_port_returns_400() -> None:
    response = request("POST", "/nat", json=nat_payload(private_port=0))

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid port"}


def test_invalid_destination_port_returns_400() -> None:
    response = request("POST", "/nat", json=nat_payload(destination_port=70000))

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid port"}


def test_unsupported_protocol_returns_400() -> None:
    response = request("POST", "/nat", json=nat_payload(protocol="ICMP"))

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported protocol"}


def test_port_exhaustion_returns_507() -> None:
    main.nat_engine = CGNATEngine(
        public_ips=["100.64.0.10"],
        port_start=30000,
        port_end=30000,
    )
    request("POST", "/nat", json=nat_payload(private_ip="10.10.0.2"))

    response = request("POST", "/nat", json=nat_payload(private_ip="10.10.0.3"))

    assert response.status_code == 507
    assert response.json() == {"detail": "No available NAT ports"}
