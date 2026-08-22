import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { listDocuments } from "@/api/documents";
import { DocumentTable } from "@/components/DocumentTable";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { DocumentStatus, VerificationState } from "@/types/api";

export function DocumentsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | "all">(
    "all",
  );
  const [verificationFilter, setVerificationFilter] = useState<
    VerificationState | "all"
  >("all");

  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: async () => (await listDocuments()).data,
  });

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (documentsQuery.data ?? []).filter((document) => {
      if (statusFilter !== "all" && document.status !== statusFilter) {
        return false;
      }
      if (
        verificationFilter !== "all" &&
        document.verification_state !== verificationFilter
      ) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        document.title.toLowerCase().includes(query) ||
        document.filename.toLowerCase().includes(query) ||
        document.source.toLowerCase().includes(query) ||
        (document.version ?? "").toLowerCase().includes(query)
      );
    });
  }, [documentsQuery.data, search, statusFilter, verificationFilter]);

  if (documentsQuery.isLoading) {
    return <LoadingState label="Loading documents..." />;
  }

  if (documentsQuery.isError) {
    return (
      <ErrorState
        title="Unable to load documents"
        error={documentsQuery.error}
        onRetry={() => documentsQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Documents</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Search and manage the authoritative document corpus.
          </p>
        </div>
        <Button variant="outline" onClick={() => documentsQuery.refetch()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Input
          placeholder="Search title, filename, source, version..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as DocumentStatus | "all")
          }
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        <select
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          value={verificationFilter}
          onChange={(event) =>
            setVerificationFilter(
              event.target.value as VerificationState | "all",
            )
          }
        >
          <option value="all">All verification states</option>
          <option value="pending">Pending</option>
          <option value="verified">Verified</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {filteredDocuments.length === 0 ? (
        <EmptyState
          title="No documents found"
          description="Try adjusting your filters or upload a new document."
          actionLabel="Upload document"
          onAction={() => navigate("/upload")}
        />
      ) : (
        <DocumentTable documents={filteredDocuments} />
      )}
    </div>
  );
}
