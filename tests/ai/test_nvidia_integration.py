"""Optional live NVIDIA integration test (legacy entry point)."""

from __future__ import annotations

import pytest

from tests.e2e.helpers import build_e2e_stack, require_nvidia_runtime
from uniassist.ai.models import RefusalAnswer, VerifiedAnswer

pytestmark = [pytest.mark.integration, pytest.mark.nvidia]


def test_live_nvidia_end_to_end(tmp_path) -> None:
    """Exercise retrieval, NVIDIA generation, and verification against the live API."""
    require_nvidia_runtime()
    stack = build_e2e_stack(tmp_path)

    assert stack.rebuild_report.chunks_created > 0

    answer = stack.pipeline.ask("Can I apply for academic leave?")
    assert isinstance(answer, VerifiedAnswer)
    assert answer.citations

    refusal = stack.pipeline.ask("What is the university policy for travel to Mars?")
    assert isinstance(refusal, RefusalAnswer)
