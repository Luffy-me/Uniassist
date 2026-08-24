"""MinerU-backed PDF processor."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from uniassist.documents.models import DocumentRecord
from uniassist.processing.models import NormalizedBlock, NormalizedDocument
from uniassist.processing.processors.base import ProcessorContext

MINERU_COMMAND = "mineru"
MINERU_EXECUTABLE_ENV = "MINERU_EXECUTABLE"
DEFAULT_TIMEOUT_SECONDS = 600


class MinerUNotInstalledError(RuntimeError):
    """Raised when the MinerU CLI is not available."""


def mineru_cli_path() -> str | None:
    """Return the configured MinerU CLI path, falling back to PATH."""
    configured_path = os.environ.get(MINERU_EXECUTABLE_ENV, "").strip()
    if configured_path:
        candidate = Path(configured_path).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None
    return shutil.which(MINERU_COMMAND)


def mineru_available() -> bool:
    """Return True when a configured or PATH MinerU CLI is available."""
    return mineru_cli_path() is not None


def mineru_version() -> str | None:
    """Return the installed MinerU version string, if available."""
    cli = mineru_cli_path()
    if cli is None:
        return None
    result = subprocess.run(
        [cli, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr).strip()
    if not output:
        return None
    match = re.search(r"(\d+\.\d+\.\d+)", output)
    return match.group(1) if match else output


def mineru_supports_docx() -> bool:
    """Return True when the installed MinerU CLI advertises DOCX support."""
    cli = mineru_cli_path()
    if cli is None:
        return False
    result = subprocess.run(
        [cli, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    help_text = f"{result.stdout}\n{result.stderr}".lower()
    return "docx" in help_text or ".docx" in help_text


def run_mineru(
    input_path: Path,
    output_dir: Path,
    *,
    backend: str = "pipeline",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Invoke the MinerU CLI against a local file."""
    cli = mineru_cli_path()
    if cli is None:
        configured_path = os.environ.get(MINERU_EXECUTABLE_ENV, "").strip()
        configured_detail = (
            f" {MINERU_EXECUTABLE_ENV} is set to a non-executable path: "
            f"{configured_path}."
            if configured_path
            else ""
        )
        raise MinerUNotInstalledError(
            "MinerU is unavailable. Set MINERU_EXECUTABLE to a valid executable or "
            "install it on PATH with a supported Python (>=3.10,<3.14)."
            f"{configured_detail}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        cli,
        "-p",
        str(input_path),
        "-o",
        str(output_dir),
        "-b",
        backend,
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


class MinerUProcessor:
    """Process PDF documents through the MinerU CLI."""

    name = "mineru"

    def supports(self, record: DocumentRecord) -> bool:
        suffix = Path(record.filename).suffix.lower()
        return suffix == ".pdf"

    def process(self, context: ProcessorContext) -> NormalizedDocument:
        record = context.record
        mineru_output = context.output_dir / "mineru"
        result = run_mineru(context.source_path, mineru_output)
        if result.returncode != 0:
            error = (result.stderr or result.stdout or "MinerU failed").strip()
            raise RuntimeError(error)

        blocks = self._blocks_from_mineru_output(mineru_output)
        return NormalizedDocument(
            document_id=record.document_id,
            title=record.title,
            source=record.source,
            source_url=record.source_url,
            source_sha256=record.sha256,
            processor=self.name,
            processor_version=mineru_version(),
            processed_at=datetime.now(UTC),
            blocks=blocks,
        )

    def _blocks_from_mineru_output(self, output_dir: Path) -> list[NormalizedBlock]:
        content_lists = sorted(output_dir.rglob("*_content_list.json"))
        if content_lists:
            return self._blocks_from_content_list(content_lists[0])

        markdown_files = sorted(output_dir.rglob("*.md"))
        if not markdown_files:
            json_files = sorted(output_dir.rglob("*.json"))
            if json_files:
                return self._blocks_from_json(json_files[0])
            raise RuntimeError("MinerU produced no markdown or JSON output")

        blocks: list[NormalizedBlock] = []
        for page_number, markdown_path in enumerate(markdown_files, start=1):
            text = markdown_path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            blocks.append(
                NormalizedBlock(
                    text=text,
                    page_number=page_number,
                    section=markdown_path.stem,
                )
            )
        if not blocks:
            raise RuntimeError("MinerU markdown output was empty")
        return blocks

    def _blocks_from_content_list(self, json_path: Path) -> list[NormalizedBlock]:
        """Normalize MinerU's structured content-list output with page provenance."""
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("MinerU content-list output was not a JSON list")

        blocks: list[NormalizedBlock] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("content") or "").strip()
            if not text:
                continue
            page_index = item.get("page_idx", item.get("page_number"))
            page_number = page_index + 1 if isinstance(page_index, int) else None
            section = str(item.get("type") or "content")
            blocks.append(
                NormalizedBlock(
                    text=text,
                    page_number=page_number,
                    section=section,
                )
            )
        if not blocks:
            raise RuntimeError("MinerU content-list output was empty")
        return blocks

    def _blocks_from_json(self, json_path: Path) -> list[NormalizedBlock]:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            texts = [str(item).strip() for item in payload if str(item).strip()]
            blocks = [
                NormalizedBlock(text=text, page_number=index + 1, section="json")
                for index, text in enumerate(texts)
            ]
            if blocks:
                return blocks
            raise RuntimeError("MinerU JSON output was empty")
        if isinstance(payload, dict) and "text" in payload:
            text = str(payload["text"]).strip()
            if not text:
                raise RuntimeError("MinerU JSON output was empty")
            return [
                NormalizedBlock(
                    text=text,
                    page_number=1,
                    section="json",
                )
            ]
        raise RuntimeError("MinerU JSON output had no extractable text")
