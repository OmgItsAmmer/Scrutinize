"""Unit tests for multi-tenant project API endpoints and search auth."""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# POST /v2/projects
# ---------------------------------------------------------------------------


class TestRegisterProject:
    def test_register_returns_201_with_keys(self, client):
        response = client.post(
            "/v2/projects",
            json={"name": "Test App", "settings": {}},
        )
        assert response.status_code == 201
        data = response.json()
        assert "project_id" in data
        assert data["api_key"].startswith("scrutinize_sk_")
        assert data["client_key"].startswith("scrutinize_pk_")

    def test_register_duplicate_name_returns_409(self, client):
        client.post("/v2/projects", json={"name": "Dup App", "settings": {}})
        response = client.post("/v2/projects", json={"name": "Dup App", "settings": {}})
        assert response.status_code == 409

    def test_register_with_settings_stores_overrides(self, client):
        response = client.post(
            "/v2/projects",
            json={
                "name": "Custom App",
                "settings": {
                    "gate_model": "custom-gate",
                    "confidence_threshold": 0.9,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Keys should still be properly prefixed regardless of settings
        assert data["api_key"].startswith("scrutinize_sk_")


# ---------------------------------------------------------------------------
# GET /v2/projects/me
# ---------------------------------------------------------------------------


class TestProjectInfo:
    def test_me_returns_401_on_invalid_key(self, client):
        response = client.get(
            "/v2/projects/me",
            headers={"X-Project-Key": "scrutinize_sk_invalid_key_xyz"},
        )
        assert response.status_code == 401

    def test_me_returns_project_info_on_valid_key(self, client):
        # Register a project first
        reg = client.post(
            "/v2/projects",
            json={"name": "Info Test App", "settings": {"gate_model": "my-model"}},
        )
        assert reg.status_code == 201
        admin_key = reg.json()["api_key"]

        response = client.get(
            "/v2/projects/me",
            headers={"X-Project-Key": admin_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Info Test App"
        assert "project_id" in data


# ---------------------------------------------------------------------------
# POST /v2/search — auth behaviour
# ---------------------------------------------------------------------------


class TestSearchAuth:
    def test_search_with_invalid_client_key_returns_401(self, client):
        response = client.post(
            "/v2/search",
            json={"query": "hello"},
            headers={"X-Project-Key": "scrutinize_pk_invalid_key_xyz"},
        )
        assert response.status_code == 401

    def test_search_with_valid_client_key_resolves_project_context(self, client):
        """Valid client_key should resolve project context without returning 401."""
        # Register project to get a real key
        reg = client.post(
            "/v2/projects",
            json={"name": "Search Test App", "settings": {}},
        )
        assert reg.status_code == 201
        client_key = reg.json()["client_key"]

        # Mock the orchestrator so we don't need a real LLM
        from app.core.deps import get_pipeline_orchestrator
        from app.schemas.v2.search import SearchV2Response, SearchV2Route

        mock_orch = MagicMock()
        mock_orch.search.return_value = SearchV2Response(
            query="hello",
            rewritten_query="hello",
            route=SearchV2Route.GENERIC,
            gate_reason="test",
            answer="Hi!",
            sources=[],
            attempts=1,
            conversation={"messages": []},
        )
        client.app.dependency_overrides[get_pipeline_orchestrator] = lambda: mock_orch

        response = client.post(
            "/v2/search",
            json={"query": "hello"},
            headers={"X-Project-Key": client_key},
        )
        client.app.dependency_overrides.pop(get_pipeline_orchestrator, None)

        # Should not be 401 — project was resolved correctly
        assert response.status_code == 200
        # The orchestrator was called with project_ctx
        mock_orch.search.assert_called_once()
        call_kwargs = mock_orch.search.call_args.kwargs
        assert call_kwargs["project_ctx"] is not None
        assert call_kwargs["project_ctx"].project_id is not None


# ---------------------------------------------------------------------------
# POST /v2/projects/mine — User Project Creation with Prompt Generation
# ---------------------------------------------------------------------------


class TestUserCreateProject:
    @patch("app.services.v2.prompt_generator.generate_project_prompts")
    def test_create_user_project_success_and_saves_settings(self, mock_gen, client, session):
        mock_gen.return_value = {
            "gate": "custom gate prompt for tests",
            "rewriter": "custom rewriter prompt for tests",
            "generic": "custom generic prompt for tests",
            "synthesis": "custom synthesis prompt for tests",
            "decision": "custom decision prompt for tests",
        }

        # Google auth signup/login
        login_res = client.post("/v2/auth/google", json={"id_token": "mock_token_creator@example.com"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create user project
        resp = client.post(
            "/v2/projects/mine",
            headers=headers,
            json={
                "name": "My Medical Summarizer",
                "description": "Medical clinical trials analysis. Only answer medical-related questions.",
                "settings": {}
            }
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Medical Summarizer"
        assert "project_id" in data
        project_id = data["project_id"]

        # Check DB to verify description and generated prompts are stored
        from app.models.project import Project
        from uuid import UUID
        db_project = session.get(Project, UUID(project_id))
        assert db_project is not None
        assert db_project.settings["description"] == "Medical clinical trials analysis. Only answer medical-related questions."
        assert db_project.settings["system_prompt_overrides"]["gate"] == "custom gate prompt for tests"
        assert db_project.settings["system_prompt_overrides"]["decision"] == "custom decision prompt for tests"


class TestUserDeleteProject:
    @patch("app.services.v2.prompt_generator.generate_project_prompts")
    @patch("app.services.project_deletion.FileDeletionService")
    def test_delete_user_project_success(self, mock_file_deletion_cls, mock_gen, client, session):
        mock_gen.return_value = {
            "gate": "gate",
            "rewriter": "rewriter",
            "generic": "generic",
            "synthesis": "synthesis",
            "decision": "decision",
        }
        mock_file_deletion_cls.return_value.delete_file.return_value = None

        owner_login = client.post("/v2/auth/google", json={"id_token": "mock_token_owner@example.com"})
        owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}

        create_res = client.post(
            "/v2/projects/mine",
            headers=owner_headers,
            json={"name": "Delete Me", "description": "Temporary project", "settings": {}},
        )
        project_id = create_res.json()["project_id"]

        delete_res = client.delete(f"/v2/projects/{project_id}", headers=owner_headers)
        assert delete_res.status_code == 204

        from app.models.project import Project
        from uuid import UUID

        assert session.get(Project, UUID(project_id)) is None

        list_res = client.get("/v2/projects", headers=owner_headers)
        assert all(item["project_id"] != project_id for item in list_res.json()["projects"])

    @patch("app.services.v2.prompt_generator.generate_project_prompts")
    def test_delete_user_project_forbidden_for_non_owner(self, mock_gen, client, session):
        mock_gen.return_value = {
            "gate": "gate",
            "rewriter": "rewriter",
            "generic": "generic",
            "synthesis": "synthesis",
            "decision": "decision",
        }

        owner_login = client.post("/v2/auth/google", json={"id_token": "mock_token_owner2@example.com"})
        owner_headers = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
        create_res = client.post(
            "/v2/projects/mine",
            headers=owner_headers,
            json={"name": "Protected Project", "description": "Owner only", "settings": {}},
        )
        project_id = create_res.json()["project_id"]

        stranger_login = client.post("/v2/auth/google", json={"id_token": "mock_token_stranger@example.com"})
        stranger_headers = {"Authorization": f"Bearer {stranger_login.json()['access_token']}"}

        delete_res = client.delete(f"/v2/projects/{project_id}", headers=stranger_headers)
        assert delete_res.status_code == 404

