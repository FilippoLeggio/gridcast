import pytest
from fastapi.testclient import TestClient

from gridcast.api.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    # Nothing listens on port 1: the database is unreachable on purpose.
    monkeypatch.setenv("GRIDCAST_DATABASE_URL", "postgresql+psycopg://user:pass@127.0.0.1:1/none")
    with TestClient(app) as test_client:
        yield test_client


def test_liveness_does_not_need_the_database(client: TestClient) -> None:
    assert client.get("/healthz").status_code == 200


def test_readiness_fails_without_the_database(client: TestClient) -> None:
    assert client.get("/readyz").status_code == 503


def test_accuracy_rejects_an_invalid_window(client: TestClient) -> None:
    assert client.get("/accuracy", params={"days": 0}).status_code == 422
