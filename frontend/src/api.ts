export interface Match {
  team_a: string;
  team_b: string;
}

export interface DownloadEntry {
  match: Match;
  pdf_slug: string;
  pdf_url: string;
}

export interface DownloadIndex {
  date: string;
  downloads: DownloadEntry[];
}

export interface RunResult {
  date: string;
  match_count: number;
  report_count: number;
  downloads: DownloadEntry[];
  email_sent?: boolean;
  email_to?: string | null;
  email_error?: string | null;
  attachment_count?: number;
}

const API_URL = import.meta.env.VITE_API_URL || "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
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
