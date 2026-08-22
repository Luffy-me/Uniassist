"""Tests for document endpoints."""

from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from tests.api.conftest import LEAVE_TEXT
from uniassist.documents.models import DocumentStatus


def _upload(client: TestClient, *, content: bytes, filename: str = "leave.txt"):
    return client.post(
        "/documents/upload",
        data={
            "title": "Academic Leave Regulations",
            "source": "TEST",
            "source_url": "https://example.org/leave",
            "version": "2026-1",
        },
        files={"file": (filename, content, "text/plain")},
    )


def test_document_upload(document_client) -> None:
    client, _, _ = document_client
    response = _upload(client, content=LEAVE_TEXT.encode("utf-8"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["title"] == "Academic Leave Regulations"
    assert payload["document"]["status"] == "draft"
    assert payload["document"]["verification_state"] == "pending"
    assert payload["duplicate"] is False


def test_unsupported_upload_returns_bad_request(document_client) -> None:
    client, _, _ = document_client
    response = _upload(
        client,
        content=b"not-a-real-binary",
        filename="bad.exe",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_duplicate_upload(document_client) -> None:
    client, _, _ = document_client
    content = LEAVE_TEXT.encode("utf-8")
    first = _upload(client, content=content)
    second = _upload(client, content=content)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert (
        second.json()["document"]["document_id"]
        == first.json()["document"]["document_id"]
    )


def test_document_list_and_filter(document_client) -> None:
    client, _, _ = document_client
    _upload(client, content=LEAVE_TEXT.encode("utf-8"))
    response = client.get("/documents", params={"source": "TEST"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_document_detail(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    response = client.get(f"/documents/{document_id}")
    assert response.status_code == 200
    assert response.json()["document_id"] == document_id


def test_missing_document_returns_not_found(document_client) -> None:
    client, _, _ = document_client
    response = client.get("/documents/missing-document-id")
    assert response.status_code == 404


def test_activation(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    response = client.post(f"/documents/{document_id}/activate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["verification_state"] == "verified"


def test_activation_conflict_for_archived_document(document_client) -> None:
    client, services, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    record = services.ingestion.get_document(document_id)
    assert record is not None
    archived = replace(record, status=DocumentStatus.ARCHIVED)
    services.ingestion._store.update_record(archived)  # noqa: SLF001
    response = client.post(f"/documents/{document_id}/activate")
    assert response.status_code == 409


def test_processing_endpoint(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    client.post(f"/documents/{document_id}/activate")
    response = client.post(f"/documents/{document_id}/process")
    assert response.status_code == 200
    assert response.json()["result"]["status"] == "completed"


def test_indexing_endpoint(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    client.post(f"/documents/{document_id}/activate")
    client.post(f"/documents/{document_id}/process")
    response = client.post(f"/documents/{document_id}/index")
    assert response.status_code == 200
    assert response.json()["chunks_indexed"] > 0


def test_indexing_ineligible_document_returns_conflict(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    response = client.post(f"/documents/{document_id}/index")
    assert response.status_code == 409


def test_secrets_are_never_returned(document_client) -> None:
    client, _, _ = document_client
    response = client.get("/status")
    body = response.text.lower()
    assert "nvidia_api_key" not in body
    assert "authorization" not in body
