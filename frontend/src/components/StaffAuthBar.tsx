import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  clearSessionAdminSecret,
  getAdminSecret,
  setSessionAdminSecret,
} from "@/lib/adminSecret";

export function StaffAuthBar() {
  const [draft, setDraft] = useState("");
  const [hasSecret, setHasSecret] = useState(() => Boolean(getAdminSecret()));

  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        setSessionAdminSecret(draft);
        setDraft("");
        setHasSecret(Boolean(getAdminSecret()));
      }}
    >
      <div>
        <label
          htmlFor="staff-secret"
          className="text-xs uppercase tracking-wide text-muted-foreground"
        >
          Staff secret
        </label>
        <Input
          id="staff-secret"
          type="password"
          autoComplete="off"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={hasSecret ? "Secret is set" : "Required for upload/publish"}
          className="mt-1 h-9 w-52"
        />
      </div>
      <Button type="submit" size="sm">
        Save
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => {
          clearSessionAdminSecret();
          setDraft("");
          setHasSecret(Boolean(getAdminSecret()));
        }}
      >
        Clear
      </Button>
    </form>
  );
}
