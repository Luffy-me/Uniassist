import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardPage } from "@/pages/Dashboard";
import { DocumentsPage } from "@/pages/Documents";
import { UploadPage } from "@/pages/Upload";
import { DocumentDetailPage } from "@/pages/DocumentDetail";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { StaffAuthBar } from "@/components/StaffAuthBar";
import { AdminLayout } from "@/layouts/AdminLayout";
import { ApiError, ADMIN_SECRET_HEADER } from "@/api/client";
import { ADMIN_SECRET_STORAGE_KEY } from "@/lib/adminSecret";
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
  processing_error: null,
  indexed: false,
  chunks_indexed: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
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
            groq_configured: false,
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

  it("explains 401 staff authentication failures", () => {
    renderWithProviders(
      <ErrorState
        error={
          new ApiError(
            401,
            {
              request_id: "auth-1",
              error: "unauthorized",
              detail: "admin authentication required",
            },
            "auth-1",
          )
        }
      />,
    );
    expect(screen.getByText(/Staff authentication required/)).toBeInTheDocument();
    expect(screen.getByText(/UNIASSIST_ADMIN_SECRET/)).toBeInTheDocument();
  });

  it("saves a staff secret for this browser session", async () => {
    const user = userEvent.setup();
    renderWithProviders(<StaffAuthBar />);
    await user.type(screen.getByLabelText("Staff secret"), "staff-secret");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(sessionStorage.getItem(ADMIN_SECRET_STORAGE_KEY)).toBe("staff-secret");
  });

  it("shows the staff secret field in the admin layout", () => {
    renderWithProviders(<AdminLayout />);
    expect(screen.getByLabelText("Staff secret")).toBeInTheDocument();
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
    await user.type(
      screen.getByLabelText("Official source URL"),
      "https://example.org/regulations",
    );
    await user.click(screen.getByRole("button", { name: "Upload Document" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    const formData = init?.body as FormData;
    expect(formData.get("title")).toBe("Academic Regulations");
    expect(formData.get("source")).toBe("TEST");
    expect(formData.get("source_url")).toBe("https://example.org/regulations");
  });

  it("sends the staff secret header on upload", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem(ADMIN_SECRET_STORAGE_KEY, "staff-secret");
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
    await user.type(
      screen.getByLabelText("Official source URL"),
      "https://example.org/regulations",
    );
    await user.click(screen.getByRole("button", { name: "Upload Document" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get(ADMIN_SECRET_HEADER)).toBe("staff-secret");
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

  it("shows processing error on document detail", async () => {
    const failedDocument = {
      ...sampleDocument,
      processing_status: "failed" as const,
      processing_error: "This PDF has no extractable text (it may be scanned).",
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(failedDocument), {
        status: 200,
        headers: { "Content-Type": "application/json", "X-Request-ID": "r1" },
      }),
    );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    expect(await screen.findByText("Processing error")).toBeInTheDocument();
    expect(screen.getAllByText(/no extractable text/).length).toBeGreaterThan(0);
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

  it("calls publish endpoint", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("confirm", () => true);
    const publishedDocument = {
      ...sampleDocument,
      status: "active" as const,
      verification_state: "verified" as const,
      processing_status: "completed" as const,
      indexed: true,
      chunks_indexed: 1,
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
        new Response(JSON.stringify(publishedDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "pub-1" },
        }),
      )
      .mockResolvedValue(
        new Response(JSON.stringify(publishedDocument), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "get-2" },
        }),
      );

    renderRoute(<DocumentDetailPage />, {
      route: "/documents/doc-1",
      path: "/documents/:documentId",
    });
    await screen.findByRole("button", { name: "Publish" });
    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/documents/doc-1/publish"),
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
