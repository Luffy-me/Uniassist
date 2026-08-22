"""Grounded question answering routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from uniassist.ai.generation import GenerationError
from uniassist.ai.models import RefusalAnswer, VerifiedAnswer
from uniassist.api.dependencies import RequestIdDep, ServicesDep
from uniassist.api.errors import BadRequestError, ServiceUnavailableError
from uniassist.api.schemas import (
    AskRequest,
    AskResponse,
    AskTimingsResponse,
    ask_response_from_refusal,
    ask_response_from_verified,
)

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask_question(
    payload: AskRequest,
    services: ServicesDep,
    request_id: RequestIdDep,
    request: Request,
) -> AskResponse:
    started = time.perf_counter()
    question = payload.question.strip()
    if not question:
        raise BadRequestError("question must not be empty")
    if len(question) > services.settings.max_question_length:
        raise BadRequestError(
            f"question exceeds maximum length of "
            f"{services.settings.max_question_length} characters"
        )

    try:
        result = services.pipeline.ask(question)
    except GenerationError as exc:
        raise ServiceUnavailableError(str(exc)) from exc

    total_ms = (time.perf_counter() - started) * 1000
    timings = AskTimingsResponse(total_latency_ms=total_ms)

    if isinstance(result, VerifiedAnswer):
        return ask_response_from_verified(
            request_id=request_id,
            answer=result,
            timings=timings,
        )

    assert isinstance(result, RefusalAnswer)
    del request
    return ask_response_from_refusal(
        request_id=request_id,
        answer=result,
        timings=timings,
    )
