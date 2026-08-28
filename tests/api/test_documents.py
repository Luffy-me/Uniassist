"""Tests for document endpoints."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from tests.api.conftest import LEAVE_TEXT
from tests.processing.conftest import FIXTURES
from tests.processing.pdf_helpers import write_text_pdf
from uniassist.documents.models import DocumentStatus


def _upload(
    client: TestClient,
    *,
    content: bytes,
    filename: str = "leave.txt",
    content_type: str = "text/plain",
):
    return client.post(
        "/documents/upload",
        data={
            "title": "Academic Leave Regulations",
            "source": "TEST",
            "source_url": "https://example.org/leave",
            "version": "2026-1",
        },
        files={"file": (filename, content, content_type)},
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


def test_document_upload_requires_official_source_url(document_client) -> None:
    client, _, _ = document_client
    response = client.post(
        "/documents/upload",
        data={"title": "Rules", "source": "TEST"},
        files={"file": ("rules.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 422


def test_document_upload_rejects_blank_official_source_url(document_client) -> None:
    client, _, _ = document_client
    response = client.post(
        "/documents/upload",
        data={"title": "Rules", "source": "TEST", "source_url": ""},
        files={"file": ("rules.txt", LEAVE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 422


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


def test_publish_activates_processes_and_indexes(document_client) -> None:
    client, _, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    response = client.post(f"/documents/{document_id}/publish")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["verification_state"] == "verified"
    assert payload["processing_status"] == "completed"
    assert payload["indexed"] is True
    assert payload["chunks_indexed"] > 0


def test_publish_text_pdf_without_mineru(
    document_client,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "uniassist.processing.processors.mineru.mineru_available",
        lambda: False,
    )
    client, _, _ = document_client
    pdf_path = tmp_path / "leave.pdf"
    write_text_pdf(pdf_path, "Students may request academic leave.")
    uploaded = _upload(
        client,
        content=pdf_path.read_bytes(),
        filename="leave.pdf",
        content_type="application/pdf",
    ).json()
    document_id = uploaded["document"]["document_id"]
    response = client.post(f"/documents/{document_id}/publish")
    assert response.status_code == 200
    payload = response.json()
    assert payload["processing_status"] == "completed"
    assert payload["indexed"] is True
    assert payload["chunks_indexed"] > 0
    assert payload["processing_error"] is None


def test_publish_empty_pdf_returns_conflict_with_clear_error(
    document_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "uniassist.processing.processors.mineru.mineru_available",
        lambda: False,
    )
    client, _, _ = document_client
    uploaded = _upload(
        client,
        content=(FIXTURES / "sample.pdf").read_bytes(),
        filename="scan.pdf",
        content_type="application/pdf",
    ).json()
    document_id = uploaded["document"]["document_id"]
    response = client.post(f"/documents/{document_id}/publish")
    assert response.status_code == 409
    assert "no extractable text" in response.json()["detail"]

    detail = client.get(f"/documents/{document_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["processing_status"] == "failed"
    assert body["processing_error"] is not None
    assert "no extractable text" in body["processing_error"]


def test_publish_conflict_for_archived_document(document_client) -> None:
    client, services, _ = document_client
    uploaded = _upload(client, content=LEAVE_TEXT.encode("utf-8")).json()
    document_id = uploaded["document"]["document_id"]
    record = services.ingestion.get_document(document_id)
    assert record is not None
    archived = replace(record, status=DocumentStatus.ARCHIVED)
    services.ingestion._store.update_record(archived)  # noqa: SLF001
    response = client.post(f"/documents/{document_id}/publish")
    assert response.status_code == 409


def test_secrets_are_never_returned(document_client) -> None:
    client, _, _ = document_client
    response = client.get("/status")
    body = response.text.lower()
    assert "groq_api_key" not in body
    assert "authorization" not in body
