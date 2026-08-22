"""Document processing orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from uniassist.core.hashing import sha256_hex
from uniassist.documents.models import DocumentRecord, DocumentStatus, VerificationState
from uniassist.documents.store import DocumentStore, JsonDocumentStore
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
        root = project_root or Path.cwd()
        document_store = JsonDocumentStore(
            raw_dir=root / "data" / "raw",
            index_path=root / "data" / "metadata" / "documents.json",
        )
        processing_store = ProcessingStore(
            processed_dir=root / "data" / "processed",
            index_path=root / "data" / "metadata" / "processing.json",
        )
        return cls(
            document_store=document_store,
            processing_store=processing_store,
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

        if not record.local_path.exists():
            return self._save_result(
                self._failed_result(
                    document_id=record.document_id,
                    processor="none",
                    input_path=record.local_path,
                    source_sha256=record.sha256,
                    error=f"source file not found: {record.local_path}",
                )
            )

        suffix = Path(record.filename).suffix.lower()
        if suffix == ".docx":
            return self._save_result(self._process_docx(record))

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
                input_path=record.local_path,
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
        context = ProcessorContext(record=record, output_dir=output_dir)
        try:
            normalized = processor.process(context)
            output_path = self._processing_store.save_normalized(normalized)
            content_hash = sha256_hex(output_path.read_bytes())
            return self._save_result(
                ProcessingResult(
                    document_id=record.document_id,
                    status=ProcessingStatus.COMPLETED,
                    processor=processor.name,
                    input_path=record.local_path,
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
                    input_path=record.local_path,
                    source_sha256=record.sha256,
                    error=str(exc),
                )
            )
        except Exception as exc:
            return self._save_result(
                self._failed_result(
                    document_id=record.document_id,
                    processor=processor.name,
                    input_path=record.local_path,
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
        path = (
            self._processing_store.output_dir_for(record.document_id, record.sha256)
            / "normalized.json"
        )
        if not path.exists():
            return None
        return NormalizedDocument.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def _process_docx(self, record: DocumentRecord) -> ProcessingResult:
        status = self._router.docx_status(record)
        if status == "mineru_docx_available":
            processor = MinerUProcessor()
            context = ProcessorContext(
                record=record,
                output_dir=self._processing_store.output_dir_for(
                    record.document_id,
                    record.sha256,
                ),
            )
            try:
                normalized = processor.process(context)
                output_path = self._processing_store.save_normalized(normalized)
                return ProcessingResult(
                    document_id=record.document_id,
                    status=ProcessingStatus.COMPLETED,
                    processor=processor.name,
                    input_path=record.local_path,
                    output_path=output_path,
                    processed_at=datetime.now(UTC),
                    source_sha256=record.sha256,
                    content_hash=sha256_hex(output_path.read_bytes()),
                    processor_version=normalized.processor_version,
                )
            except Exception as exc:
                return self._failed_result(
                    document_id=record.document_id,
                    processor=processor.name,
                    input_path=record.local_path,
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

    def _processor_version(self, processor: object) -> str | None:
        if getattr(processor, "name", None) == "text":
            return TEXT_PROCESSOR_VERSION
        if getattr(processor, "name", None) == "mineru":
            return mineru_version()
        return None
