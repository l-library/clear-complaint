import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ping_returns_envelope(client: TestClient) -> None:
    response = client.get("/api/ping")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "message": "ok", "data": {"status": "up"}}


def test_health_reports_service(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "up", "service": "clear-complaint-backend"}


def test_unknown_path_is_404_not_500(client: TestClient) -> None:
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {"code": 404, "message": "资源不存在", "data": None}
