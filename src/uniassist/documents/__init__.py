"""Admin-controlled document corpus for UniAssist v1."""

from uniassist.documents.ingestion import DocumentIngestionService, IngestResult
from uniassist.documents.models import (
    DocumentRecord,
    DocumentStatus,
    SourceType,
    VerificationState,
)
from uniassist.documents.store import DocumentStore, JsonDocumentStore

__all__ = [
    "DocumentIngestionService",
    "DocumentRecord",
    "DocumentStatus",
    "DocumentStore",
    "IngestResult",
    "JsonDocumentStore",
    "SourceType",
    "VerificationState",
]
