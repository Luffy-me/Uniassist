import { cn } from "@/lib/utils";
import type { Document } from "@/types/api";
import { isFailedProcessing } from "@/lib/lifecycle";

type BadgeVariant =
  | "draft"
  | "pending"
  | "active"
  | "verified"
  | "archived"
  | "rejected"
  | "failed"
  | "indexed"
  | "neutral";

const variantClasses: Record<BadgeVariant, string> = {
  draft: "bg-slate-100 text-slate-700 border-slate-200",
  pending: "bg-amber-50 text-amber-800 border-amber-200",
  active: "bg-sky-50 text-sky-800 border-sky-200",
  verified: "bg-emerald-50 text-emerald-800 border-emerald-200",
  archived: "bg-slate-100 text-slate-600 border-slate-200",
  rejected: "bg-rose-50 text-rose-800 border-rose-200",
  failed: "bg-rose-50 text-rose-800 border-rose-200",
  indexed: "bg-emerald-50 text-emerald-800 border-emerald-200",
  neutral: "bg-muted text-muted-foreground border-border",
};

function resolveVariant(document: Document): BadgeVariant {
  if (isFailedProcessing(document.processing_status)) {
    return "failed";
  }
  if (document.indexed) {
    return "indexed";
  }
  if (document.verification_state === "rejected") {
    return "rejected";
  }
  if (document.status === "archived") {
    return "archived";
  }
  if (document.status === "active" && document.verification_state === "verified") {
    return "verified";
  }
  if (document.status === "active") {
    return "active";
  }
  if (document.verification_state === "pending") {
    return "pending";
  }
  return "draft";
}

function resolveLabel(document: Document): string {
  if (isFailedProcessing(document.processing_status)) {
    return "FAILED";
  }
  if (document.indexed) {
    return "INDEXED";
  }
  if (document.status === "active" && document.verification_state === "verified") {
    return "VERIFIED";
  }
  if (document.verification_state === "pending") {
    return "PENDING";
  }
  return (document.status ?? "unknown").toUpperCase();
}

interface StatusBadgeProps {
  document: Document;
  className?: string;
}

export function StatusBadge({ document, className }: StatusBadgeProps) {
  const variant = resolveVariant(document);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium tracking-wide",
        variantClasses[variant],
        className,
      )}
    >
      {resolveLabel(document)}
    </span>
  );
}
