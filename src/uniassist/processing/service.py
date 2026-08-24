"""Document processing orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from uniassist.core.hashing import sha256_hex
from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.documents.store import DocumentStore
from uniassist.processing.models import (
    NormalizedDocument,
    ProcessingResult,
    ProcessingStatus,
)
from uniassist.processing.processors.base import ProcessorContext
from uniassist.processing.processors.mineru import (
    MinerUNotInstalledError,
    MinerUProcessor,
    mineru_version,
)
from uniassist.processing.processors.text import (
    PROCESSOR_VERSION as TEXT_PROCESSOR_VERSION,
)
from uniassist.processing.router import ProcessorRouter, UnsupportedDocumentError
from uniassist.processing.store import ProcessingStore


class ProcessingEligibilityError(ValueError):
    """Raised when a document is not eligible for processing."""


class DocumentProcessingService:
    """Transform approved source documents into normalized content."""

    def __init__(
        self,
        document_store: DocumentStore,
        processing_store: ProcessingStore,
        router: ProcessorRouter | None = None,
        *,
        require_eligibility: bool = True,
    ) -> None:
        self._document_store = document_store
        self._processing_store = processing_store
        self._router = router or ProcessorRouter()
        self._require_eligibility = require_eligibility

    @classmethod
    def default(
        cls,
        project_root: Path | None = None,
        *,
        require_eligibility: bool = True,
    ) -> DocumentProcessingService:
        from uniassist.persistence.factory import build_persistence

        root = project_root or Path.cwd()
        persistence = build_persistence(root)
        return cls(
            document_store=persistence.document_store,
            processing_store=persistence.processing_store,
            require_eligibility=require_eligibility,
        )

    def process_document(self, document_id: str) -> ProcessingResult:
        record = self._document_store.get(document_id)
        if record is None:
            return self._failed_result(
                document_id=document_id,
                processor="none",
                input_path=Path("missing"),
                source_sha256="",
                error=f"document not found: {document_id}",
            )

        if self._require_eligibility:
            self._ensure_eligible(record)

        if not self._document_store.blob_exists(record):
            return self._save_result(
                self._failed_result(
                    document_id=record.document_id,
                    processor="none",
                    input_path=record.local_path,
                    source_sha256=record.sha256,
                    error="source file not found for document",
                )
            )

        input_path = self._materialize_input(record)
        suffix = Path(record.filename).suffix.lower()
        if suffix == ".docx":
            return self._save_result(self._process_docx(record, input_path=input_path))

        try:
            processor = self._router.select(record)
        except UnsupportedDocumentError as exc:
            return self._save_result(
                self._unsupported_result(record, processor="none", error=str(exc))
            )

        self._save_result(
            ProcessingResult(
                document_id=record.document_id,
                status=ProcessingStatus.PROCESSING,
                processor=processor.name,
                input_path=input_path,
                output_path=None,
                processed_at=datetime.now(UTC),
                source_sha256=record.sha256,
                processor_version=self._processor_version(processor),
            )
        )

        output_dir = self._processing_store.output_dir_for(
            record.document_id,
            record.sha256,
        )
        context = ProcessorContext(
            record=record,
            output_dir=output_dir,
            input_path=input_path,
        )
        try:
            normalized = processor.process(context)
            output_path = self._processing_store.save_normalized(normalized)
            content_hash = sha256_hex(self._read_output_bytes(output_path))
            return self._save_result(
                ProcessingResult(
                    document_id=record.document_id,
                    status=ProcessingStatus.COMPLETED,
                    processor=processor.name,
                    input_path=input_path,
                    output_path=output_path,
                    processed_at=datetime.now(UTC),
                    source_sha256=record.sha256,
                    content_hash=content_hash,
                    processor_version=normalized.processor_version,
                )
            )
        except MinerUNotInstalledError as exc:
            return self._save_result(
                self._failed_result(
                    document_id=record.document_id,
                    processor=processor.name,
                    input_path=input_path,
                    source_sha256=record.sha256,
                    error=str(exc),
                )
            )
        except Exception as exc:
            return self._save_result(
                self._failed_result(
                    document_id=record.document_id,
                    processor=processor.name,
                    input_path=input_path,
                    source_sha256=record.sha256,
                    error=str(exc),
                )
            )

    def get_result(self, document_id: str) -> ProcessingResult | None:
        return self._processing_store.get_result(document_id)

    def list_results(self) -> list[ProcessingResult]:
        return self._processing_store.list_results()

    def get_normalized(self, document_id: str) -> NormalizedDocument | None:
        record = self._document_store.get(document_id)
        if record is None:
            return None
        try:
            return self._processing_store.load_normalized(
                record.document_id,
                record.sha256,
            )
        except FileNotFoundError:
            return None

    def _process_docx(
        self,
        record: DocumentRecord,
        *,
        input_path: Path,
    ) -> ProcessingResult:
        status = self._router.docx_status(record)
        if status == "mineru_docx_available":
            processor = MinerUProcessor()
            context = ProcessorContext(
                record=record,
                output_dir=self._processing_store.output_dir_for(
                    record.document_id,
                    record.sha256,
                ),
                input_path=input_path,
            )
            try:
                normalized = processor.process(context)
                output_path = self._processing_store.save_normalized(normalized)
                return ProcessingResult(
                    document_id=record.document_id,
                    status=ProcessingStatus.COMPLETED,
                    processor=processor.name,
                    input_path=input_path,
                    output_path=output_path,
                    processed_at=datetime.now(UTC),
                    source_sha256=record.sha256,
                    content_hash=sha256_hex(self._read_output_bytes(output_path)),
                    processor_version=normalized.processor_version,
                )
            except Exception as exc:
                return self._failed_result(
                    document_id=record.document_id,
                    processor=processor.name,
                    input_path=input_path,
                    source_sha256=record.sha256,
                    error=str(exc),
                )

        messages = {
            "mineru_not_installed": (
                "DOCX processing requires MinerU, which is not installed. "
                "Install with: pip install 'mineru[pipeline]' (Python >=3.10,<3.14)."
            ),
            "docx_deferred": (
                "DOCX processing is deferred because the installed MinerU version "
                "does not advertise reliable DOCX support."
            ),
        }
        return self._unsupported_result(
            record,
            processor="mineru",
            error=messages.get(status, "DOCX processing is not supported."),
        )

    def _ensure_eligible(self, record: DocumentRecord) -> None:
        if record.status != DocumentStatus.ACTIVE:
            raise ProcessingEligibilityError(
                "only ACTIVE documents can be processed; "
                f"document {record.document_id} is {record.status.value}"
            )
        if record.verification_state != VerificationState.VERIFIED:
            raise ProcessingEligibilityError(
                "only VERIFIED documents can be processed; "
                f"document {record.document_id} is {record.verification_state.value}"
            )

    def _save_result(self, result: ProcessingResult) -> ProcessingResult:
        return self._processing_store.save_result(result)

    def _failed_result(
        self,
        *,
        document_id: str,
        processor: str,
        input_path: Path,
        source_sha256: str,
        error: str,
    ) -> ProcessingResult:
        return ProcessingResult(
            document_id=document_id,
            status=ProcessingStatus.FAILED,
            processor=processor,
            input_path=input_path,
            output_path=None,
            processed_at=datetime.now(UTC),
            source_sha256=source_sha256,
            error=error,
        )

    def _unsupported_result(
        self,
        record: DocumentRecord,
        *,
        processor: str,
        error: str,
    ) -> ProcessingResult:
        return ProcessingResult(
            document_id=record.document_id,
            status=ProcessingStatus.UNSUPPORTED,
            processor=processor,
            input_path=record.local_path,
            output_path=None,
            processed_at=datetime.now(UTC),
            source_sha256=record.sha256,
            error=error,
        )

    def _materialize_input(self, record: DocumentRecord) -> Path:
        if record.local_path.exists():
            return record.local_path
        workspace = self._processing_store.output_dir_for(
            record.document_id,
            record.sha256,
        )
        input_path = workspace / record.filename
        input_path.write_bytes(self._document_store.read_blob(record))
        return input_path

    def _read_output_bytes(self, output_path: Path) -> bytes:
        from uniassist.persistence.appwrite_blob_store import AppwriteBlobStore
        from uniassist.persistence.appwrite_paths import decode_blob_path

        ref = decode_blob_path(output_path)
        if ref.startswith("appwrite://"):
            if isinstance(self._processing_store, object) and hasattr(
                self._processing_store, "_artifact_store"
            ):
                store = getattr(self._processing_store, "_artifact_store")
                if isinstance(store, AppwriteBlobStore):
                    return store.read(ref)
        return output_path.read_bytes()

    def _processor_version(self, processor: object) -> str | None:
        if getattr(processor, "name", None) == "text":
            return TEXT_PROCESSOR_VERSION
        if getattr(processor, "name", None) == "mineru":
            return mineru_version()
        return None
