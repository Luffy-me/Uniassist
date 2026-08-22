"""Processing result persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path

from uniassist.processing.models import NormalizedDocument, ProcessingResult


class ProcessingStore:
    """Persist processing results and normalized output."""

    def __init__(self, processed_dir: Path, index_path: Path) -> None:
        self.processed_dir = processed_dir
        self.index_path = index_path
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def output_dir_for(self, document_id: str, source_sha256: str) -> Path:
        return self.processed_dir / document_id / source_sha256

    def save_normalized(self, normalized: NormalizedDocument) -> Path:
        output_dir = self.output_dir_for(
            normalized.document_id,
            normalized.source_sha256,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "normalized.json"
        output_path.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def load_normalized(
        self,
        document_id: str,
        source_sha256: str,
    ) -> NormalizedDocument:
        path = self.output_dir_for(document_id, source_sha256) / "normalized.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return NormalizedDocument.from_dict(data)

    def save_result(self, result: ProcessingResult) -> ProcessingResult:
        records = self.list_results()
        updated = [item for item in records if item.document_id != result.document_id]
        updated.append(result)
        self._write_index(updated)
        return result

    def get_result(self, document_id: str) -> ProcessingResult | None:
        for result in self.list_results():
            if result.document_id == document_id:
                return result
        return None

    def list_results(self) -> list[ProcessingResult]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [ProcessingResult.from_dict(item) for item in data]

    def _write_index(self, results: list[ProcessingResult]) -> None:
        payload = [result.to_dict() for result in results]
        temp_path = self.index_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.index_path)
