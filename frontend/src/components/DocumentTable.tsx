import { Link } from "react-router-dom";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatDate, formatDateTime } from "@/lib/utils";
import type { Document } from "@/types/api";

interface DocumentTableProps {
  documents: Document[];
}

export function DocumentTable({ documents }: DocumentTableProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <table className="min-w-full divide-y divide-border text-sm">
        <thead className="bg-muted/40">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Title
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Status
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Version
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Source
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Effective
            </th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">
              Updated
            </th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {documents.map((document) => (
            <tr key={document.document_id} className="hover:bg-muted/20">
              <td className="px-4 py-3">
                <div className="font-medium text-foreground">{document.title}</div>
                <div className="text-xs text-muted-foreground">
                  {document.filename}
                </div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge document={document} />
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {document.version ?? "—"}
              </td>
              <td className="px-4 py-3 text-muted-foreground">{document.source}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDate(document.effective_date)}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDateTime(document.uploaded_at)}
              </td>
              <td className="px-4 py-3 text-right">
                <Button asChild variant="outline" size="sm">
                  <Link to={`/documents/${document.document_id}`}>Open</Link>
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
