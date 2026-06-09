from fastapi.testclient import TestClient
from pathlib import Path
from uuid import uuid4

from app.main import create_app


def make_db_path() -> Path:
    base_dir = Path(".tmp_testdata")
    base_dir.mkdir(exist_ok=True)
    return base_dir / f"{uuid4().hex}.db"


def test_health_endpoint_returns_ok():
    client = TestClient(create_app(database_path=make_db_path()))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_snapshot_and_theme_endpoints_exist():
    client = TestClient(create_app(database_path=make_db_path()))
    assert client.get("/api/snapshots").status_code == 200
    assert client.get("/api/themes").status_code == 200


def test_root_serves_dashboard_page():
    client = TestClient(create_app(database_path=make_db_path()))
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_theme_mapping_api_upserts_and_lists_mapping():
    client = TestClient(create_app(database_path=make_db_path()))
    response = client.post(
        "/api/themes",
        json={
            "symbol": "NVDA",
            "theme": "AI基建",
            "display_name": "NVIDIA",
            "color": "#22d3ee",
            "enabled": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["symbol"] == "NVDA"

    list_response = client.get("/api/themes")
    assert list_response.status_code == 200
    assert any(item["theme"] == "AI基建" for item in list_response.json())


def test_category_api_lists_definitions_and_upserts_override():
    client = TestClient(create_app(database_path=make_db_path()))

    categories_response = client.get("/api/categories")
    assert categories_response.status_code == 200
    assert any(item["category_code"] == "semiconductor" for item in categories_response.json())

    response = client.post(
        "/api/category-overrides",
        json={
            "symbol": "nvda",
            "market": "us",
            "sector_code": "semiconductor",
            "industry_code": "ai_chip",
            "theme_code": "ai",
            "reason": "manual test",
            "enabled": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["symbol"] == "NVDA"
    assert response.json()["sector_name"] == "半导体"
    assert response.json()["category_source"] == "manual"

    list_response = client.get("/api/category-overrides")
    assert list_response.status_code == 200
    assert list_response.json()[0]["theme_name"] == "AI"


def test_category_api_rejects_wrong_category_type():
    client = TestClient(create_app(database_path=make_db_path()))

    response = client.post(
        "/api/category-overrides",
        json={
            "symbol": "NVDA",
            "market": "US",
            "sector_code": "ai",
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert "sector_code" in response.json()["detail"]


def test_dashboard_returns_empty_shape_without_snapshots():
    client = TestClient(create_app(database_path=make_db_path()))
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.json()["summary"] == {}
    assert response.json()["positions"] == []


def test_sync_endpoint_fails_gracefully_without_opend():
    client = TestClient(create_app(database_path=make_db_path()))
    response = client.post("/api/sync/run")
    assert response.status_code == 502
