"""Data models for the UniAssist document corpus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path


class DocumentStatus(StrEnum):
    """Lifecycle status of a document in the corpus."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class VerificationState(StrEnum):
    """Verification state reserved for future NVIDIA/admin review."""

    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class SourceType(StrEnum):
    """How a document entered the corpus."""

    ADMIN_UPLOAD = "admin_upload"
    SINGLE_PAGE_IMPORT = "single_page_import"
    SCRAPEAI = "scrapeai"


@dataclass(frozen=True)
class DocumentRecord:
    """A document in the authoritative UniAssist corpus."""

    document_id: str
    title: str
    filename: str
    content_type: str
    sha256: str
    local_path: Path
    uploaded_at: datetime
    source: str
    source_type: SourceType
    status: DocumentStatus
    verification_state: VerificationState
    source_url: str | None = None
    effective_date: date | None = None
    version: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Serialize the record for JSON persistence."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "filename": self.filename,
            "content_type": self.content_type,
            "sha256": self.sha256,
            "local_path": str(self.local_path),
            "uploaded_at": self.uploaded_at.isoformat(),
            "source": self.source,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "effective_date": (
                self.effective_date.isoformat() if self.effective_date else None
            ),
            "version": self.version,
            "status": self.status.value,
            "verification_state": self.verification_state.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | None]) -> DocumentRecord:
        """Deserialize a record from JSON persistence."""
        effective = data.get("effective_date")
        return cls(
            document_id=str(data["document_id"]),
            title=str(data["title"]),
            filename=str(data["filename"]),
            content_type=str(data["content_type"]),
            sha256=str(data["sha256"]),
            local_path=Path(str(data["local_path"])),
            uploaded_at=datetime.fromisoformat(str(data["uploaded_at"])),
            source=str(data["source"]),
            source_type=SourceType(str(data["source_type"])),
            source_url=data.get("source_url"),
            effective_date=date.fromisoformat(effective) if effective else None,
            version=data.get("version"),
            status=DocumentStatus(str(data["status"])),
            verification_state=VerificationState(str(data["verification_state"])),
            notes=data.get("notes"),
        )
