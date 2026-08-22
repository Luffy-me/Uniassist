import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardPage } from "@/pages/Dashboard";
import { DocumentsPage } from "@/pages/Documents";
import { UploadPage } from "@/pages/Upload";
import { DocumentDetailPage } from "@/pages/DocumentDetail";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { ApiError } from "@/api/client";
import { renderWithProviders, renderRoute } from "@/test/utils";
import type { Document } from "@/types/api";

const sampleDocument: Document = {
  document_id: "doc-1",
  title: "Academic Regulations",
  filename: "rules.txt",
  content_type: "text/plain",
  sha256: "abc",
  uploaded_at: "2026-01-01T00:00:00Z",
  source: "TEST",
  source_type: "admin_upload",
  source_url: null,
  effective_date: "2026-09-01",
  version: "2026.1",
  status: "draft",
  verification_state: "pending",
  notes: null,
  processing_status: null,
  indexed: false,
  chunks_indexed: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("admin UI", () => {
  it("renders dashboard", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([sampleDocument]), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "r1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "r2",
            application_version: "0.1.0",
            rag_available: false,
            indexed_documents: 0,
            total_chunks: 0,
            nvidia_configured: false,
            nvidia_embedding_configured: false,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", "X-Request-ID": "r2" },
          },
        ),
      );

    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
    expect(await screen.findByText("Academic Regulations")).toBeInTheDocument();
  });

  it("renders empty documents state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "r1" },
      }),
    );

    renderWithProviders(<DocumentsPage />);
    expect(await screen.findByText("No documents found")).toBeInTheDocument();
  });

  it("renders API error state with request id", () => {
    renderWithProviders(
      <ErrorState
        error={
          new ApiError(
            500,
            {
              request_id: "abc123",
              error: "internal_error",
              detail: "Failed",
            },
            "abc123",
          )
        }
      />,
    );
    expect(screen.getByText(/Request ID: abc123/)).toBeInTheDocument();
  });

  it("renders upload form", () => {
    renderWithProviders(<UploadPage />);
    expect(
      screen.getByRole("heading", { name: "Upload Document" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });

  it("sends multipart upload data", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          request_id: "upload-1",
          duplicate: false,
          document: sampleDocument,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "upload-1" },
        },
      ),
    );

    renderWithProviders(<UploadPage />);
    const file = new File(["hello"], "rules.txt", { type: "text/plain" });
    const input = document.getElementById("file-upload") as HTMLInputElement;
    await user.upload(input, file);
    await user.type(screen.getByLabelText("Title"), "Academic Regulations");
    await user.type(screen.getByLabelText("Source"), "TEST");
    await user.click(screen.getByRole("button", { name: "Upload Document" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    const formData = init?.body as FormData;
    expect(formData.get("title")).toBe("Academic Regulations");
    expect(formData.get("source")).toBe("TEST");
  });

  it("renders document detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(sampleDocument), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "r1" },
      }),
    );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    expect(await screen.findByText("Academic Regulations")).toBeInTheDocument();
    expect(screen.getByText("Lifecycle")).toBeInTheDocument();
  });

  it("calls activate endpoint", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", () => true);
    const activatedDocument = {
      ...sampleDocument,
      status: "active" as const,
      verification_state: "verified" as const,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(sampleDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "get-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(activatedDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "act-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(activatedDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "get-2" },
        }),
      )
      .mockResolvedValue(
        new Response(JSON.stringify([activatedDocument]), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "list-1" },
        }),
      );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    await screen.findByText("Activate");
    await user.click(screen.getByRole("button", { name: "Activate" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/documents/doc-1/activate"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("renders document list with rows", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([sampleDocument]), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "r1" },
      }),
    );

    renderWithProviders(<DocumentsPage />);
    expect(await screen.findByText("Academic Regulations")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toBeInTheDocument();
  });

  it("calls process endpoint", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", () => true);
    const activeDocument = {
      ...sampleDocument,
      status: "active" as const,
      verification_state: "verified" as const,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(activeDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "get-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "proc-1",
            result: {
              ...activeDocument,
              status: "completed",
              processor: "text",
              input_path: "/tmp/rules.txt",
              output_path: "/tmp/out",
              processed_at: "2026-01-02T00:00:00Z",
              source_sha256: "abc",
              content_hash: "def",
              processor_version: "1.0.0",
              error: null,
            },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", "X-Request-ID": "proc-1" },
          },
        ),
      )
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            ...activeDocument,
            processing_status: "completed",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", "X-Request-ID": "get-2" },
          },
        ),
      );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    await screen.findByText("Process");
    await user.click(screen.getByRole("button", { name: "Process" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/documents/doc-1/process"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("calls index endpoint", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", () => true);
    const readyDocument = {
      ...sampleDocument,
      status: "active" as const,
      verification_state: "verified" as const,
      processing_status: "completed" as const,
      indexed: false,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(readyDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "get-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "idx-1",
            document_id: "doc-1",
            chunks_indexed: 2,
            indexed_at: "2026-01-03T00:00:00Z",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", "X-Request-ID": "idx-1" },
          },
        ),
      )
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            ...readyDocument,
            indexed: true,
            chunks_indexed: 2,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json", "X-Request-ID": "get-2" },
          },
        ),
      );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    await screen.findByText("Index");
    await user.click(screen.getByRole("button", { name: "Index" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/documents/doc-1/index"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("renders empty state component", () => {
    renderWithProviders(
      <EmptyState title="No documents found" description="Upload one." />,
    );
    expect(screen.getByText("No documents found")).toBeInTheDocument();
  });
});
