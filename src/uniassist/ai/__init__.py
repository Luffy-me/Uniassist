"""NVIDIA-powered answer generation and verification."""

from uniassist.ai.models import (
    CandidateAnswer,
    Question,
    VerificationResult,
    VerifiedAnswer,
)

__all__ = [
    "AnswerPipeline",
    "CandidateAnswer",
    "Question",
    "VerificationResult",
    "VerifiedAnswer",
]


def __getattr__(name: str):
    if name == "AnswerPipeline":
        from uniassist.ai.pipeline import AnswerPipeline

        return AnswerPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
