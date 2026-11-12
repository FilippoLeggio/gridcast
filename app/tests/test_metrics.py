from fastapi.testclient import TestClient

from gridcast.api.main import app


def test_requests_are_measured_by_route_template() -> None:
    with TestClient(app) as client:
        client.get("/healthz")
        body = client.get("/metrics").text
    assert (
        'gridcast_http_request_duration_seconds_count{method="GET",route="/healthz",status="200"}'
        in body
    )


def test_metrics_survive_a_missing_database() -> None:
    # Tests run without a database: the scrape must still succeed and say so.
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "gridcast_metrics_db_up 0.0" in response.text
