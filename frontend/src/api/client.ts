import type { ErrorResponse } from "@/types/api";

export const REQUEST_ID_HEADER = "X-Request-ID";

const DEFAULT_BASE_URL = "http://127.0.0.1:8001";

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ErrorResponse;
  readonly requestId: string;

  constructor(status: number, body: ErrorResponse, requestId: string) {
    super(body.detail || body.error);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.requestId = requestId;
  }
}

export interface ApiResult<T> {
  data: T;
  requestId: string;
}

function extractRequestId(response: Response): string {
  return response.headers.get(REQUEST_ID_HEADER) ?? "unknown";
}

async function parseError(response: Response): Promise<ApiError> {
  const requestId = extractRequestId(response);
  try {
    const body = (await response.json()) as ErrorResponse;
    return new ApiError(response.status, body, body.request_id ?? requestId);
  } catch {
    return new ApiError(
      response.status,
      {
        request_id: requestId,
        error: "request_failed",
        detail: response.statusText || "Request failed",
      },
      requestId,
    );
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  const requestId = extractRequestId(response);

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return { data: undefined as T, requestId };
  }

  const data = (await response.json()) as T;
  return { data, requestId };
}

export async function apiRequestMultipart<T>(
  path: string,
  formData: FormData,
): Promise<ApiResult<T>> {
  return apiRequest<T>(path, {
    method: "POST",
    body: formData,
  });
}
