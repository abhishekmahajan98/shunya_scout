import { useCallback, useEffect, useMemo, useState } from "react";
import AuthForm from "./AuthForm";
import {
  AuthUser,
  DownloadEntry,
  FixtureOption,
  downloadPdf,
  fetchDownloads,
  fetchMe,
  fetchReportDates,
  fetchUpcomingFixtures,
  logout,
  runPipeline,
  todayIso,
  tomorrowIso,
} from "./api";
import { clearSession, getAccessToken } from "./auth";
import "./App.css";

function formatDayLabel(dateValue: string): string {
  const label = new Date(`${dateValue}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
  if (dateValue === todayIso()) return `Today · ${label}`;
  if (dateValue === tomorrowIso()) return `Tomorrow · ${label}`;
  return label;
}

function formatKickoff(kickoff: string | null): string {
  if (!kickoff) return "Kickoff TBD";
  return new Date(kickoff).toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function groupByDate(fixtures: FixtureOption[]): Map<string, FixtureOption[]> {
  const groups = new Map<string, FixtureOption[]>();
  for (const fixture of fixtures) {
    const list = groups.get(fixture.report_date) ?? [];
    list.push(fixture);
    groups.set(fixture.report_date, list);
  }
  return groups;
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);
  const [fixtures, setFixtures] = useState<FixtureOption[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [downloads, setDownloads] = useState<DownloadEntry[]>([]);
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState(todayIso());
  const [loadingFixtures, setLoadingFixtures] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fixtureGroups = useMemo(() => groupByDate(fixtures), [fixtures]);

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

  const loadUpcoming = useCallback(async () => {
    setLoadingFixtures(true);
    setError(null);
    try {
      const data = await fetchUpcomingFixtures();
      setFixtures(data.fixtures);
      setSelectedIds((current) => {
        const valid = new Set(data.fixtures.map((item) => item.fixture_id));
        const next = new Set<number>();
        for (const id of current) {
          if (valid.has(id)) next.add(id);
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load fixtures");
    } finally {
      setLoadingFixtures(false);
    }
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
    loadUpcoming();
    loadDates().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load dates");
    });
  }, [loadDates, loadUpcoming, user]);

  useEffect(() => {
    if (!user) return;
    loadDownloads(selectedDate);
  }, [loadDownloads, selectedDate, user]);

  function toggleFixture(fixtureId: number) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(fixtureId)) next.delete(fixtureId);
      else next.add(fixtureId);
      return next;
    });
  }

  function toggleDay(dateValue: string) {
    const dayFixtures = fixtureGroups.get(dateValue) ?? [];
    const dayIds = dayFixtures.map((item) => item.fixture_id);
    const allSelected = dayIds.every((id) => selectedIds.has(id));
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const id of dayIds) {
        if (allSelected) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  function selectMissingReports() {
    setSelectedIds(
      new Set(
        fixtures
          .filter((fixture) => !fixture.has_report)
          .map((fixture) => fixture.fixture_id),
      ),
    );
  }

  function emailNotice(result: {
    email_sent?: boolean;
    email_to?: string | null;
    email_error?: string | null;
    attachment_count?: number;
    generated_count?: number;
  }) {
    if (result.email_sent && result.email_to) {
      const count = result.attachment_count ?? result.generated_count ?? 0;
      const files = count === 1 ? "1 PDF" : `${count} PDFs`;
      setNotice(`Reports emailed to ${result.email_to} (${files} attached).`);
      return;
    }
    if (result.email_error) {
      setNotice(`Reports finished, but email failed: ${result.email_error}`);
    }
  }

  async function handleGenerateSelected() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      setError("Select at least one match to generate.");
      return;
    }

    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const result = await runPipeline(ids);
      const generated = result.generated_count ?? 0;
      const skipped = result.skipped_count ?? 0;
      let message = `Generated ${generated} report${generated === 1 ? "" : "s"}.`;
      if (skipped > 0) {
        message += ` ${skipped} skipped.`;
      }
      setNotice(message);
      emailNotice(result);
      await Promise.all([loadUpcoming(), loadDates()]);
      if (selectedDate) await loadDownloads(selectedDate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setFixtures([]);
    setSelectedIds(new Set());
    setDownloads([]);
    setDates([]);
    setError(null);
    setNotice(null);
  }

  async function handleDownload(pdfUrl: string, filename: string) {
    setError(null);
    try {
      await downloadPdf(pdfUrl, filename);
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

  const selectedCount = selectedIds.size;

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Shunya Scout</h1>
          <p className="subtitle">Morning match reports · today & tomorrow</p>
          <p className="user-label">{user.email}</p>
        </div>
        <div className="actions">
          <button className="logout-btn" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Upcoming fixtures</h2>
            <p className="panel-subtitle">
              Select the matches you want reports for, then generate.
            </p>
          </div>
          <div className="panel-actions">
            <button
              type="button"
              className="ghost-btn"
              onClick={selectMissingReports}
              disabled={loadingFixtures || generating}
            >
              Select missing
            </button>
            <button
              type="button"
              className="run-btn"
              onClick={handleGenerateSelected}
              disabled={generating || selectedCount === 0}
            >
              {generating
                ? "Generating…"
                : `Generate selected (${selectedCount})`}
            </button>
          </div>
        </div>

        {loadingFixtures ? (
          <p className="hint">Loading fixtures…</p>
        ) : fixtures.length === 0 ? (
          <p className="hint">No fixtures scheduled for today or tomorrow.</p>
        ) : (
          <div className="fixture-groups">
            {Array.from(fixtureGroups.entries()).map(([dateValue, dayFixtures]) => {
              const dayIds = dayFixtures.map((item) => item.fixture_id);
              const allSelected =
                dayIds.length > 0 &&
                dayIds.every((id) => selectedIds.has(id));
              return (
                <section key={dateValue} className="fixture-group">
                  <div className="fixture-group-header">
                    <h3>{formatDayLabel(dateValue)}</h3>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => toggleDay(dateValue)}
                    >
                      {allSelected ? "Deselect day" : "Select day"}
                    </button>
                  </div>
                  <div className="fixture-list">
                    {dayFixtures.map((fixture) => {
                      const checked = selectedIds.has(fixture.fixture_id);
                      const location = [fixture.venue, fixture.city]
                        .filter(Boolean)
                        .join(", ");
                      return (
                        <label
                          key={fixture.fixture_id}
                          className={`fixture-card${checked ? " fixture-card-selected" : ""}`}
                        >
                          <input
                            type="checkbox"
                            className="fixture-checkbox"
                            checked={checked}
                            onChange={() => toggleFixture(fixture.fixture_id)}
                          />
                          <div className="fixture-body">
                            <div className="fixture-topline">
                              <h4>
                                {fixture.team_a}{" "}
                                <span className="vs">vs</span> {fixture.team_b}
                              </h4>
                              {fixture.has_report && (
                                <span className="status-badge">Report ready</span>
                              )}
                            </div>
                            <p className="fixture-meta">
                              {formatKickoff(fixture.kickoff)}
                              {location ? ` · ${location}` : ""}
                            </p>
                            <p className="fixture-meta">{fixture.stage}</p>
                          </div>
                          {fixture.has_report && fixture.pdf_url && (
                            <button
                              type="button"
                              className="download-inline-btn"
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                handleDownload(
                                  fixture.pdf_url!,
                                  `${fixture.pdf_slug}-shunya-scout.pdf`,
                                );
                              }}
                            >
                              PDF
                            </button>
                          )}
                        </label>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Saved reports</h2>
            <p className="panel-subtitle">Browse PDFs from previous matchdays.</p>
          </div>
        </div>

        <div className="toolbar">
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
        </div>

        {downloads.length === 0 ? (
          <p className="hint">No PDF reports saved for {selectedDate}.</p>
        ) : (
          <section className="downloads">
            {downloads.map((entry) => (
              <button
                key={entry.pdf_slug}
                type="button"
                className="download-card"
                onClick={() =>
                  handleDownload(
                    entry.pdf_url,
                    `${entry.pdf_slug}-shunya-scout.pdf`,
                  )
                }
              >
                <div>
                  <h2>
                    {entry.match.team_a}{" "}
                    <span className="vs">vs</span> {entry.match.team_b}
                  </h2>
                  <p className="file-label">Shunya Scout PDF</p>
                </div>
                <span className="download-icon">↓</span>
              </button>
            ))}
          </section>
        )}
      </section>

      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}
    </main>
  );
}
