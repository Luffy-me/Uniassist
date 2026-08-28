export type DocumentStatus = "draft" | "active" | "archived";
export type VerificationState = "pending" | "verified" | "rejected";
export type ProcessingStatus =
  | "pending"
  | "processing"
  | "completed"
  | "failed"
  | "unsupported";

export interface Document {
  document_id: string;
  title: string;
  filename: string;
  content_type: string;
  sha256: string;
  uploaded_at: string;
  source: string;
  source_type: string;
  source_url: string | null;
  effective_date: string | null;
  version: string | null;
  status: DocumentStatus;
  verification_state: VerificationState;
  notes: string | null;
  processing_status: ProcessingStatus | null;
  processing_error: string | null;
  indexed: boolean;
  chunks_indexed: number | null;
}

export interface DocumentUploadResponse {
  request_id: string;
  document: Document;
  duplicate: boolean;
}

export interface ProcessingResultPayload {
  document_id: string;
  status: ProcessingStatus;
  processor: string;
  input_path: string;
  output_path: string | null;
  processed_at: string;
  source_sha256: string;
  content_hash: string | null;
  processor_version: string | null;
  error: string | null;
}

export interface ProcessingResponse {
  request_id: string;
  result: ProcessingResultPayload;
}

export interface IndexResponse {
  request_id: string;
  document_id: string;
  chunks_indexed: number;
  indexed_at: string;
}

export interface ErrorResponse {
  request_id: string;
  error: string;
  detail: string;
}

export interface HealthResponse {
  status: "ok";
}

export interface StatusResponse {
  request_id: string;
  application_version: string;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimension: number | null;
  rag_available: boolean;
  indexed_documents: number;
  total_chunks: number;
  chat_provider?: string;
  groq_configured?: boolean;
  groq_chat_model?: string | null;
}

export interface DocumentListFilters {
  status?: DocumentStatus;
  verification_state?: VerificationState;
  source?: string;
}

export interface UploadDocumentInput {
  file: File;
  title: string;
  source: string;
  source_url?: string;
  version?: string;
  effective_date?: string;
  notes?: string;
}
