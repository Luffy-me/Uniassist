"""Optional MinerU smoke test when the CLI is installed locally."""

from __future__ import annotations

import pytest

from uniassist.processing.processors.mineru import mineru_available, mineru_version


@pytest.mark.skipif(not mineru_available(), reason="MinerU CLI is not installed")
def test_mineru_version_is_detectable() -> None:
    version = mineru_version()
    assert version is not None
    assert version.strip()
