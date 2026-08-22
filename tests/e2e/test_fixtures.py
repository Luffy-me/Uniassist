"""Offline checks for the synthetic E2E evaluation corpus."""

from __future__ import annotations

from tests.e2e.helpers import E2E_DOCUMENTS, FIXTURES_DIR


def test_e2e_fixture_directory_exists() -> None:
    assert FIXTURES_DIR.is_dir()


def test_e2e_fixture_documents_exist() -> None:
    for filename, title, source in E2E_DOCUMENTS:
        path = FIXTURES_DIR / filename
        assert path.exists(), f"Missing fixture: {filename}"
        content = path.read_text(encoding="utf-8")
        assert title.split("(")[0].strip() in content or len(content) > 40
        assert "TEST FIXTURE" in content
        assert source.startswith("E2E_")


def test_e2e_fixtures_have_distinct_facts() -> None:
    contents = {
        filename: (FIXTURES_DIR / filename).read_text(encoding="utf-8")
        for filename, _, _ in E2E_DOCUMENTS
    }
    assert "academic leave" in contents["academic_leave.txt"].lower()
    assert "misses an examination" in contents["exam_rules.txt"].lower()
    assert "dormitory" in contents["dormitory.txt"].lower()
    assert "tuition" in contents["tuition.txt"].lower()
