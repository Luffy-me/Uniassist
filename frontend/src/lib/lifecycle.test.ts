import { describe, expect, it } from "vitest";
import {
  canActivate,
  canIndex,
  canProcess,
  canPublish,
  getLifecycleSteps,
} from "@/lib/lifecycle";
import type { Document } from "@/types/api";

const baseDocument: Document = {
  document_id: "doc-1",
  title: "Academic Regulations",
  filename: "rules.txt",
  content_type: "text/plain",
  sha256: "abc",
  uploaded_at: "2026-01-01T00:00:00Z",
  source: "TEST",
  source_type: "admin_upload",
  source_url: null,
  effective_date: null,
  version: "2026.1",
  status: "draft",
  verification_state: "pending",
  notes: null,
  processing_status: null,
  processing_error: null,
  indexed: false,
  chunks_indexed: null,
};

describe("lifecycle helpers", () => {
  it("allows activate only for draft documents", () => {
    expect(canActivate(baseDocument)).toBe(true);
    expect(
      canActivate({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
      }),
    ).toBe(false);
  });

  it("allows process only for active verified unprocessed documents", () => {
    expect(
      canProcess({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
      }),
    ).toBe(true);
    expect(
      canProcess({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
        processing_status: "completed",
      }),
    ).toBe(false);
  });

  it("allows index only after processing completes", () => {
    expect(
      canIndex({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
        processing_status: "completed",
      }),
    ).toBe(true);
    expect(
      canIndex({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
        processing_status: "completed",
        indexed: true,
      }),
    ).toBe(false);
  });

  it("allows publish until the document is indexed", () => {
    expect(canPublish(baseDocument)).toBe(true);
    expect(
      canPublish({
        ...baseDocument,
        status: "active",
        verification_state: "verified",
        processing_status: "completed",
        indexed: true,
      }),
    ).toBe(false);
    expect(canPublish({ ...baseDocument, status: "archived" })).toBe(false);
  });

  it("surfaces processing_error on a failed process step", () => {
    const steps = getLifecycleSteps({
      ...baseDocument,
      status: "active",
      verification_state: "verified",
      processing_status: "failed",
      processing_error: "This PDF has no extractable text",
    });
    const processed = steps.find((step) => step.id === "processed");
    expect(processed?.state).toBe("failed");
    expect(processed?.detail).toContain("no extractable text");
  });

  it("derives lifecycle steps from backend state", () => {
    const steps = getLifecycleSteps({
      ...baseDocument,
      status: "active",
      verification_state: "verified",
      processing_status: "completed",
      indexed: true,
      chunks_indexed: 3,
    });
    expect(steps.every((step) => step.state === "complete")).toBe(true);
  });
});
