import { Link } from "react-router-dom";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import type { Document } from "@/types/api";

interface DocumentCardProps {
  document: Document;
}

export function DocumentCard({ document }: DocumentCardProps) {
  return (
    <Link to={`/documents/${document.document_id}`}>
      <Card className="transition-colors hover:bg-muted/20">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-base">{document.title}</CardTitle>
            <StatusBadge document={document} />
          </div>
        </CardHeader>
        <CardContent className="space-y-1 text-sm text-muted-foreground">
          <p>{document.source}</p>
          <p>Version {document.version ?? "—"}</p>
          <p>Effective {formatDate(document.effective_date)}</p>
          {document.processing_status === "failed" && document.processing_error ? (
            <p className="text-rose-700">{document.processing_error}</p>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}
