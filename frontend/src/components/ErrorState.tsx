import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";

interface ErrorStateProps {
  title?: string;
  error: unknown;
  onRetry?: () => void;
}

function resolveMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unexpected error occurred.";
}

function resolveRequestId(error: unknown): string | null {
  if (error instanceof ApiError) {
    return error.requestId;
  }
  return null;
}

export function ErrorState({
  title = "Unable to complete the request",
  error,
  onRetry,
}: ErrorStateProps) {
  const requestId = resolveRequestId(error);
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center rounded-lg border border-rose-200 bg-rose-50 px-6 py-10 text-center">
      <AlertCircle className="mb-3 h-8 w-8 text-destructive" />
      <h3 className="text-base font-medium text-foreground">{title}</h3>
      <p className="mt-2 max-w-lg text-sm text-muted-foreground">
        {resolveMessage(error)}
      </p>
      {requestId ? (
        <p className="mt-3 font-mono text-xs text-muted-foreground">
          Request ID: {requestId}
        </p>
      ) : null}
      {onRetry ? (
        <Button className="mt-5" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
