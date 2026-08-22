import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listDocuments } from "@/api/documents";
import { getStatus } from "@/api/health";
import { DocumentCard } from "@/components/DocumentCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { isFailedProcessing } from "@/lib/lifecycle";
import type { Document } from "@/types/api";

function computeStats(documents: Document[]) {
  return {
    total: documents.length,
    draft: documents.filter((doc) => doc.status === "draft").length,
    pending: documents.filter((doc) => doc.verification_state === "pending").length,
    active: documents.filter((doc) => doc.status === "active").length,
    verified: documents.filter(
      (doc) =>
        doc.status === "active" && doc.verification_state === "verified",
    ).length,
    processed: documents.filter((doc) => doc.processing_status === "completed")
      .length,
    indexed: documents.filter((doc) => doc.indexed).length,
    failed: documents.filter((doc) => isFailedProcessing(doc.processing_status))
      .length,
  };
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: async () => (await listDocuments()).data,
  });
  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: async () => (await getStatus()).data,
  });

  const stats = useMemo(
    () => computeStats(documentsQuery.data ?? []),
    [documentsQuery.data],
  );

  const recentDocuments = useMemo(() => {
    const items = [...(documentsQuery.data ?? [])];
    items.sort(
      (left, right) =>
        new Date(right.uploaded_at).getTime() -
        new Date(left.uploaded_at).getTime(),
    );
    return items.slice(0, 5);
  }, [documentsQuery.data]);

  if (documentsQuery.isLoading) {
    return <LoadingState label="Loading dashboard..." />;
  }

  if (documentsQuery.isError) {
    return (
      <ErrorState
        title="Unable to load dashboard"
        error={documentsQuery.error}
        onRetry={() => documentsQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Dashboard</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Overview of the UniAssist document corpus.
        </p>
        {statusQuery.data ? (
          <p className="mt-2 text-xs text-muted-foreground">
            API v{statusQuery.data.application_version} · RAG{" "}
            {statusQuery.data.rag_available ? "available" : "empty"} ·{" "}
            {statusQuery.data.total_chunks} chunks indexed
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total" value={stats.total} />
        <StatCard label="Draft" value={stats.draft} />
        <StatCard label="Pending" value={stats.pending} />
        <StatCard label="Active" value={stats.active} />
        <StatCard label="Verified" value={stats.verified} />
        <StatCard label="Processed" value={stats.processed} />
        <StatCard label="Indexed" value={stats.indexed} />
        <StatCard label="Failed" value={stats.failed} />
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Recent documents</h3>
        </div>
        {recentDocuments.length === 0 ? (
          <EmptyState
            title="No documents found"
            description="Upload your first document to begin managing the corpus."
            actionLabel="Upload document"
            onAction={() => navigate("/upload")}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {recentDocuments.map((document) => (
              <DocumentCard key={document.document_id} document={document} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
