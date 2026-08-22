import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { UploadCloud } from "lucide-react";
import { uploadDocument } from "@/api/documents";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function UploadPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [source, setSource] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [version, setVersion] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<ApiError | null>(null);

  const uploadMutation = useMutation({
    mutationFn: () =>
      uploadDocument({
        file: file as File,
        title,
        source,
        source_url: sourceUrl || undefined,
        version: version || undefined,
        effective_date: effectiveDate || undefined,
        notes: notes || undefined,
      }),
    onSuccess: async ({ data, requestId }) => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      navigate(`/documents/${data.document.document_id}`, {
        state: {
          uploadRequestId: requestId,
          duplicate: data.duplicate,
        },
      });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err : null);
    },
  });

  const canSubmit =
    file !== null && title.trim() !== "" && source.trim() !== "" && !uploadMutation.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Upload Document</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          New uploads remain DRAFT and PENDING until explicitly activated.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Document file</CardTitle>
        </CardHeader>
        <CardContent>
          <label
            htmlFor="file-upload"
            className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 py-10 text-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const dropped = event.dataTransfer.files?.[0];
              if (dropped) {
                setFile(dropped);
              }
            }}
          >
            <UploadCloud className="mb-3 h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">
              {file ? file.name : "Drop file here or click to browse"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Supported formats are validated by the API.
            </p>
            <input
              id="file-upload"
              type="file"
              className="hidden"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="source">Source</Label>
            <Input
              id="source"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="source-url">Source URL</Label>
            <Input
              id="source-url"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="version">Version</Label>
            <Input
              id="version"
              value={version}
              onChange={(event) => setVersion(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="effective-date">Effective date</Label>
            <Input
              id="effective-date"
              type="date"
              value={effectiveDate}
              onChange={(event) => setEffectiveDate(event.target.value)}
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {error ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-destructive">
          {error.message}
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            Request ID: {error.requestId}
          </p>
        </div>
      ) : null}

      <Button disabled={!canSubmit} onClick={() => uploadMutation.mutate()}>
        Upload Document
      </Button>
    </div>
  );
}
