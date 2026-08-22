"""Tests for the documents CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uniassist.documents.cli import main
from uniassist.documents.ingestion import DocumentIngestionService
from uniassist.documents.store import JsonDocumentStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_cli_upload_list_and_show(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = JsonDocumentStore(
        raw_dir=tmp_path / "raw",
        index_path=tmp_path / "metadata" / "documents.json",
    )
    service = DocumentIngestionService(store)
    monkeypatch.setattr(
        "uniassist.documents.cli.DocumentIngestionService.default",
        lambda project_root=None: service,
    )

    main(
        [
            "upload",
            str(FIXTURES / "sample.pdf"),
            "--title",
            "Student Rules",
            "--source",
            "Registrar",
            "--version",
            "2025-1",
        ]
    )
    upload_output = capsys.readouterr().out
    uploaded = json.loads(upload_output)
    document_id = uploaded["document_id"]

    main(["list"])
    list_output = capsys.readouterr().out
    assert document_id in list_output
    assert "draft" in list_output
    assert "pending" in list_output

    main(["show", document_id])
    show_output = capsys.readouterr().out
    shown = json.loads(show_output)
    assert shown["title"] == "Student Rules"
    assert shown["version"] == "2025-1"
