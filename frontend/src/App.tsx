import { useCallback, useEffect, useMemo, useState } from "react";
import AuthForm from "./AuthForm";
import {
  AuthUser,
  DownloadEntry,
  downloadPdf,
  fetchDownloads,
  fetchMe,
  fetchReportDates,
  logout,
  regeneratePipeline,
  runPipeline,
  runQuickReport,
  todayIso,
} from "./api";
import { clearSession, getAccessToken } from "./auth";
import "./App.css";

export default function App() {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  const [downloads, setDownloads] = useState<DownloadEntry[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState(todayIso());
  const [loading, setLoading] = useState<"full" | "quick" | "regen" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canMutate = selectedDate >= todayIso();

  const dateOptions = useMemo(() => {
    const merged = new Set([todayIso(), ...dates, selectedDate]);
    return Array.from(merged).sort((a, b) => b.localeCompare(a));
  }, [dates, selectedDate]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      return;
    }
    fetchMe()
      .then(({ user: currentUser }) => setUser(currentUser))
      .catch(() => {
        clearSession();
        setUser(null);
      });
  }, []);

  const loadDates = useCallback(async () => {
    const list = await fetchReportDates();
    setDates(list.dates);
  }, []);

  const loadDownloads = useCallback(async (reportDate: string) => {
    setError(null);
    try {
      const index = await fetchDownloads(reportDate);
      setDownloads(index.downloads);
    } catch (err) {
      if (err instanceof Error && err.message.includes("404")) {
        setDownloads([]);
        return;
      }
      if (err instanceof Error && err.message.includes("Session expired")) {
        clearSession();
        setUser(null);
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load reports");
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    loadDates().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load dates");
    });
  }, [loadDates, user]);

  useEffect(() => {
    if (!user) return;
    loadDownloads(selectedDate);
  }, [loadDownloads, selectedDate, user]);

  function emailNotice(
    result: {
      email_sent?: boolean;
      email_to?: string | null;
      email_error?: string | null;
      attachment_count?: number;
      report_count: number;
      generated_count?: number;
      skipped_count?: number;
    },
    label: string,
  ) {
    if (result.email_sent && result.email_to) {
      const count = result.attachment_count ?? result.report_count;
      const files = count === 1 ? "1 PDF" : `${count} PDFs`;
      const generated =
        result.generated_count != null
          ? ` Generated ${result.generated_count}, skipped ${result.skipped_count ?? 0}.`
          : "";
      setNotice(
        `${label} emailed to ${result.email_to} (${files} attached).${generated}`,
      );
      return;
    }
    if (result.email_error) {
      setNotice(`${label} finished, but email failed: ${result.email_error}`);
    }
  }

  async function handleRun() {
    setLoading("full");
    setError(null);
    setNotice(null);
    try {
      const result = await runPipeline(selectedDate);
      setDownloads(result.downloads);
      emailNotice(result, "Reports");
      await loadDates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pipeline failed");
    } finally {
      setLoading(null);
    }
  }

  async function handleRegenerate() {
    setLoading("regen");
    setError(null);
    setNotice(null);
    try {
      const result = await regeneratePipeline(selectedDate);
      setDownloads(result.downloads);
      emailNotice(result, "Regenerated reports");
      await loadDates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Regenerate failed");
    } finally {
      setLoading(null);
    }
  }

  async function handleQuickTest() {
    setLoading("quick");
    setError(null);
    setNotice(null);
    try {
      const result = await runQuickReport();
      setDownloads(result.downloads);
      setSelectedDate(result.date);
      emailNotice(result, "Quick test");
      await loadDates();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quick test failed");
    } finally {
      setLoading(null);
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setDownloads([]);
    setDates([]);
    setError(null);
    setNotice(null);
  }

  async function handleDownload(entry: DownloadEntry) {
    setError(null);
    try {
      await downloadPdf(
        entry.pdf_url,
        `${entry.pdf_slug}-shunya-scout.pdf`,
      );
    } catch (err) {
      if (err instanceof Error && err.message.includes("Session expired")) {
        setUser(null);
      }
      setError(err instanceof Error ? err.message : "Download failed");
    }
  }

  if (user === undefined) {
    return (
      <main className="page">
        <p className="hint">Loading…</p>
      </main>
    );
  }

  if (!user) {
    return <AuthForm onAuthenticated={setUser} />;
  }

  const formattedDate = new Date(`${selectedDate}T12:00:00`).toLocaleDateString(
    "en-US",
    {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    },
  );

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Shunya Scout</h1>
          <p className="subtitle">{formattedDate}</p>
          <p className="user-label">{user.email}</p>
        </div>
        <div className="actions">
          <button className="logout-btn" onClick={handleLogout}>
            Sign out
          </button>
          <button
            className="quick-btn"
            onClick={handleQuickTest}
            disabled={loading !== null}
          >
            {loading === "quick" ? "Testing…" : "Quick Test PDF"}
          </button>
          {canMutate && (
            <button
              className="regen-btn"
              onClick={handleRegenerate}
              disabled={loading !== null}
            >
              {loading === "regen" ? "Regenerating…" : "Regenerate Day"}
            </button>
          )}
          <button
            className="run-btn"
            onClick={handleRun}
            disabled={loading !== null || !canMutate}
            title={
              canMutate
                ? "Generate missing reports for this date"
                : "Only today and future dates can be generated"
            }
          >
            {loading === "full" ? "Generating…" : "Generate Reports"}
          </button>
        </div>
      </header>

      <section className="toolbar">
        <label className="date-picker" htmlFor="report-date">
          Report date
        </label>
        <select
          id="report-date"
          className="date-select"
          value={selectedDate}
          onChange={(event) => setSelectedDate(event.target.value)}
        >
          {dateOptions.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </section>

      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      {downloads.length === 0 ? (
        <section className="empty">
          <p>No PDF reports for {selectedDate} yet.</p>
          {canMutate ? (
            <p className="hint">Generate reports for this matchday.</p>
          ) : (
            <p className="hint">Browse another date from the dropdown.</p>
          )}
        </section>
      ) : (
        <section className="downloads">
          {downloads.map((entry) => (
            <button
              key={entry.pdf_slug}
              type="button"
              className="download-card"
              onClick={() => handleDownload(entry)}
            >
              <div>
                <h2>
                  {entry.match.team_a}{" "}
                  <span className="vs">vs</span> {entry.match.team_b}
                </h2>
                <p className="file-label">
                  {entry.quick_test ? "Quick test PDF" : "Shunya Scout PDF"}
                </p>
              </div>
              <span className="download-icon">↓</span>
            </button>
          ))}
        </section>
      )}
    </main>
  );
}
