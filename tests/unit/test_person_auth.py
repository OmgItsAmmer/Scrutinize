import pytest
from sqlmodel import select

from app.models.user import User


def test_google_signup_login_and_default_project(client, session):
    # Register/login first time via Google auth
    response = client.post("/v2/auth/google", json={"id_token": "mock_token_google-user@example.com"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify default project got created
    projects = client.get("/v2/projects", headers=headers)
    assert projects.status_code == 200
    assert len(projects.json()["projects"]) == 1
    assert projects.json()["projects"][0]["name"] == "My First Project"
    assert projects.json()["projects"][0]["role"] == "owner"

    # Login second time via Google auth
    response_login = client.post("/v2/auth/google", json={"id_token": "mock_token_google-user@example.com"})
    assert response_login.status_code == 200
    token_login = response_login.json()["access_token"]
    headers_login = {"Authorization": f"Bearer {token_login}"}

    # Verify no duplicate project got created
    projects_login = client.get("/v2/projects", headers=headers_login)
    assert projects_login.status_code == 200
    assert len(projects_login.json()["projects"]) == 1


def test_legacy_endpoints_are_disabled(client):
    signup = client.post("/v2/auth/signup", json={"email": "person@example.com", "password": "password123"})
    assert signup.status_code == 400
    assert "Password authentication is disabled" in signup.json()["detail"]

    verify = client.post("/v2/auth/verify", json={"email": "person@example.com", "otp": "123456"})
    assert verify.status_code == 400
    assert "Password authentication is disabled" in verify.json()["detail"]

    login = client.post("/v2/auth/login", json={"email": "person@example.com", "password": "password123"})
    assert login.status_code == 400
    assert "Password authentication is disabled" in login.json()["detail"]


def test_project_membership_blocks_cross_tenant_access(client, session):
    tokens = []
    project_ids = []
    for email in ("one@example.com", "two@example.com"):
        token = client.post("/v2/auth/google", json={"id_token": f"mock_token_{email}"}).json()["access_token"]
        tokens.append(token)
        project_ids.append(client.get("/v2/projects", headers={"Authorization": f"Bearer {token}"}).json()["projects"][0]["project_id"])

    response = client.post(
        "/v2/projects/files",
        headers={"Authorization": f"Bearer {tokens[0]}", "X-Project-Id": project_ids[1]},
        files={"file": ("note.txt", b"private", "text/plain")},
    )
    assert response.status_code == 403

