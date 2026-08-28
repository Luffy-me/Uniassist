export const ADMIN_SECRET_STORAGE_KEY = "uniassist.adminSecret";

export function getAdminSecret(): string {
  if (typeof sessionStorage !== "undefined") {
    const stored = sessionStorage.getItem(ADMIN_SECRET_STORAGE_KEY)?.trim();
    if (stored) {
      return stored;
    }
  }
  return (import.meta.env.VITE_ADMIN_SECRET ?? "").trim();
}

export function setSessionAdminSecret(secret: string): void {
  sessionStorage.setItem(ADMIN_SECRET_STORAGE_KEY, secret.trim());
}

export function clearSessionAdminSecret(): void {
  sessionStorage.removeItem(ADMIN_SECRET_STORAGE_KEY);
}
