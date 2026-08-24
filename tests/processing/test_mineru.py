"""Tests for the isolated MinerU CLI adapter."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.processing.conftest import build_record
from uniassist.processing.processors.base import ProcessorContext
from uniassist.processing.processors.mineru import (
    MinerUNotInstalledError,
    MinerUProcessor,
    mineru_cli_path,
    run_mineru,
)


def test_mineru_executable_override_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "mineru"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("MINERU_EXECUTABLE", str(executable))
    with patch("uniassist.processing.processors.mineru.shutil.which") as which:
        assert mineru_cli_path() == str(executable)
    which.assert_not_called()


def test_mineru_uses_path_when_no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINERU_EXECUTABLE", raising=False)
    with patch(
        "uniassist.processing.processors.mineru.shutil.which",
        return_value="/usr/local/bin/mineru",
    ):
        assert mineru_cli_path() == "/usr/local/bin/mineru"


def test_missing_configured_executable_is_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-mineru"
    monkeypatch.setenv("MINERU_EXECUTABLE", str(missing))
    with pytest.raises(MinerUNotInstalledError, match="non-executable path"):
        run_mineru(tmp_path / "source.pdf", tmp_path / "output")


def test_run_mineru_uses_supported_pipeline_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MINERU_EXECUTABLE", raising=False)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF")
    with (
        patch(
            "uniassist.processing.processors.mineru.mineru_cli_path",
            return_value="/isolated/mineru",
        ),
        patch(
            "uniassist.processing.processors.mineru.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0),
        ) as run,
    ):
        run_mineru(source, tmp_path / "output")
    assert run.call_args.args[0] == [
        "/isolated/mineru",
        "-p",
        str(source),
        "-o",
        str(tmp_path / "output"),
        "-b",
        "pipeline",
    ]


def test_subprocess_failure_is_returned_to_processor(tmp_path: Path) -> None:
    processor = MinerUProcessor()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF")
    record = build_record(
        document_id="pdf-1",
        filename="source.pdf",
        local_path=source,
        sha256="sha",
    )
    with patch(
        "uniassist.processing.processors.mineru.run_mineru",
        return_value=subprocess.CompletedProcess(
            [], 1, stdout="", stderr="parser failed"
        ),
    ):
        with pytest.raises(RuntimeError, match="parser failed"):
            processor.process(
                ProcessorContext(
                    record=record,
                    input_path=source,
                    output_dir=tmp_path / "output",
                )
            )


def test_content_list_preserves_page_provenance(tmp_path: Path) -> None:
    content_list = tmp_path / "document_content_list.json"
    content_list.write_text(
        '[{"type": "text", "text": "First page", "page_idx": 0}, '
        '{"type": "title", "text": "Second page", "page_idx": 1}]',
        encoding="utf-8",
    )
    blocks = MinerUProcessor()._blocks_from_mineru_output(tmp_path)  # noqa: SLF001
    assert [(block.text, block.page_number, block.section) for block in blocks] == [
        ("First page", 1, "text"),
        ("Second page", 2, "title"),
    ]


def test_empty_or_malformed_mineru_output_is_rejected(tmp_path: Path) -> None:
    content_list = tmp_path / "document_content_list.json"
    content_list.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        MinerUProcessor()._blocks_from_mineru_output(tmp_path)  # noqa: SLF001

    content_list.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        MinerUProcessor()._blocks_from_mineru_output(tmp_path)  # noqa: SLF001
