import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const EDITOR_TOKEN = import.meta.env.VITE_DEMO_EDITOR_TOKEN || "demo-editor-token";
const ADMIN_TOKEN = import.meta.env.VITE_DEMO_ADMIN_TOKEN || "demo-admin-token";

type Role = "editor" | "admin";
type Tab = "shows" | "validation" | "publish" | "history";
type Show = { id: number; show_id: string; title: string; section_id: string; category: string; description: string; default_language: string };
type Season = { id: number; show_id: number; season_number: number };
type Episode = { id: number; season_id: number; episode_id: string; content_group: string; episode_number: number; title: string; language: string; duration_seconds: number };
type Issue = { type: string; id?: number; owner_type?: "show" | "episode"; owner_id?: number; surface?: string; show_id?: string; episode_id?: string; message: string };
type Report = { valid: boolean; issues: Issue[] };
type Run = { id: number; status: string; started_at: string; completed_at?: string; version?: string; error?: string };

const emptyShow = { show_id: "", title: "", section_id: "drama", category: "Drama", description: "", default_language: "en" };
const emptyEpisode = { episode_id: "", content_group: "", episode_number: 1, title: "", language: "en", duration_seconds: 60 };

async function api(path: string, init: RequestInit = {}, token = EDITOR_TOKEN) {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(API + path, { ...init, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw Error(body?.detail?.error_summary || body?.detail || `${response.status} request failed`);
  return response.status === 204 ? null : body;
}

function App() {
  const [tab, setTab] = useState<Tab>("shows");
  const [role, setRole] = useState<Role>("editor");
  const [shows, setShows] = useState<Show[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Show>();
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState<number>();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [report, setReport] = useState<Report>();
  const [runs, setRuns] = useState<Run[]>([]);
  const [form, setForm] = useState(emptyShow);
  const [seasonNumber, setSeasonNumber] = useState(1);
  const [episodeForm, setEpisodeForm] = useState(emptyEpisode);
  const [editingEpisode, setEditingEpisode] = useState<number>();
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const token = role === "admin" ? ADMIN_TOKEN : EDITOR_TOKEN;
  const busy = (key: string) => Boolean(loading[key]);
  const run = async <T,>(key: string, action: () => Promise<T>) => {
    setLoading((current) => ({ ...current, [key]: true }));
    setError("");
    try { return await action(); } catch (caught) { setError((caught as Error).message); return undefined; }
    finally { setLoading((current) => ({ ...current, [key]: false })); }
  };

  const loadShows = async () => {
    const rows = await run("shows", () => api("/shows", {}, token));
    if (rows) setShows(rows);
  };
  const loadEpisodes = async (id: number) => {
    setSeasonId(id);
    const rows = await run("episodes", () => api(`/seasons/${id}/episodes`, {}, token));
    if (rows) setEpisodes(rows);
  };
  const loadShowDetails = async (show: Show) => {
    setSelected(show);
    setForm({ ...show });
    const rows = await run("seasons", () => api(`/shows/${show.id}/seasons`, {}, token));
    if (rows) {
      setSeasons(rows);
      const nextSeason = rows.find((season: Season) => season.id === seasonId)?.id || rows[0]?.id;
      setSeasonId(nextSeason);
      if (nextSeason) await loadEpisodes(nextSeason);
      else setEpisodes([]);
    }
  };
  useEffect(() => { void loadShows(); }, []);

  const saveShow = async () => {
    const saved = await run("save-show", () => api(selected ? `/shows/${selected.id}` : "/shows", { method: selected ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) }, token));
    if (saved) { setMessage(selected ? "Show updated." : "Show created."); setForm(emptyShow); await loadShows(); await loadShowDetails(saved); }
  };
  const saveSeason = async () => {
    if (!selected) return;
    const saved = await run("save-season", () => api(`/shows/${selected.id}/seasons`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ season_number: seasonNumber }) }, token));
    if (saved) { setMessage("Season created."); await loadShowDetails(selected); setSeasonNumber(seasonNumber + 1); }
  };
  const saveEpisode = async () => {
    if (!seasonId) return;
    const path = editingEpisode ? `/episodes/${editingEpisode}` : `/seasons/${seasonId}/episodes`;
    const saved = await run("save-episode", () => api(path, { method: editingEpisode ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(episodeForm) }, token));
    if (saved) { setMessage(editingEpisode ? "Episode updated." : "Episode created."); setEpisodeForm(emptyEpisode); setEditingEpisode(undefined); await loadEpisodes(seasonId); }
  };
  const loadReport = async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    setReportLoading(true);
    setError("");
    setTab("validation");
    try {
      const response = await fetch(`${API}/validation/report`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = typeof body?.detail === "string" ? body.detail : body?.detail ? JSON.stringify(body.detail) : `${response.status} request failed`;
        if (response.status === 401) throw Error("Editor authentication required to load validation.");
        if (response.status === 403) throw Error("Permission denied: validation requires an Editor or Admin token.");
        throw Error(detail);
      }
      if (!body || typeof body.valid !== "boolean" || !Array.isArray(body.issues)) throw Error("Validation response has an unexpected shape.");
      setReport(body as Report);
    } catch (caught) {
      setReport(undefined);
      setError(caught instanceof DOMException && caught.name === "AbortError" ? "Validation request timed out." : (caught as Error).message || "Unable to load validation report.");
    } finally {
      window.clearTimeout(timeout);
      setReportLoading(false);
    }
  };
  const loadRuns = async () => {
    const result = await run("runs", () => api("/publish/runs", {}, token));
    if (result) { setRuns(result); setTab("history"); }
  };
  const publish = async () => {
    if (role !== "admin") { setTab("publish"); setError("Admin required: publishing is restricted to the admin token."); return; }
    const result = await run("publish", () => api("/publish", { method: "POST" }, token));
    if (result) { setMessage(`Published ${result.version}.`); await loadRuns(); await loadReport(); setTab("publish"); }
  };
  const upload = async (issue: Issue, file?: File) => {
    if (!file || !issue.owner_type || !issue.owner_id || !issue.surface) return;
    const data = new FormData(); data.append("file", file);
    const result = await run("upload", () => api(`/artworks/upload?owner_type=${issue.owner_type}&owner_id=${issue.owner_id}&surface=${issue.surface}`, { method: "POST", body: data }, token));
    if (result) { setMessage("Artwork uploaded and validated."); await loadReport(); }
  };

  const filteredShows = shows.filter((show) => `${show.title} ${show.show_id} ${show.description}`.toLowerCase().includes(query.toLowerCase()));
  return <main>
    <header><div><small>PEBLO TV / CMS</small><h1>Catalogue workspace</h1></div><label className="role">Role <select value={role} onChange={(event) => setRole(event.target.value as Role)}><option value="editor">Editor</option><option value="admin">Admin</option></select></label></header>
    <nav>{([ ["shows", "Shows"], ["validation", "Validation report"], ["publish", "Publish"], ["history", "Publish history"] ] as [Tab, string][]).map(([value, label]) => <button className={tab === value ? "active" : ""} key={value} onClick={() => { setTab(value); if (value === "validation") void loadReport(); if (value === "history") void loadRuns(); }}>{label}</button>)}</nav>
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="good">{message}</p>}
    {tab === "shows" && <>
      <div className="toolbar"><input className="search" placeholder="Search shows" value={query} onChange={(event) => setQuery(event.target.value)} /><button onClick={() => { setSelected(undefined); setForm(emptyShow); }}>New show</button></div>
      {busy("shows") && <p className="state">Loading shows...</p>}{!busy("shows") && !error && filteredShows.length === 0 && <p className="state">No shows match your search.</p>}
      <section className="grid">{filteredShows.map((show) => <article key={show.id}><h2>{show.title}</h2><p>{show.show_id} · {show.category} / {show.section_id}</p><p>{show.description || "No description."}</p><button onClick={() => void loadShowDetails(show)}>Edit / manage</button><div className="slots">{["poster", "banner", "thumbnail"].map((surface) => <label key={surface}>{surface}<input type="file" accept="image/*" onChange={(event) => void upload({ type: "artwork", owner_type: "show", owner_id: show.id, surface, message: "" }, event.target.files?.[0])} /></label>)}</div></article>)}</section>
      <section className="editor"><h2>{selected ? `Edit ${selected.title}` : "Create show"}</h2><div className="form-grid">{(["show_id", "title", "section_id", "category", "description", "default_language"] as const).map((field) => <input key={field} placeholder={field} value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} />)}</div><button onClick={() => void saveShow()} disabled={busy("save-show")}>{busy("save-show") ? "Saving..." : selected ? "Save show" : "Create show"}</button></section>
      {selected && <section className="editor"><h2>{selected.title}: seasons and episodes</h2><div className="inline"><input type="number" min="0" value={seasonNumber} onChange={(event) => setSeasonNumber(Number(event.target.value))} /><button onClick={() => void saveSeason()} disabled={busy("save-season")}>Add season</button></div>{busy("seasons") ? <p className="state">Loading seasons...</p> : seasons.length === 0 ? <p className="state">No seasons yet.</p> : <div className="season-list">{seasons.map((season) => <button className={season.id === seasonId ? "selected" : ""} key={season.id} onClick={() => void loadEpisodes(season.id)}>Season {season.season_number}</button>)}</div>}{seasonId && <><h3>{editingEpisode ? "Edit episode" : "Add episode"}</h3><div className="form-grid">{(["episode_id", "content_group", "title", "language", "duration_seconds"] as const).map((field) => <input key={field} type={field === "duration_seconds" ? "number" : "text"} placeholder={field} value={episodeForm[field]} onChange={(event) => setEpisodeForm({ ...episodeForm, [field]: field === "duration_seconds" ? Number(event.target.value) : event.target.value })} />)}<input type="number" min="1" placeholder="episode_number" value={episodeForm.episode_number} onChange={(event) => setEpisodeForm({ ...episodeForm, episode_number: Number(event.target.value) })} /></div><button onClick={() => void saveEpisode()} disabled={busy("save-episode")}>{editingEpisode ? "Save episode" : "Add episode"}</button>{editingEpisode && <button onClick={() => { setEditingEpisode(undefined); setEpisodeForm(emptyEpisode); }}>Cancel</button>}<h3>Episodes</h3>{busy("episodes") ? <p className="state">Loading episodes...</p> : episodes.length === 0 ? <p className="state">No episodes in this season.</p> : episodes.map((episode) => <div className="episode" key={episode.id}><span>#{episode.episode_number} {episode.title} ({episode.language})</span><button onClick={() => { setEditingEpisode(episode.id); setEpisodeForm({ episode_id: episode.episode_id, content_group: episode.content_group, episode_number: episode.episode_number, title: episode.title, language: episode.language, duration_seconds: episode.duration_seconds }); }}>Edit</button></div>)}</>}</section>}
    </>}
    {tab === "validation" && <section className="report"><h2>Validation report</h2>{reportLoading ? <p className="state">Checking catalogue...</p> : report ? <><strong className={report.valid ? "valid" : "invalid"}>{report.valid ? "Valid: ready to publish" : `Invalid: ${report.issues.length} issue${report.issues.length === 1 ? "" : "s"}`}</strong>{report.issues.length === 0 ? <p>No validation issues found.</p> : report.issues.map((issue, index) => <div className="issue" key={`${issue.type}-${issue.id || issue.show_id || issue.episode_id}-${index}`}><p><b>{issue.type}</b>: {issue.message}</p>{issue.type === "artwork" && <input type="file" accept="image/*" onChange={(event) => void upload(issue, event.target.files?.[0])} />}</div>)}</> : <p className="state">No report loaded.</p>}</section>}
    {tab === "publish" && <section className="report"><h2>Publish</h2>{role === "editor" ? <p className="error">Admin required. The Editor token cannot publish.</p> : <><p>Publishing uses the backend-authorized Admin token.</p><button onClick={() => void publish()} disabled={busy("publish")}>{busy("publish") ? "Publishing..." : "Publish catalogue"}</button></>}</section>}
    {tab === "history" && <section className="report"><h2>Publish history</h2>{role === "editor" ? <p className="error">Admin required. Publish history is restricted to the Admin token.</p> : busy("runs") ? <p className="state">Loading publish history...</p> : runs.length === 0 ? <p className="state">No publish runs found.</p> : <div className="history">{runs.map((run) => <div className="run" key={run.id}><strong>{run.status}</strong><span>Started: {new Date(run.started_at).toLocaleString()}</span>{run.completed_at && <span>Completed: {new Date(run.completed_at).toLocaleString()}</span>}<span>{run.version || run.error || "No details"}</span></div>)}</div>}</section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<App />);
