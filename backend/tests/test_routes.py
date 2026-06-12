import asyncio

import httpx
import pytest

from backend.app import main
from backend.app.route_table import RouteTable


@pytest.fixture(autouse=True)
def reset_route_table() -> None:
    main.route_table = RouteTable()


def request(method: str, path: str, json: dict[str, str] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_add_route() -> None:
    response = request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access0"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "prefix": "10.10.0.0/24",
        "next_hop": None,
        "interface": "access0",
    }


def test_list_routes() -> None:
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access0"},
    )
    request(
        "POST",
        "/routes",
        json={
            "prefix": "0.0.0.0/0",
            "next_hop": "203.0.113.1",
            "interface": "internet0",
        },
    )

    response = request("GET", "/routes")

    assert response.status_code == 200
    assert response.json() == [
        {
            "prefix": "10.10.0.0/24",
            "next_hop": None,
            "interface": "access0",
        },
        {
            "prefix": "0.0.0.0/0",
            "next_hop": "203.0.113.1",
            "interface": "internet0",
        },
    ]


def test_duplicate_route_returns_400() -> None:
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access0"},
    )

    response = request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access1"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Route already exists"}


def test_delete_route() -> None:
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access0"},
    )

    response = request("DELETE", "/routes/10.10.0.0/24")

    assert response.status_code == 200
    assert response.json() == {"message": "Route deleted"}
    assert request("GET", "/routes").json() == []


def test_delete_unknown_route_returns_404() -> None:
    response = request("DELETE", "/routes/10.10.0.0/24")

    assert response.status_code == 404
    assert response.json() == {"detail": "Route not found"}


def test_lookup_returns_matching_route() -> None:
    request(
        "POST",
        "/routes",
        json={
            "prefix": "10.10.0.0/24",
            "next_hop": "192.0.2.1",
            "interface": "access0",
        },
    )

    response = request("GET", "/routes/lookup/10.10.0.12")

    assert response.status_code == 200
    assert response.json() == {
        "destination_ip": "10.10.0.12",
        "matched_prefix": "10.10.0.0/24",
        "next_hop": "192.0.2.1",
        "interface": "access0",
    }


def test_longest_prefix_match_chooses_most_specific_route() -> None:
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/16", "interface": "core0"},
    )
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.1.0/24", "interface": "access1"},
    )
    request(
        "POST",
        "/routes",
        json={"prefix": "0.0.0.0/0", "interface": "internet0"},
    )

    response = request("GET", "/routes/lookup/10.10.1.5")

    assert response.status_code == 200
    assert response.json()["matched_prefix"] == "10.10.1.0/24"
    assert response.json()["interface"] == "access1"


def test_lookup_without_matching_route_returns_404() -> None:
    request(
        "POST",
        "/routes",
        json={"prefix": "10.10.0.0/24", "interface": "access0"},
    )

    response = request("GET", "/routes/lookup/192.0.2.10")

    assert response.status_code == 404
    assert response.json() == {"detail": "No matching route found"}


def test_invalid_prefix_returns_400() -> None:
    response = request(
        "POST",
        "/routes",
        json={"prefix": "not-a-prefix", "interface": "access0"},
    )

    assert response.status_code == 400
    assert "not-a-prefix" in response.json()["detail"]


def test_invalid_destination_ip_returns_400() -> None:
    response = request("GET", "/routes/lookup/not-an-ip")

    assert response.status_code == 400
    assert "not-an-ip" in response.json()["detail"]
