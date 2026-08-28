"""HTTP client for the UniAssist FastAPI /ask endpoint."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from uniassist.telegram.errors import (
    UniAssistAPIError,
    UniAssistAPIResponseError,
    UniAssistAPIUnavailableError,
)

REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class CitationPayload:
    chunk_id: str
    document_id: str
    title: str
    page_number: int | None
    section: str | None
    source: str
    source_url: str | None
    label: str


@dataclass(frozen=True)
class AskResult:
    """Parsed /ask response."""

    request_id: str
    status: str
    answer: str | None = None
    message: str | None = None
    citations: tuple[CitationPayload, ...] = ()
    verified: bool = False


@dataclass
class UniAssistAPIClient:
    """Async client for UniAssist FastAPI endpoints."""

    base_url: str
    timeout_seconds: float = 60.0
    _client: httpx.AsyncClient | None = field(default=None, repr=False)
    _external_client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def ask(
        self,
        question: str,
        *,
        request_id: str | None = None,
    ) -> AskResult:
        resolved_request_id = request_id or uuid.uuid4().hex
        try:
            response = await self._get_client().post(
                f"{self.base_url.rstrip('/')}/ask",
                json={"question": question},
                headers={REQUEST_ID_HEADER: resolved_request_id},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            # #region agent log
            try:
                import json
                import time

                with open(
                    "/Users/cleo/Desktop/Uniassist/.cursor/debug-0bf777.log", "a"
                ) as _f:
                    _f.write(
                        json.dumps(
                            {
                                "sessionId": "0bf777",
                                "hypothesisId": "D",
                                "location": "api_client.py:ask",
                                "message": "ask_timeout",
                                "data": {
                                    "request_id": resolved_request_id,
                                    "timeout_seconds": self.timeout_seconds,
                                    "exc_type": type(exc).__name__,
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            raise UniAssistAPIUnavailableError(
                "UniAssist API request timed out",
                request_id=resolved_request_id,
            ) from exc
        except httpx.RequestError as exc:
            # #region agent log
            try:
                import json
                import time

                with open(
                    "/Users/cleo/Desktop/Uniassist/.cursor/debug-0bf777.log", "a"
                ) as _f:
                    _f.write(
                        json.dumps(
                            {
                                "sessionId": "0bf777",
                                "hypothesisId": "B",
                                "location": "api_client.py:ask",
                                "message": "ask_request_error",
                                "data": {
                                    "request_id": resolved_request_id,
                                    "exc_type": type(exc).__name__,
                                    "error": str(exc)[:240],
                                },
                                "timestamp": int(time.time() * 1000),
                            }
                        )
                        + "\n"
                    )
            except Exception:
                pass
            # #endregion
            raise UniAssistAPIUnavailableError(
                "UniAssist API is unavailable",
                request_id=resolved_request_id,
            ) from exc

        request_id_from_header = response.headers.get(REQUEST_ID_HEADER)
        final_request_id = request_id_from_header or resolved_request_id

        if response.status_code >= 400:
            payload = _safe_json(response)
            detail = payload.get("detail", response.reason_phrase)
            error_code = payload.get("error")
            raise UniAssistAPIError(
                str(detail),
                status_code=response.status_code,
                request_id=payload.get("request_id", final_request_id),
                error_code=error_code,
            )

        payload = _safe_json(response)
        return _parse_ask_response(payload, final_request_id)

    async def health(self) -> bool:
        try:
            response = await self._get_client().get(
                f"{self.base_url.rstrip('/')}/health",
                timeout=self.timeout_seconds,
            )
        except httpx.RequestError:
            return False
        if response.status_code != 200:
            return False
        payload = _safe_json(response)
        return payload.get("status") == "ok"

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        if self._client is None:
            self._client = httpx.AsyncClient(trust_env=False)
        return self._client


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise UniAssistAPIResponseError(
            "Malformed UniAssist API response",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, dict):
        raise UniAssistAPIResponseError(
            "Malformed UniAssist API response",
            status_code=response.status_code,
        )
    return payload


def _parse_ask_response(payload: dict[str, Any], request_id: str) -> AskResult:
    status = payload.get("status")
    if status not in {"verified", "refused"}:
        raise UniAssistAPIResponseError(
            "Unexpected /ask response status",
            request_id=payload.get("request_id", request_id),
        )
    citations_raw = payload.get("citations", [])
    citations: list[CitationPayload] = []
    if isinstance(citations_raw, list):
        for item in citations_raw:
            if not isinstance(item, dict):
                continue
            citations.append(
                CitationPayload(
                    chunk_id=str(item.get("chunk_id", "")),
                    document_id=str(item.get("document_id", "")),
                    title=str(item.get("title", "")),
                    page_number=item.get("page_number"),
                    section=item.get("section"),
                    source=str(item.get("source", "")),
                    source_url=item.get("source_url"),
                    label=str(item.get("label", item.get("title", ""))),
                )
            )
    verification = payload.get("verification", {})
    verified = bool(
        isinstance(verification, dict) and verification.get("verified") is True
    )
    return AskResult(
        request_id=str(payload.get("request_id", request_id)),
        status=str(status),
        answer=payload.get("answer"),
        message=payload.get("message"),
        citations=tuple(citations),
        verified=verified and status == "verified",
    )
