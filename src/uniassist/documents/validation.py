"""File validation for document ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".txt": "text/plain",
}


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating an upload candidate."""

    success: bool
    content_type: str | None = None
    errors: tuple[str, ...] = ()


def extension_for_filename(filename: str) -> str | None:
    """Return the lowercase extension for *filename*, if any."""
    path = Path(filename)
    suffix = path.suffix.lower()
    return suffix or None


def detect_content_type(filename: str, content: bytes) -> str | None:
    """Guess MIME type from filename and light content inspection."""
    extension = extension_for_filename(filename)
    if extension is None:
        return None

    if extension == ".pdf" and content.startswith(b"%PDF"):
        return ALLOWED_EXTENSIONS[".pdf"]
    if extension == ".docx" and content.startswith(b"PK"):
        return ALLOWED_EXTENSIONS[".docx"]
    if extension == ".txt":
        return ALLOWED_EXTENSIONS[".txt"]
    return ALLOWED_EXTENSIONS.get(extension)


def validate_upload(
    filename: str,
    content: bytes,
    *,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> ValidationResult:
    """Validate filename, size, and supported document type."""
    errors: list[str] = []

    if not filename.strip():
        errors.append("filename must not be empty")

    if not content:
        errors.append("file must not be empty")

    if len(content) > max_size_bytes:
        errors.append(f"file exceeds maximum size of {max_size_bytes} bytes")

    extension = extension_for_filename(filename)
    if extension not in ALLOWED_EXTENSIONS:
        errors.append(
            "unsupported file type; allowed types: PDF, DOCX, TXT"
        )

    content_type = detect_content_type(filename, content)
    if extension in ALLOWED_EXTENSIONS and content_type is None:
        errors.append(f"content does not match expected type for {extension}")

    if errors:
        return ValidationResult(success=False, errors=tuple(errors))

    assert content_type is not None
    return ValidationResult(success=True, content_type=content_type)


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename."""
    cleaned = Path(filename).name.replace("\x00", "").strip()
    if not cleaned:
        raise ValueError("filename must not be empty after sanitization")
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in cleaned)
    return safe or "document"
