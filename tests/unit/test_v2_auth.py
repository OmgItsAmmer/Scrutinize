"""Unit tests for the project Login/Signup auth system."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestProjectAuth:
    def test_signup_project_success(self, client):
        response = client.post(
            "/v2/projects/signup",
            json={"name": "my-cool-project", "password": "supersecretpassword", "settings": {}},
        )
        assert response.status_code == 201
        data = response.json()
        assert "project_id" in data
        assert data["api_key"].startswith("scrutinize_sk_")
        assert data["client_key"].startswith("scrutinize_pk_")

    def test_signup_duplicate_name_returns_409(self, client):
        client.post(
            "/v2/projects/signup",
            json={"name": "dup-project", "password": "password123", "settings": {}},
        )
        response = client.post(
            "/v2/projects/signup",
            json={"name": "dup-project", "password": "differentpassword", "settings": {}},
        )
        assert response.status_code == 409

    def test_login_success(self, client):
        # Register first
        client.post(
            "/v2/projects/signup",
            json={"name": "login-project", "password": "correctpassword", "settings": {}},
        )

        # Login
        response = client.post(
            "/v2/projects/login",
            json={"name": "login-project", "password": "correctpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert data["api_key"].startswith("scrutinize_sk_")
        assert data["client_key"].startswith("scrutinize_pk_")

    def test_login_invalid_password(self, client):
        client.post(
            "/v2/projects/signup",
            json={"name": "wrong-pw-project", "password": "correctpassword", "settings": {}},
        )

        response = client.post(
            "/v2/projects/login",
            json={"name": "wrong-pw-project", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid project name or password."

    def test_login_nonexistent_project(self, client):
        response = client.post(
            "/v2/projects/login",
            json={"name": "nonexistent-project", "password": "somepassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid project name or password."

    def test_library_endpoint_requires_auth(self, client):
        # Without X-Project-Key, lists all (for backwards compatibility), but with key filters/authenticates
        response = client.get("/library", headers={"X-Project-Key": "scrutinize_sk_invalid"})
        assert response.status_code == 401

    def test_library_delete_unauthorized_project(self, client):
        # Create Project A and Project B
        reg_a = client.post(
            "/v2/projects/signup",
            json={"name": "project-a", "password": "passwordA", "settings": {}},
        ).json()
        reg_b = client.post(
            "/v2/projects/signup",
            json={"name": "project-b", "password": "passwordB", "settings": {}},
        ).json()

        key_a = reg_a["api_key"]
        key_b = reg_b["api_key"]

        # Mock database file query to simulate owned vs unowned file
        from uuid import UUID
        file_id = uuid4()
        mock_file = MagicMock()
        mock_file.id = file_id
        mock_file.project_id = UUID(reg_a["project_id"])

        from app.core.deps import get_job_orchestrator

        mock_orch = MagicMock()
        mock_orch.get_file.return_value = mock_file
        client.app.dependency_overrides[get_job_orchestrator] = lambda: mock_orch

        with patch("app.api.library.FileDeletionService") as mock_del_svc_cls:
            # Attempt to delete file of Project A using Project B's key
            resp = client.delete(f"/library/{file_id}", headers={"X-Project-Key": key_b})
            assert resp.status_code == 403
            assert resp.json()["detail"] == "Access denied: File does not belong to your project."

            # Delete file of Project A using Project A's key should succeed
            resp_ok = client.delete(f"/library/{file_id}", headers={"X-Project-Key": key_a})
            assert resp_ok.status_code == 200

        client.app.dependency_overrides.pop(get_job_orchestrator, None)

