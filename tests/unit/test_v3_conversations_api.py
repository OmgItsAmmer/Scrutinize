from uuid import UUID

from sqlmodel import select

from app.models.conversation import ChatConversation
from app.models.project import Project
from app.models.user import User


def _auth_headers(client, email: str) -> dict[str, str]:
    login_res = client.post("/v2/auth/google", json={"id_token": f"mock_token_{email}"})
    assert login_res.status_code == 200
    return {"Authorization": f"Bearer {login_res.json()['access_token']}"}


def _create_project(client, headers: dict[str, str], name: str) -> str:
    from unittest.mock import patch

    with patch("app.services.v2.prompt_generator.generate_project_prompts") as mock_gen:
        mock_gen.return_value = {
            "gate": "gate",
            "rewriter": "rewriter",
            "generic": "generic",
            "synthesis": "synthesis",
            "decision": "decision",
        }
        resp = client.post(
            "/v2/projects/mine",
            headers=headers,
            json={"name": name, "description": f"{name} description", "settings": {}},
        )
    assert resp.status_code == 201
    return resp.json()["project_id"]


class TestDeleteConversation:
    def test_delete_general_conversation_archives_it(self, client, session):
        headers = _auth_headers(client, "chat_delete@example.com")

        create_res = client.post(
            "/v3/conversations",
            headers=headers,
            json={"scope": "general", "project_id": None, "title": "News chat"},
        )
        assert create_res.status_code == 201
        conversation_id = create_res.json()["id"]

        delete_res = client.delete(f"/v3/conversations/{conversation_id}", headers=headers)
        assert delete_res.status_code == 204

        conversation = session.get(ChatConversation, UUID(conversation_id))
        assert conversation is not None
        assert conversation.archived_at is not None

        list_res = client.get("/v3/conversations?scope=general", headers=headers)
        assert all(item["id"] != conversation_id for item in list_res.json()["conversations"])

    def test_delete_project_conversation_requires_membership(self, client, session):
        owner_headers = _auth_headers(client, "project_owner@example.com")
        project_id = _create_project(client, owner_headers, "Shared Project")

        create_res = client.post(
            "/v3/conversations",
            headers=owner_headers,
            json={"scope": "project", "project_id": project_id, "title": "Project chat"},
        )
        conversation_id = create_res.json()["id"]

        stranger_headers = _auth_headers(client, "project_stranger@example.com")
        delete_res = client.delete(f"/v3/conversations/{conversation_id}", headers=stranger_headers)
        assert delete_res.status_code == 404

        conversation = session.get(ChatConversation, UUID(conversation_id))
        assert conversation is not None
        assert conversation.archived_at is None

    def test_delete_project_cascades_conversations(self, client, session):
        from unittest.mock import patch

        owner_headers = _auth_headers(client, "project_cascade@example.com")
        with patch("app.services.project_deletion.FileDeletionService"):
            project_id = _create_project(client, owner_headers, "Cascade Project")

        create_res = client.post(
            "/v3/conversations",
            headers=owner_headers,
            json={"scope": "project", "project_id": project_id, "title": "Cascade chat"},
        )
        conversation_id = create_res.json()["id"]

        with patch("app.services.project_deletion.FileDeletionService"):
            delete_res = client.delete(f"/v2/projects/{project_id}", headers=owner_headers)
        assert delete_res.status_code == 204

        assert session.get(Project, UUID(project_id)) is None
        assert session.get(ChatConversation, UUID(conversation_id)) is None

        owner = session.exec(select(User).where(User.email == "project_cascade@example.com")).first()
        assert owner is not None
        list_res = client.get("/v2/projects", headers=owner_headers)
        assert all(item["project_id"] != project_id for item in list_res.json()["projects"])
