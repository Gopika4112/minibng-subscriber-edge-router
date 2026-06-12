import asyncio

import httpx

from backend.app.main import app


def request(method: str, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path)

    return asyncio.run(send())


def test_root() -> None:
    response = request("GET", "/")

    assert response.status_code == 200
    assert response.json() == {"message": "MiniBNG backend is running"}


def test_health() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
