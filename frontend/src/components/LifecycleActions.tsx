import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { activateDocument, indexDocument, processDocument } from "@/api/documents";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  canActivate,
  canIndex,
  canProcess,
} from "@/lib/lifecycle";
import type { Document } from "@/types/api";

interface LifecycleActionsProps {
  document: Document;
  onActionComplete?: (requestId: string) => void;
}

export function LifecycleActions({
  document,
  onActionComplete,
}: LifecycleActionsProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<ApiError | null>(null);
  const [lastRequestId, setLastRequestId] = useState<string | null>(null);

  const invalidate = async (documentId: string) => {
    await queryClient.invalidateQueries({ queryKey: ["documents"] });
    await queryClient.invalidateQueries({ queryKey: ["document", documentId] });
  };

  const activateMutation = useMutation({
    mutationFn: () => activateDocument(document.document_id),
    onSuccess: async ({ requestId }) => {
      setError(null);
      setLastRequestId(requestId);
      await invalidate(document.document_id);
      onActionComplete?.(requestId);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err : null);
    },
  });

  const processMutation = useMutation({
    mutationFn: () => processDocument(document.document_id),
    onSuccess: async ({ requestId }) => {
      setError(null);
      setLastRequestId(requestId);
      await invalidate(document.document_id);
      onActionComplete?.(requestId);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err : null);
    },
  });

  const indexMutation = useMutation({
    mutationFn: () => indexDocument(document.document_id),
    onSuccess: async ({ requestId }) => {
      setError(null);
      setLastRequestId(requestId);
      await invalidate(document.document_id);
      onActionComplete?.(requestId);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err : null);
    },
  });

  const pending =
    activateMutation.isPending ||
    processMutation.isPending ||
    indexMutation.isPending;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Button
          disabled={!canActivate(document) || pending}
          onClick={() => {
            if (window.confirm("Activate this document?")) {
              activateMutation.mutate();
            }
          }}
        >
          {activateMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          Activate
        </Button>
        <Button
          variant="outline"
          disabled={!canProcess(document) || pending}
          onClick={() => {
            if (window.confirm("Process this document?")) {
              processMutation.mutate();
            }
          }}
        >
          {processMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          Process
        </Button>
        <Button
          variant="outline"
          disabled={!canIndex(document) || pending}
          onClick={() => {
            if (window.confirm("Index this document for retrieval?")) {
              indexMutation.mutate();
            }
          }}
        >
          {indexMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          Index
        </Button>
      </div>
      {error ? (
        <p className="text-sm text-destructive">
          {error.message}
          <span className="mt-1 block font-mono text-xs text-muted-foreground">
            Request ID: {error.requestId}
          </span>
        </p>
      ) : null}
      {lastRequestId ? (
        <p className="font-mono text-xs text-muted-foreground">
          Last request ID: {lastRequestId}
        </p>
      ) : null}
    </div>
  );
}
