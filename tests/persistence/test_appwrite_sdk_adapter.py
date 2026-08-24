"""Tests for Appwrite SDK response adapter."""

from __future__ import annotations

from types import SimpleNamespace

from uniassist.persistence.appwrite_paths import (
    decode_blob_path,
    encode_blob_path,
    normalize_blob_ref,
)
from uniassist.persistence.appwrite_sdk_adapter import (
    appwrite_row_id,
    document_data,
    iter_collection_documents,
    sanitize_payload,
)


def test_appwrite_row_id_maps_long_chunk_ids() -> None:
    chunk_id = "f" * 64
    row_id = appwrite_row_id(chunk_id)
    assert len(row_id) == 36
    assert row_id == appwrite_row_id(chunk_id)


def test_appwrite_row_id_preserves_short_ids() -> None:
    assert appwrite_row_id("index_manifest") == "index_manifest"
    payload = SimpleNamespace(
        id="doc-1",
        data={
            "metadata_json": '{"document_id":"doc-1"}',
            "title": "Rules",
        },
    )
    data = document_data(payload)
    assert data["metadata_json"] == '{"document_id":"doc-1"}'
    assert data["title"] == "Rules"


def test_iter_collection_documents_reads_document_list() -> None:
    response = SimpleNamespace(
        documents=[
            SimpleNamespace(
                id="chunk-1",
                data={"chunk_id": "chunk-1", "embedding": "[1.0]"},
            )
        ]
    )
    rows = iter_collection_documents(response)
    assert rows == [{"chunk_id": "chunk-1", "embedding": "[1.0]"}]


def test_sanitize_payload_removes_nulls_and_stringifies_paths() -> None:
    from pathlib import Path

    payload = sanitize_payload(
        {
            "document_id": "doc-1",
            "notes": None,
            "local_path": Path("/tmp/file.txt"),
            "chunk_index": 2,
        }
    )
    assert payload == {
        "document_id": "doc-1",
        "local_path": "/tmp/file.txt",
        "chunk_index": 2,
    }


def test_encode_decode_blob_path_survives_pathlib() -> None:
    ref = "appwrite://raw/raw-bucket/abc123"
    encoded = encode_blob_path(ref)
    assert str(encoded) == "uniassist-remote/raw/raw-bucket/abc123"
    assert decode_blob_path(encoded) == ref


def test_normalize_blob_ref_fixes_pathlib_corruption() -> None:
    assert (
        normalize_blob_ref("appwrite:/raw/raw-bucket/abc123")
        == "appwrite://raw/raw-bucket/abc123"
    )
    assert (
        decode_blob_path("virtual:/appwrite:/processed/processed/file123")
        == "appwrite://processed/processed/file123"
    )
