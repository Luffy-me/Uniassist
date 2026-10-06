import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import {
  activateDocument,
  archiveDocument,
  indexDocument,
  processDocument,
  publishDocument,
} from "@/api/documents";
import { ApiError, type ApiResult } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  canActivate,
  canArchive,
  canIndex,
  canProcess,
  canPublish,
} from "@/lib/lifecycle";
import type { Document } from "@/types/api";

interface LifecycleActionsProps {
  document: Document;
  onActionComplete?: (requestId: string) => void;
}

interface ActionDefinition {
  label: string;
  confirm: string;
  enabled: boolean;
  primary?: boolean;
  destructive?: boolean;
  run: () => Promise<ApiResult<unknown>>;
}

function describeError(err: unknown): { message: string; requestId: string } {
  if (err instanceof ApiError) {
    return { message: err.message, requestId: err.requestId };
  }
  const message =
    err instanceof Error ? err.message : "The request could not be completed.";
  return { message, requestId: "unknown" };
}

export function LifecycleActions({
  document,
  onActionComplete,
}: LifecycleActionsProps) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<{
    message: string;
    requestId: string;
  } | null>(null);
  const [lastRequestId, setLastRequestId] = useState<string | null>(null);
  const [activeLabel, setActiveLabel] = useState<string | null>(null);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["documents"] });
    await queryClient.invalidateQueries({
      queryKey: ["document", document.document_id],
    });
    await queryClient.invalidateQueries({ queryKey: ["status"] });
  };

  const mutation = useMutation({
    mutationFn: (action: ActionDefinition) => action.run(),
    onMutate: (action) => setActiveLabel(action.label),
    onSuccess: async ({ requestId }) => {
      setError(null);
      setLastRequestId(requestId);
      await refresh();
      onActionComplete?.(requestId);
    },
    onError: async (err: unknown) => {
      setError(describeError(err));
      // A failed step may still have changed server state (e.g. processing).
      await refresh();
    },
    onSettled: () => setActiveLabel(null),
  });

  const id = document.document_id;
  const actions: ActionDefinition[] = [
    {
      label: "Publish",
      confirm:
        "Publish this document? It will be activated, processed, and indexed for student answers.",
      enabled: canPublish(document),
      primary: true,
      run: () => publishDocument(id),
    },
    {
      label: "Activate",
      confirm: "Activate this document?",
      enabled: canActivate(document),
      run: () => activateDocument(id),
    },
    {
      label: "Process",
      confirm: "Process this document?",
      enabled: canProcess(document),
      run: () => processDocument(id),
    },
    {
      label: "Index",
      confirm: "Index this document for retrieval?",
      enabled: canIndex(document),
      run: () => indexDocument(id),
    },
    {
      label: "Archive",
      confirm:
        "Archive this document? Students will no longer receive answers based on it.",
      enabled: canArchive(document),
      destructive: true,
      run: () => archiveDocument(id),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {actions.map((action) => (
          <Button
            key={action.label}
            variant={
              action.primary
                ? "default"
                : action.destructive
                  ? "destructive"
                  : "outline"
            }
            disabled={!action.enabled || mutation.isPending}
            onClick={() => {
              if (window.confirm(action.confirm)) {
                mutation.mutate(action);
              }
            }}
          >
            {mutation.isPending && activeLabel === action.label ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : null}
            {action.label}
          </Button>
        ))}
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
