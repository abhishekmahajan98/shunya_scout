import { useCallback, useEffect, useState } from "react";
import {
  DownloadEntry,
  fetchReportDates,
  fetchTodayDownloads,
  pdfDownloadUrl,
  runPipeline,
  runQuickReport,
} from "./api";
import "./App.css";

export default function App() {
  const [downloads, setDownloads] = useState<DownloadEntry[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [loading, setLoading] = useState<"full" | "quick" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [today, list] = await Promise.all([
        fetchTodayDownloads().catch(() => null),
        fetchReportDates(),
      ]);
      setDownloads(today?.downloads ?? []);
      setDates(list.dates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRun() {
    setLoading("full");
    setError(null);
    setNotice(null);
    try {
      const result = await runPipeline();
      setDownloads(result.downloads);
      if (result.email_sent && result.email_to) {
        const count = result.attachment_count ?? result.report_count;
        const files = count === 1 ? "1 PDF" : `${count} PDFs`;
        setNotice(
          `Reports generated and emailed to ${result.email_to} (${files} attached).`,
        );
      } else if (result.email_error) {
        setNotice(`Reports generated, but email failed: ${result.email_error}`);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pipeline failed");
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
      if (result.email_sent && result.email_to) {
        const count = result.attachment_count ?? result.report_count;
        const files = count === 1 ? "1 PDF" : `${count} PDFs`;
        setNotice(
          `Quick test emailed to ${result.email_to} (${files} attached).`,
        );
      } else if (result.email_error) {
        setNotice(`Quick test generated, but email failed: ${result.email_error}`);
      }
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quick test failed");
    } finally {
      setLoading(null);
    }
  }

  const formattedDate = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Shunya Scout</h1>
          <p className="subtitle">{formattedDate}</p>
        </div>
        <div className="actions">
          <button
            className="quick-btn"
            onClick={handleQuickTest}
            disabled={loading !== null}
          >
            {loading === "quick" ? "Testing…" : "Quick Test PDF"}
          </button>
          <button
            className="run-btn"
            onClick={handleRun}
            disabled={loading !== null}
          >
            {loading === "full" ? "Generating…" : "Generate Reports"}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      {downloads.length === 0 ? (
        <section className="empty">
          <p>No PDF reports for today yet.</p>
          {dates.length > 0 && (
            <p className="hint">Latest report date: {dates[0]}</p>
          )}
        </section>
      ) : (
        <section className="downloads">
          {downloads.map((entry) => (
            <a
              key={entry.pdf_slug}
              className="download-card"
              href={pdfDownloadUrl(entry.pdf_url)}
              download={`${entry.pdf_slug}-shunya-scout.pdf`}
            >
              <div>
                <h2>
                  {entry.match.team_a}{" "}
                  <span className="vs">vs</span> {entry.match.team_b}
                </h2>
                <p className="file-label">Shunya Scout PDF</p>
              </div>
              <span className="download-icon">↓</span>
            </a>
          ))}
        </section>
      )}
    </main>
  );
}
