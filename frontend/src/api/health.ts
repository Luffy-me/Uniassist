import { apiRequest } from "@/api/client";
import type { HealthResponse, StatusResponse } from "@/types/api";

export async function getHealth() {
  return apiRequest<HealthResponse>("/health");
}

export async function getStatus() {
  return apiRequest<StatusResponse>("/status");
}
