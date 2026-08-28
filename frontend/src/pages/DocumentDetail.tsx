import { useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getDocument } from "@/api/documents";
import { ErrorState } from "@/components/ErrorState";
import { LifecycleActions } from "@/components/LifecycleActions";
import { LoadingState } from "@/components/LoadingState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getLifecycleSteps } from "@/lib/lifecycle";
import { cn, formatDate, formatDateTime } from "@/lib/utils";

interface UploadNavigationState {
  uploadRequestId?: string;
  duplicate?: boolean;
}

export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const location = useLocation();
  const navigationState = location.state as UploadNavigationState | null;

  const documentQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: async () => (await getDocument(documentId as string)).data,
    enabled: Boolean(documentId),
  });

  if (!documentId) {
    return <ErrorState title="Invalid document" error={new Error("Missing document id")} />;
  }

  if (documentQuery.isLoading) {
    return <LoadingState label="Loading document..." />;
  }

  if (documentQuery.isError || !documentQuery.data) {
    return (
      <ErrorState
        title="Unable to load document"
        error={documentQuery.error ?? new Error("Document not found")}
        onRetry={() => documentQuery.refetch()}
      />
    );
  }

  const document = documentQuery.data;
  const lifecycleSteps = getLifecycleSteps(document);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-semibold tracking-tight">
              {document.title}
            </h2>
            <StatusBadge document={document} />
          </div>
          <p className="mt-2 text-sm text-muted-foreground">{document.filename}</p>
        </div>
      </div>

      {navigationState?.duplicate ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Duplicate content detected. The existing document record was returned.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm md:grid-cols-2">
            <MetadataItem label="Document ID" value={document.document_id} mono />
            <MetadataItem label="Source" value={document.source} />
            <MetadataItem label="Source URL" value={document.source_url ?? "—"} />
            <MetadataItem label="Version" value={document.version ?? "—"} />
            <MetadataItem
              label="Effective date"
              value={formatDate(document.effective_date)}
            />
            <MetadataItem
              label="Uploaded"
              value={formatDateTime(document.uploaded_at)}
            />
            <MetadataItem label="Content type" value={document.content_type} />
            <MetadataItem label="SHA-256" value={document.sha256} mono />
            <MetadataItem label="Status" value={document.status} />
            <MetadataItem
              label="Verification"
              value={document.verification_state}
            />
            <MetadataItem
              label="Processing"
              value={document.processing_status ?? "not started"}
            />
            {document.processing_error ? (
              <div className="md:col-span-2">
                <MetadataItem
                  label="Processing error"
                  value={document.processing_error}
                />
              </div>
            ) : null}
            <MetadataItem
              label="Indexed"
              value={
                document.indexed
                  ? `yes (${document.chunks_indexed ?? 0} chunks)`
                  : "no"
              }
            />
            {document.notes ? (
              <div className="md:col-span-2">
                <MetadataItem label="Notes" value={document.notes} />
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lifecycle</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {lifecycleSteps.map((step, index) => (
              <div key={step.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold",
                      step.state === "complete" &&
                        "border-emerald-200 bg-emerald-50 text-emerald-800",
                      step.state === "current" &&
                        "border-sky-200 bg-sky-50 text-sky-800",
                      step.state === "upcoming" &&
                        "border-border bg-muted text-muted-foreground",
                      step.state === "failed" &&
                        "border-rose-200 bg-rose-50 text-rose-800",
                    )}
                  >
                    {index + 1}
                  </div>
                  {index < lifecycleSteps.length - 1 ? (
                    <div className="my-1 h-8 w-px bg-border" />
                  ) : null}
                </div>
                <div className="pb-2">
                  <p className="font-medium">{step.label}</p>
                  <p className="text-sm text-muted-foreground">{step.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <LifecycleActions document={document} />
        </CardContent>
      </Card>

      {navigationState?.uploadRequestId ? (
        <p className="font-mono text-xs text-muted-foreground">
          Upload request ID: {navigationState.uploadRequestId}
        </p>
      ) : null}
    </div>
  );
}

function MetadataItem({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-1 break-all", mono && "font-mono text-xs")}>{value}</p>
    </div>
  );
}
