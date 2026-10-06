"""Tests for staff-secret protection on mutating document routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import (
    LEAVE_TEXT,
    MockAnswerPipeline,
    build_test_services,
    make_verified_answer,
)
from uniassist.api.app import create_app
from uniassist.api.dependencies import ADMIN_SECRET_HEADER


def _locked_client(project_root, secret: str = "staff-secret") -> TestClient:
    pipeline = MockAnswerPipeline(make_verified_answer())
    services = build_test_services(project_root, pipeline)
    services.settings.admin_secret = secret
    return TestClient(create_app(settings=services.settings, services=services))


def _upload(client: TestClient, *, secret: str | None) -> str:
    headers = {ADMIN_SECRET_HEADER: secret} if secret else {}
    response = client.post(
        "/documents/upload",
        headers=headers,
        data={
            "title": "Rules",
            "source": "TEST",
            "source_url": "https://example.org/leave",
        },
        files={"file": ("leave.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 200
    return response.json()["document"]["document_id"]


def test_mutating_document_routes_require_admin_secret(project_root) -> None:
    client = _locked_client(project_root)
    response = client.post(
        "/documents/upload",
        data={
            "title": "Rules",
            "source": "TEST",
            "source_url": "https://example.org/leave",
        },
        files={"file": ("leave.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_wrong_admin_secret_is_rejected(project_root) -> None:
    client = _locked_client(project_root)
    response = client.post(
        "/documents/upload",
        headers={ADMIN_SECRET_HEADER: "not-the-secret"},
        data={
            "title": "Rules",
            "source": "TEST",
            "source_url": "https://example.org/leave",
        },
        files={"file": ("leave.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 401


def test_student_routes_stay_open_without_admin_secret(project_root) -> None:
    client = _locked_client(project_root)
    assert client.get("/health").status_code == 200
    assert client.get("/status").status_code == 401
    assert client.get("/documents").status_code == 401
    headers = {ADMIN_SECRET_HEADER: "staff-secret"}
    assert client.get("/documents", headers=headers).status_code == 200
    assert client.get("/status", headers=headers).status_code == 200
    asked = client.post("/ask", json={"question": "Can I take academic leave?"})
    assert asked.status_code == 200


def test_lifecycle_routes_require_admin_secret(project_root) -> None:
    client = _locked_client(project_root)
    document_id = _upload(client, secret="staff-secret")
    for path in (
        f"/documents/{document_id}/activate",
        f"/documents/{document_id}/process",
        f"/documents/{document_id}/index",
        f"/documents/{document_id}/publish",
    ):
        response = client.post(path)
        assert response.status_code == 401, path


def test_mutating_document_routes_accept_admin_secret(project_root) -> None:
    client = _locked_client(project_root)
    document_id = _upload(client, secret="staff-secret")
    listed = client.get("/documents", headers={ADMIN_SECRET_HEADER: "staff-secret"})
    assert listed.status_code == 200
    published = client.post(
        f"/documents/{document_id}/publish",
        headers={ADMIN_SECRET_HEADER: "staff-secret"},
    )
    assert published.status_code == 200
    asked = client.post("/ask", json={"question": "Can I take academic leave?"})
    assert asked.status_code == 200


def test_archive_removes_document_from_answers(project_root) -> None:
    client = _locked_client(project_root)
    headers = {ADMIN_SECRET_HEADER: "staff-secret"}
    document_id = _upload(client, secret="staff-secret")
    assert client.post(f"/documents/{document_id}/archive").status_code == 401
    assert (
        client.post(f"/documents/{document_id}/publish", headers=headers).status_code
        == 200
    )
    archived = client.post(f"/documents/{document_id}/archive", headers=headers)
    assert archived.status_code == 200
    body = archived.json()
    assert body["status"] == "archived"
    assert body["indexed"] is False


def test_remote_clients_are_rejected_when_no_secret_is_configured(
    project_root,
) -> None:
    from starlette.testclient import TestClient

    services = build_test_services(
        project_root, MockAnswerPipeline(make_verified_answer())
    )
    services.settings.admin_secret = ""
    app = create_app(settings=services.settings, services=services)
    remote = TestClient(app, client=("203.0.113.9", 50000))
    assert remote.get("/documents").status_code == 401
    assert TestClient(app).get("/documents").status_code == 200


def test_proxied_requests_are_not_treated_as_local(project_root) -> None:
    services = build_test_services(
        project_root, MockAnswerPipeline(make_verified_answer())
    )
    services.settings.admin_secret = ""
    client = TestClient(create_app(settings=services.settings, services=services))
    assert client.get("/documents").status_code == 200
    proxied = client.get("/documents", headers={"X-Forwarded-For": "198.51.100.7"})
    assert proxied.status_code == 401


def test_unexpected_value_errors_are_not_reported_as_client_errors(
    project_root,
) -> None:
    services = build_test_services(
        project_root, MockAnswerPipeline(make_verified_answer())
    )

    def boom(*_args, **_kwargs):
        raise ValueError("internal detail")

    services.ingestion.list_documents = boom
    client = TestClient(
        create_app(settings=services.settings, services=services),
        raise_server_exceptions=False,
    )
    response = client.get("/documents")
    assert response.status_code == 500
    assert "internal detail" not in response.text
