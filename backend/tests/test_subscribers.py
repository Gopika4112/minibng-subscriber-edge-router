import asyncio

import httpx
import pytest

from backend.app import main
from backend.app.subscriber_manager import SubscriberManager


@pytest.fixture(autouse=True)
def reset_subscriber_manager() -> None:
    main.subscriber_manager = SubscriberManager()


def request(method: str, path: str, json: dict[str, str] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json)

    return asyncio.run(send())


def test_create_subscriber() -> None:
    response = request(
        "POST",
        "/subscribers",
        json={"subscriber_id": "sub-1", "plan": "fiber"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "subscriber_id": "sub-1",
        "ip_address": "10.10.0.1",
        "plan": "fiber",
        "status": "ACTIVE",
    }


def test_list_subscribers() -> None:
    request("POST", "/subscribers", json={"subscriber_id": "sub-1"})
    request(
        "POST",
        "/subscribers",
        json={"subscriber_id": "sub-2", "plan": "premium"},
    )

    response = request("GET", "/subscribers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "subscriber_id": "sub-1",
            "ip_address": "10.10.0.1",
            "plan": "basic",
            "status": "ACTIVE",
        },
        {
            "subscriber_id": "sub-2",
            "ip_address": "10.10.0.2",
            "plan": "premium",
            "status": "ACTIVE",
        },
    ]


def test_duplicate_subscriber_returns_400() -> None:
    request("POST", "/subscribers", json={"subscriber_id": "sub-1"})

    response = request("POST", "/subscribers", json={"subscriber_id": "sub-1"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Subscriber already exists"}


def test_get_unknown_subscriber_returns_404() -> None:
    response = request("GET", "/subscribers/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Subscriber not found"}


def test_block_and_unblock_subscriber() -> None:
    request("POST", "/subscribers", json={"subscriber_id": "sub-1"})

    block_response = request("POST", "/subscribers/sub-1/block")
    assert block_response.status_code == 200
    assert block_response.json()["status"] == "BLOCKED"

    unblock_response = request("POST", "/subscribers/sub-1/unblock")
    assert unblock_response.status_code == 200
    assert unblock_response.json()["status"] == "ACTIVE"


def test_delete_subscriber_releases_ip() -> None:
    create_response = request("POST", "/subscribers", json={"subscriber_id": "sub-1"})
    ip_address = create_response.json()["ip_address"]

    delete_response = request("DELETE", "/subscribers/sub-1")

    assert delete_response.status_code == 200
    assert delete_response.json() == {"message": "Subscriber deleted"}
    assert main.subscriber_manager._ip_allocator.allocated_ips() == []
    assert ip_address == "10.10.0.1"


def test_deleted_subscriber_ip_can_be_reused() -> None:
    first_response = request("POST", "/subscribers", json={"subscriber_id": "sub-1"})
    first_ip = first_response.json()["ip_address"]
    request("DELETE", "/subscribers/sub-1")

    second_response = request("POST", "/subscribers", json={"subscriber_id": "sub-2"})

    assert second_response.status_code == 200
    assert second_response.json()["ip_address"] == first_ip
