import { apiRequest } from "@/api/client";
import type {
  Document,
  DocumentListFilters,
  DocumentUploadResponse,
  IndexResponse,
  ProcessingResponse,
  UploadDocumentInput,
} from "@/types/api";

function buildQuery(filters: DocumentListFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.verification_state) {
    params.set("verification_state", filters.verification_state);
  }
  if (filters.source) {
    params.set("source", filters.source);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function listDocuments(filters: DocumentListFilters = {}) {
  return apiRequest<Document[]>(`/documents${buildQuery(filters)}`);
}

export async function getDocument(documentId: string) {
  return apiRequest<Document>(`/documents/${documentId}`);
}

export async function uploadDocument(input: UploadDocumentInput) {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("title", input.title);
  formData.append("source", input.source);
  if (input.source_url) {
    formData.append("source_url", input.source_url);
  }
  if (input.version) {
    formData.append("version", input.version);
  }
  if (input.effective_date) {
    formData.append("effective_date", input.effective_date);
  }
  if (input.notes) {
    formData.append("notes", input.notes);
  }
  return apiRequest<DocumentUploadResponse>("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function activateDocument(documentId: string) {
  return apiRequest<Document>(`/documents/${documentId}/activate`, {
    method: "POST",
  });
}

export async function processDocument(documentId: string) {
  return apiRequest<ProcessingResponse>(`/documents/${documentId}/process`, {
    method: "POST",
  });
}

export async function indexDocument(documentId: string) {
  return apiRequest<IndexResponse>(`/documents/${documentId}/index`, {
    method: "POST",
  });
}
