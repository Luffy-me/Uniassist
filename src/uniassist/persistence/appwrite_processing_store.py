"""Appwrite-backed processing metadata and normalized artifact storage."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.processing.models import NormalizedDocument, ProcessingResult


class AppwriteProcessingStore:
    """Persist processing metadata in Appwrite Database and artifacts in Storage."""

    def __init__(
        self,
        clients: AppwriteClients,
        *,
        artifact_store: AppwriteBlobStore,
        workspace_dir: Path | None = None,
    ) -> None:
        self._clients = clients
        self._config = clients.config
        self._artifact_store = artifact_store
        self._workspace_dir = workspace_dir or Path(tempfile.gettempdir()) / "uniassist"
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

    def output_dir_for(self, document_id: str, source_sha256: str) -> Path:
        output_dir = self._workspace_dir / document_id / source_sha256
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def save_normalized(self, normalized: NormalizedDocument) -> Path:
        payload = json.dumps(normalized.to_dict(), ensure_ascii=False).encode("utf-8")
        filename = (
            f"{normalized.document_id}_{normalized.source_sha256}_normalized.json"
        )
        blob_ref = self._artifact_store.save(payload, filename, digest=None)
        return Path(blob_ref)

    def load_normalized(
        self,
        document_id: str,
        source_sha256: str,
    ) -> NormalizedDocument:
        result = self.get_result(document_id)
        if result is None or result.output_path is None:
            raise FileNotFoundError(
                f"normalized output missing for document {document_id}"
            )
        data = json.loads(self._artifact_store.read(str(result.output_path)))
        return NormalizedDocument.from_dict(data)

    def save_result(self, result: ProcessingResult) -> ProcessingResult:
        payload = result.to_dict()
        payload["metadata_json"] = json.dumps(payload, ensure_ascii=False)
        try:
            self._clients.databases.create_document(
                database_id=self._config.database_id,
                collection_id=self._config.processing_collection_id,
                document_id=result.document_id,
                data=payload,
            )
        except Exception:
            self._clients.databases.update_document(
                database_id=self._config.database_id,
                collection_id=self._config.processing_collection_id,
                document_id=result.document_id,
                data=payload,
            )
        return result

    def get_result(self, document_id: str) -> ProcessingResult | None:
        try:
            payload = self._clients.databases.get_document(
                database_id=self._config.database_id,
                collection_id=self._config.processing_collection_id,
                document_id=document_id,
            )
        except Exception:
            return None
        return _result_from_payload(payload)

    def list_results(self) -> list[ProcessingResult]:
        response = self._clients.databases.list_documents(
            database_id=self._config.database_id,
            collection_id=self._config.processing_collection_id,
        )
        documents = response.get("documents", [])
        return [_result_from_payload(item) for item in documents]


def _result_from_payload(payload: dict) -> ProcessingResult:
    if "metadata_json" in payload:
        data = json.loads(str(payload["metadata_json"]))
        return ProcessingResult.from_dict(data)
    return ProcessingResult.from_dict(payload)
