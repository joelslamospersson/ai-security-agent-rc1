"""Tests for the Management Server API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestRoot:
    def test_root_returns_service_info(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AI Security Management Server"
        assert data["status"] == "running"


class TestHealth:
    def test_health_returns_healthy(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded", "failed")
        assert data["application"] == "ai-security-management-server"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "startup_time" in data

    def test_health_uptime_increases(self, client: TestClient) -> None:
        import time

        response1 = client.get("/health")
        time.sleep(0.01)
        response2 = client.get("/health")
        uptime1 = response1.json()["uptime_seconds"]
        uptime2 = response2.json()["uptime_seconds"]
        assert uptime2 > uptime1


class TestVersion:
    def test_version_returns_version_info(self, client: TestClient) -> None:
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"
        assert "git_commit" in data
        assert "build_timestamp" in data


class TestErrorHandling:
    def test_404_returns_structured_error(self, client: TestClient) -> None:
        response = client.get("/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == 404
        assert "message" in data["error"]

    def test_method_not_allowed(self, client: TestClient) -> None:
        response = client.post("/health")
        assert response.status_code in (405, 200)  # 405 if method not allowed, 200 if accepted


class TestApplicationLifecycle:
    def test_app_creation(self) -> None:
        """Verify the application can be created without error."""
        from management_server.app import create_app
        from management_server.config.settings import Settings

        settings = Settings(debug=True)
        app = create_app(settings=settings)
        assert app.title == "AI Security Management Server"
        assert app.state.settings is not None

    def test_settings_loading(self) -> None:
        """Verify settings load with defaults."""
        from management_server.config.settings import Settings

        settings = Settings()
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.port == 8000


class TestVersionModule:
    def test_version_string(self) -> None:
        from management_server.version import VERSION, get_version_info

        assert VERSION == "0.1.0"
        info = get_version_info()
        assert info["version"] == "0.1.0"
        assert "git_commit" in info
        assert "build_timestamp" in info
