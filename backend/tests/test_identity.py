"""Isolated provider-contract tests. No real Supabase project or email is used."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.core.security import current_user
from app.db.session import get_db
from app.main import app
from app.services.identity_service import get_identity_service, token_digest

ADMIN = "00000000-0000-4000-8000-000000000001"
PASSWORD = "isolated-test-passphrase"
NOW = datetime.now(timezone.utc).isoformat()


class Providers:
    def __init__(self):
        self.tables = {"profiles": [{"id": ADMIN, "email": "owner@example.org", "display_name": "Test Owner",
            "role": "SYSTEM_ADMIN", "status": "active", "project_ids": [], "invitation_delivery": "not_sent"}],
            "sessions": [], "auth_audit": []}
        self.users = {ADMIN: {"id": ADMIN, "email": "owner@example.org", "email_confirmed_at": NOW}}
        self.passwords = {ADMIN: PASSWORD}
        self.tokens = {}
        self.buckets = {}
        self.emails = []
        self.mail_status = 201
        self.requests = []

    def handle(self, request):
        import json
        data = json.loads(request.content) if request.content else {}
        self.requests.append((request.method, request.url.path, data, dict(request.headers)))
        def respond(body=None, status=200):
            return httpx.Response(status, json=body)
        path = request.url.path
        if request.url.host == "api.brevo.com":
            self.emails.append(data)
            return respond({"messageId": "isolated"}, self.mail_status)
        if path == "/auth/v1/token":
            user = next((u for u in self.users.values() if u["email"] == data["email"]), None)
            if not user or self.passwords.get(user["id"]) != data["password"]:
                return respond({"msg": "private provider error"}, 400)
            return respond({"user": user, "access_token": "provider-only", "refresh_token": "never-exposed"})
        if path == "/auth/v1/admin/generate_link":
            user = next((u for u in self.users.values() if u["email"] == data["email"]), None)
            if not user:
                user = {"id": str(uuid4()), "email": data["email"], "email_confirmed_at": None}
                self.users[user["id"]] = user
            token = uuid4().hex + uuid4().hex
            self.tokens[token] = (user["id"], data["type"])
            return respond({**user, "hashed_token": token, "verification_type": data["type"]})
        if path.startswith("/auth/v1/admin/users/"):
            return respond(self.users[path.rsplit("/", 1)[1]])
        if path == "/auth/v1/verify":
            value = self.tokens.pop(data["token_hash"], None)
            if not value or value[1] != data["type"]:
                return respond({}, 403)
            user = self.users[value[0]]
            user["email_confirmed_at"] = NOW
            return respond({"user": user, "access_token": "verified:" + user["id"]})
        if path == "/auth/v1/user":
            uid = request.headers["authorization"].removeprefix("Bearer verified:")
            self.passwords[uid] = data["password"]
            return respond(self.users[uid])
        if path == "/rest/v1/rpc/landguard_auth_rate_limit":
            bucket = data["p_bucket"]
            self.buckets[bucket] = self.buckets.get(bucket, 0) + 1
            return respond(self.buckets[bucket] <= data["p_limit"])
        if path.startswith("/rest/v1/landguard_"):
            table = path.removeprefix("/rest/v1/landguard_")
            rows = self.tables[table]
            if request.method == "POST":
                rows.append(deepcopy(data))
                return respond([data], 201)
            selected = rows[:]
            for key, value in request.url.params.items():
                if value.startswith("eq."):
                    selected = [row for row in selected if str(row.get(key)) == value[3:]]
            if request.method == "PATCH":
                for row in selected:
                    row.update(data)
            if request.method == "DELETE":
                self.tables[table] = [row for row in rows if row not in selected]
            return respond(selected)
        raise AssertionError("Unexpected provider path: " + path)


@pytest.fixture
def identity_client(database, monkeypatch):
    providers = Providers()
    original_client = httpx.Client
    transport = httpx.MockTransport(providers.handle)
    monkeypatch.setattr("app.services.identity_service.httpx.Client",
                        lambda **kw: original_client(transport=transport, **kw))
    monkeypatch.setattr(settings, "supabase_url", "https://isolated.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", SecretStr("sb_secret_isolated"))
    monkeypatch.setattr(settings, "brevo_api_key", SecretStr("isolated-brevo-key"))
    monkeypatch.setattr(settings, "brevo_sender_email", "sender@example.org")
    def db_override():
        with database() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    try:
        with TestClient(app, headers={"X-LandGuard-Request": "1"}) as client:
            yield client, providers
    finally:
        app.dependency_overrides.clear()


def login(client, email="owner@example.org", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def invite(client, **values):
    return client.post("/api/v1/auth/invitations", json={"email": "officer@example.org",
        "display_name": "District Colleague", "role": "DISTRICT_OFFICER",
        "state": "Maharashtra", "district": "Pune", **values})


def accept(client, providers, password=PASSWORD):
    token = next(reversed(providers.tokens))
    return client.post("/api/v1/auth/accept-invitation",
        json={"token_hash": token, "type": providers.tokens[token][1], "password": password})


def test_cookie_session_is_hashed_and_revoked(identity_client):
    client, providers = identity_client
    result = login(client, email=" OWNER@EXAMPLE.ORG ")
    assert result.status_code == 200
    assert set(result.json()) == {"user"}
    assert "HttpOnly" in result.headers["set-cookie"] and "SameSite=lax" in result.headers["set-cookie"]
    raw = client.cookies.get("landguard_session")
    assert providers.tables["sessions"][0]["token_hash"] == token_digest(raw)
    assert raw not in str(providers.tables)
    assert client.get("/api/v1/auth/me").json()["role"] == "SYSTEM_ADMIN"
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("landguard_session", raw)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert not providers.tables["sessions"]


def test_no_demo_login_or_client_assigned_roles(identity_client):
    client, providers = identity_client
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "LandGuard@2026"}).status_code == 422
    bad = login(client, password="incorrect")
    assert bad.status_code == 401
    assert bad.json()["code"] == "INVALID_LOGIN"
    assert "provider error" not in bad.text
    assert client.post("/api/v1/auth/login", json={"email": "owner@example.org", "password": PASSWORD, "role": "SYSTEM_ADMIN"}).status_code == 422
    assert not providers.tables["sessions"]


@pytest.mark.parametrize("path", ["/projects", "/projects/TEST01", "/dashboard/summary",
    "/dashboard/district-summary", "/dashboard/stage-distribution", "/dashboard/operational-risks",
    "/map-data", "/alerts", "/review-notices", "/model/status", "/auth/users"])
def test_every_workspace_read_requires_session(identity_client, path):
    client, _ = identity_client
    assert client.get("/api/v1" + path).status_code == 401
    assert client.post("/api/v1/projects/TEST01/predict").status_code == 401


def test_csrf_and_https_configuration(identity_client):
    client, providers = identity_client
    assert client.post("/api/v1/auth/login", json={}, headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-LandGuard-Request": ""}).status_code == 403
    assert not providers.requests
    assert Settings(_env_file=None, public_app_url="https://portal.example.org").cookie_secure
    with pytest.raises(ValidationError):
        Settings(_env_file=None, public_app_url="http://portal.example.org")


def test_invitation_activation_and_single_use(identity_client):
    client, providers = identity_client
    assert login(client).status_code == 200
    result = invite(client)
    assert result.status_code == 201
    assert result.json()["status"] == "invited"
    assert result.json()["invitation_delivery"] == "accepted_by_brevo"
    token = next(iter(providers.tokens))
    assert token not in result.text
    assert "/accept-invitation#token_hash=" in providers.emails[0]["htmlContent"]
    assert PASSWORD not in str(providers.emails)
    assert accept(client, providers).status_code == 200
    replay = client.post("/api/v1/auth/accept-invitation", json={"token_hash": token, "type": "invite", "password": PASSWORD})
    assert replay.status_code == 400
    assert replay.json()["code"] == "INVITATION_INVALID"
    assert login(client, "officer@example.org").status_code == 200
    assert client.get("/api/v1/auth/me").json()["role"] == "DISTRICT_OFFICER"
    assert client.get("/api/v1/auth/users").status_code == 403
    assert invite(client, email="unapproved@example.org").status_code == 403


def test_mail_failure_can_be_resent_without_duplicate_user(identity_client):
    client, providers = identity_client
    login(client)
    providers.mail_status = 500
    result = invite(client)
    assert result.status_code == 502
    pending = providers.tables["profiles"][1]
    assert pending["invitation_delivery"] == "failed" and pending["status"] == "invited"
    providers.mail_status = 201
    result = client.post("/api/v1/auth/users/" + pending["id"] + "/resend")
    assert result.status_code == 200
    assert len(providers.tables["profiles"]) == 2
    assert result.json()["invitation_delivery"] == "accepted_by_brevo"


def test_missing_mail_configuration_creates_no_user(identity_client, monkeypatch):
    client, providers = identity_client
    login(client)
    monkeypatch.setattr(settings, "brevo_api_key", SecretStr(""))
    assert invite(client).json()["code"] == "MAIL_NOT_CONFIGURED"
    assert len(providers.users) == 1


def test_scope_and_invitation_validation(identity_client):
    client, providers = identity_client
    login(client)
    assert invite(client, state="").status_code == 422
    assert invite(client, district="").status_code == 422
    assert invite(client, role="IMPLEMENTING_AGENCY", project_ids=[]).status_code == 422
    assert invite(client, role="SUPERADMIN").status_code == 422
    assert invite(client, email="not-an-email").status_code == 422
    assert not providers.emails


def test_pending_account_cannot_log_in_or_set_role(identity_client):
    client, providers = identity_client
    login(client)
    pending = invite(client).json()
    providers.passwords[pending["id"]] = PASSWORD
    providers.users[pending["id"]]["email_confirmed_at"] = NOW
    assert login(client, pending["email"]).status_code == 403
    token = next(iter(providers.tokens))
    assert client.post("/api/v1/auth/accept-invitation", json={
        "token_hash": token, "type": "invite", "password": PASSWORD, "role": "SYSTEM_ADMIN"}).status_code == 422


def test_disable_revokes_existing_session_and_admin_is_protected(identity_client):
    client, providers = identity_client
    login(client)
    pending = invite(client).json()
    accept(client, providers)
    login(client, pending["email"])
    officer_cookie = client.cookies.get("landguard_session")
    login(client)
    assert client.patch("/api/v1/auth/users/" + ADMIN, json={"status": "disabled"}).status_code == 403
    assert client.patch("/api/v1/auth/users/" + pending["id"], json={"status": "disabled"}).status_code == 200
    client.cookies.clear()
    client.cookies.set("landguard_session", officer_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client, pending["email"]).status_code == 403


def test_expired_session_and_rate_limit(identity_client):
    client, providers = identity_client
    login(client)
    providers.tables["sessions"][0]["expires_at"] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    assert client.get("/api/v1/auth/me").status_code == 401
    for _ in range(9):
        assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 429


def test_system_admin_cannot_access_project_surfaces(identity_client):
    client, _ = identity_client
    assert login(client).status_code == 200
    for path in ("/projects", "/dashboard/summary", "/dashboard/district-summary", "/dashboard/stage-distribution",
                 "/dashboard/operational-risks", "/map-data", "/alerts", "/review-notices", "/model/status"):
        assert client.get("/api/v1" + path).status_code == 403
    assert client.post("/api/v1/projects", json={}).status_code == 403


@pytest.mark.parametrize("role,scope", [
    ("DISTRICT_OFFICER", {"state": "Maharashtra", "district": "Pune"}),
    ("STATE_OFFICER", {"state": "Maharashtra"}),
    ("IMPLEMENTING_AGENCY", {"project_ids": ["TEST01"]}),
])
def test_scope_filters_all_surfaces_and_prevents_record_reassignment(identity_client, payload, role, scope):
    client, providers = identity_client
    login(client)
    user = providers.tables["profiles"][0]
    user.update(role="STATE_OFFICER", state="Maharashtra", district=None, project_ids=[])
    assert client.post("/api/v1/projects", json=payload).status_code == 201
    outside = {**payload, "project_id": "OUTSIDE", "state": "Karnataka", "district": "Bengaluru"}
    user.update(state="Karnataka")
    assert client.post("/api/v1/projects", json=outside).status_code == 201
    user.update(role=role, state=None, district=None, project_ids=[])
    user.update(**scope)
    assert client.get("/api/v1/projects").json()["total"] == 1
    assert client.get("/api/v1/projects?state=Karnataka").json()["total"] == 0
    assert client.get("/api/v1/dashboard/summary").json()["total_projects"] == 1
    assert sum(x["project_count"] for x in client.get("/api/v1/dashboard/district-summary").json()) == 1
    assert sum(x["count"] for x in client.get("/api/v1/dashboard/stage-distribution").json()) == 1
    assert client.get("/api/v1/dashboard/operational-risks").json()["projects_with_pending_approvals"] == 1
    assert client.get("/api/v1/review-notices").json()["total"] == 1
    for path in ("/map-data", "/alerts"):
        assert {p["project_id"] for p in client.get("/api/v1" + path).json()} == {"TEST01"}
    assert client.get("/api/v1/projects/OUTSIDE").status_code == 404
    assert client.post("/api/v1/projects/OUTSIDE/predict").status_code == 404
    assert client.put("/api/v1/projects/OUTSIDE", json=payload).status_code == 404
    assert client.put("/api/v1/projects/TEST01", json=outside).status_code == 404
    assert client.post("/api/v1/projects", json={**outside, "project_id": "NEW"}).status_code == 404
    expected_delete = 204 if role == "STATE_OFFICER" else 403
    assert client.delete("/api/v1/projects/TEST01").status_code == expected_delete
    if expected_delete == 403:
        assert client.get("/api/v1/projects/TEST01").json()["district"] == "Pune"
