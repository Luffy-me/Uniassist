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
    assert client.get("/status").status_code == 200
    assert client.get("/documents").status_code == 200
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
    listed = client.get("/documents")
    assert listed.status_code == 200
    published = client.post(
        f"/documents/{document_id}/publish",
        headers={ADMIN_SECRET_HEADER: "staff-secret"},
    )
    assert published.status_code == 200
    asked = client.post("/ask", json={"question": "Can I take academic leave?"})
    assert asked.status_code == 200
