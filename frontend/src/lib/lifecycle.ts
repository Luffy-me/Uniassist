import type { Document, ProcessingStatus } from "@/types/api";

export type LifecycleStepState = "complete" | "current" | "upcoming" | "failed";

export interface LifecycleStep {
  id: string;
  label: string;
  state: LifecycleStepState;
  detail?: string;
}

export function getLifecycleSteps(document: Document): LifecycleStep[] {
  const failed = document.processing_status === "failed";
  const processed = document.processing_status === "completed";
  const activated =
    document.status === "active" && document.verification_state === "verified";
  const uploaded = true;

  return [
    {
      id: "uploaded",
      label: "Uploaded",
      state: uploaded ? "complete" : "upcoming",
      detail: "DRAFT / PENDING",
    },
    {
      id: "activated",
      label: "Activated",
      state: activated ? "complete" : uploaded ? "current" : "upcoming",
      detail: "ACTIVE / VERIFIED",
    },
    {
      id: "processed",
      label: "Processed",
      state: failed
        ? "failed"
        : processed
          ? "complete"
          : activated
            ? "current"
            : "upcoming",
      detail: failed
        ? document.processing_error ?? document.processing_status ?? "failed"
        : document.processing_status ?? "not started",
    },
    {
      id: "indexed",
      label: "Indexed",
      state: document.indexed
        ? "complete"
        : processed
          ? "current"
          : "upcoming",
      detail: document.indexed
        ? `${document.chunks_indexed ?? 0} chunks`
        : "not indexed",
    },
  ];
}

export function canActivate(document: Document): boolean {
  return document.status === "draft";
}

export function canPublish(document: Document): boolean {
  if (document.status === "archived") {
    return false;
  }
  if (document.indexed) {
    return false;
  }
  if (document.processing_status === "processing") {
    return false;
  }
  return true;
}

export function canProcess(document: Document): boolean {
  return (
    document.status === "active" &&
    document.verification_state === "verified" &&
    document.processing_status !== "completed" &&
    document.processing_status !== "processing"
  );
}

export function canIndex(document: Document): boolean {
  return (
    document.status === "active" &&
    document.verification_state === "verified" &&
    document.processing_status === "completed" &&
    !document.indexed
  );
}

export function isFailedProcessing(status: ProcessingStatus | null): boolean {
  return status === "failed" || status === "unsupported";
}
