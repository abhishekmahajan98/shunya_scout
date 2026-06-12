import {
  AuthSession,
  AuthUser,
  authHeaders,
  clearSession,
  getRefreshToken,
  saveSession,
} from "./auth";

export type { AuthUser };

export interface Match {
  team_a: string;
  team_b: string;
}

export interface DownloadEntry {
  match: Match;
  pdf_slug: string;
  pdf_url: string;
  quick_test?: boolean;
  created_at?: string | null;
}

export interface DownloadIndex {
  date: string;
  downloads: DownloadEntry[];
}

export interface RunResult {
  date: string;
  match_count: number;
  report_count: number;
  generated_count?: number;
  skipped_count?: number;
  downloads: DownloadEntry[];
  email_sent?: boolean;
  email_to?: string | null;
  email_error?: string | null;
  attachment_count?: number;
  quick_test?: boolean;
}

export interface SignupResult extends Partial<AuthSession> {
  message?: string;
  user: AuthUser;
}

// Dev: Vite proxies /api → backend. Production: same-origin (backend serves UI + API).
const API_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD ? "" : "/api");

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshSession(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!res.ok) return false;
        const session = (await res.json()) as AuthSession;
        saveSession(session);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }

  return refreshPromise;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  retry = true,
): Promise<T> {
  const headers = new Headers(init?.headers);
  Object.entries(authHeaders()).forEach(([key, value]) => {
    headers.set(key, value);
  });

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefreshSession();
    if (refreshed) return request<T>(path, init, false);
    clearSession();
    throw new Error("Session expired. Please sign in again.");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || item).join(", ")
          : `Request failed: ${res.status}`;
    throw new Error(message);
  }

  return res.json();
}

export function login(email: string, password: string): Promise<AuthSession> {
  return request<AuthSession>(
    "/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false,
  ).then((session) => {
    saveSession(session);
    return session;
  });
}

export function signup(email: string, password: string): Promise<SignupResult> {
  return request<SignupResult>(
    "/auth/signup",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false,
  ).then((result) => {
    if (result.access_token && result.refresh_token) {
      saveSession(result as AuthSession);
    }
    return result;
  });
}

export function fetchMe(): Promise<{ user: AuthUser }> {
  return request("/auth/me");
}

export function logout(): Promise<void> {
  return request<{ ok: boolean }>("/auth/logout", { method: "POST" })
    .catch(() => ({ ok: true }))
    .then(() => {
      clearSession();
    });
}

export function todayIso(): string {
  return new Date().toLocaleDateString("en-CA");
}

export function fetchTodayDownloads(): Promise<DownloadIndex> {
  return request("/reports/today/latest");
}

export function fetchDownloads(date: string): Promise<DownloadIndex> {
  return request(`/reports/${date}`);
}

export function fetchReportDates(): Promise<{ dates: string[] }> {
  return request("/reports");
}

export function runPipeline(date?: string): Promise<RunResult> {
  return request("/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(date ? { date } : {}),
  });
}

export function regeneratePipeline(date: string): Promise<RunResult> {
  return request("/run/regenerate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date }),
  });
}

export function runQuickReport(): Promise<RunResult> {
  return request("/run/quick", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

export function pdfDownloadUrl(pdfUrl: string): string {
  if (pdfUrl.startsWith("http")) return pdfUrl;
  const base = API_URL.replace(/\/$/, "");
  return `${base}${pdfUrl}`;
}

export async function downloadPdf(
  pdfUrl: string,
  filename: string,
): Promise<void> {
  const url = pdfDownloadUrl(pdfUrl);
  const headers = new Headers(authHeaders());
  let res = await fetch(url, { headers });

  if (res.status === 401) {
    const refreshed = await tryRefreshSession();
    if (!refreshed) {
      clearSession();
      throw new Error("Session expired. Please sign in again.");
    }
    res = await fetch(url, { headers: new Headers(authHeaders()) });
  }

  if (!res.ok) {
    throw new Error("Failed to download PDF");
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}
