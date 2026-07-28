import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

// ─── Types (match server JSON verbatim) ───────────────────────────
type Status = {
  running: boolean;
  total_experiments: number;
  best_score: number;
  budget_remaining: number;
  uptime: number;
};
type Experiment = {
  id: string;
  hypothesis: string;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  score: number;
  status: "completed" | "reverted" | "failed";
  timestamp: string;
  git_hash: string;
  duration_seconds: number;
  budget_remaining?: number;
};

// Runtime server URL — window global for Tauri, fall back to same-origin.
const API = (window as unknown as { AUTOCLAW_URL?: string }).AUTOCLAW_URL ?? "";

// ─── Small pieces ─────────────────────────────────────────────────

function Sparkline({ scores }: { scores: number[] }) {
  if (scores.length < 2) return <div className="spark-empty">no data yet</div>;
  const w = 640, h = 120, pad = 6;
  const max = Math.max(...scores), min = Math.min(...scores);
  const span = max - min || 1;
  const step = (w - pad * 2) / (scores.length - 1);
  const pts = scores.map((s, i) => {
    const x = pad + i * step;
    const y = h - pad - ((s - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const lastX = pad + (scores.length - 1) * step;
  const lastY = h - pad - ((scores[scores.length - 1] - min) / span) * (h - pad * 2);
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-label="Score history">
      <polyline points={pts.join(" ")} fill="none" stroke="var(--accent-2)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={lastX} cy={lastY} r="4" fill="var(--accent-2)"/>
    </svg>
  );
}

function StatusPill({ s }: { s: string }) {
  return <span className={`pill pill-${s}`}>{s}</span>;
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [context, setContext] = useState("");
  const [tab, setTab] = useState<"live" | "history" | "context">("live");
  const [connected, setConnected] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  // Initial hydrate + SSE stream
  useEffect(() => {
    fetch(`${API}/api/status`).then(r => r.json()).then(setStatus).catch(() => {});
    fetch(`${API}/api/results`).then(r => r.json()).then(setExperiments).catch(() => {});
    fetch(`${API}/api/context`).then(r => r.text()).then(setContext).catch(() => {});

    const es = new EventSource(`${API}/events`);
    sseRef.current = es;
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.id && typeof data.score === "number") {
          setExperiments(prev => {
            const idx = prev.findIndex(e => e.id === data.id);
            if (idx >= 0) { const next = [...prev]; next[idx] = data; return next; }
            return [...prev, data];
          });
        }
      } catch { /* skip non-JSON */ }
    };

    const poll = setInterval(() => {
      fetch(`${API}/api/status`).then(r => r.json()).then(setStatus).catch(() => {});
    }, 3000);

    return () => { es.close(); clearInterval(poll); };
  }, []);

  const post = useCallback(async (path: string) => {
    await fetch(`${API}${path}`, { method: "POST" });
    fetch(`${API}/api/status`).then(r => r.json()).then(setStatus);
  }, []);

  const saveContext = useCallback(async () => {
    await fetch(`${API}/api/context`, { method: "POST", body: context });
  }, [context]);

  // Keyboard shortcuts: S=start, X=stop, R=reset, 1/2/3=tabs
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA") return;
      if (e.key === "s") post("/api/start");
      else if (e.key === "x") post("/api/stop");
      else if (e.key === "r") { if (confirm("Reset all state?")) post("/api/reset"); }
      else if (e.key === "1") setTab("live");
      else if (e.key === "2") setTab("history");
      else if (e.key === "3") setTab("context");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [post]);

  const scores = useMemo(() => experiments.map(e => e.score), [experiments]);
  const best = useMemo(() => experiments.reduce((a, b) => b.score > (a?.score ?? -Infinity) ? b : a, experiments[0]), [experiments]);
  const running = status?.running ?? false;
  const budgetLeft = status?.budget_remaining ?? 0;
  const totalExp = experiments.length;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="mark">⟲</span>
          <span className="name">autoclaw</span>
          <span className={`pulse ${connected ? "on" : "off"}`} title={connected ? "connected" : "disconnected"}/>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "live"} onClick={() => setTab("live")} className={tab === "live" ? "active" : ""}><kbd>1</kbd>Live</button>
          <button role="tab" aria-selected={tab === "history"} onClick={() => setTab("history")} className={tab === "history" ? "active" : ""}><kbd>2</kbd>History</button>
          <button role="tab" aria-selected={tab === "context"} onClick={() => setTab("context")} className={tab === "context" ? "active" : ""}><kbd>3</kbd>Context</button>
        </nav>
        <div className="actions">
          <button className="btn" onClick={() => post("/api/start")} disabled={running}><kbd>S</kbd>Start</button>
          <button className="btn" onClick={() => post("/api/stop")} disabled={!running}><kbd>X</kbd>Stop</button>
        </div>
      </header>

      <main>
        {tab === "live" && (
          <section className="grid">
            <StatCard label="Experiments" value={String(totalExp)}/>
            <StatCard label="Best score" value={best ? best.score.toFixed(4) : "—"} hint={best ? best.id : undefined}/>
            <StatCard label="Budget left" value={`${budgetLeft.toFixed(0)}s`} hint={running ? "running" : "idle"}/>
            <StatCard label="Uptime" value={status ? formatDuration(status.uptime) : "—"}/>

            <div className="panel span-4">
              <div className="panel-head">Score history <span className="muted">· {totalExp} runs</span></div>
              <Sparkline scores={scores}/>
            </div>

            <div className="panel span-4">
              <div className="panel-head">Recent experiments</div>
              <ExperimentTable experiments={experiments.slice(-8).reverse()}/>
            </div>
          </section>
        )}

        {tab === "history" && (
          <section>
            <div className="panel">
              <div className="panel-head">All experiments <span className="muted">· {totalExp} total</span></div>
              <ExperimentTable experiments={[...experiments].reverse()}/>
            </div>
          </section>
        )}

        {tab === "context" && (
          <section className="ctx">
            <div className="panel">
              <div className="panel-head">context.md <span className="muted">· your goals</span></div>
              <textarea value={context} onChange={e => setContext(e.target.value)} spellCheck={false} aria-label="Context editor"/>
              <div className="ctx-actions">
                <button className="btn btn-accent" onClick={saveContext}>Save</button>
                <span className="muted">Tip: edit here, then <kbd>S</kbd> to start a new loop.</span>
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="footer">
        <span className="muted">
          {running ? "● running" : "○ idle"} · {connected ? "SSE connected" : "SSE offline"} ·
          <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> tabs · <kbd>S</kbd> start · <kbd>X</kbd> stop · <kbd>R</kbd> reset
        </span>
      </footer>
    </div>
  );
}

function ExperimentTable({ experiments }: { experiments: Experiment[] }) {
  if (experiments.length === 0) return <div className="empty">No experiments yet. Set your context, then <kbd>S</kbd>tart.</div>;
  return (
    <table className="tbl">
      <thead>
        <tr><th>ID</th><th>Hypothesis</th><th className="num">Score</th><th>Status</th><th className="num">Dur</th><th>Git</th></tr>
      </thead>
      <tbody>
        {experiments.map(e => (
          <tr key={e.id}>
            <td className="mono">{e.id}</td>
            <td className="hypo">{e.hypothesis}</td>
            <td className="num mono">{e.score.toFixed(4)}</td>
            <td><StatusPill s={e.status}/></td>
            <td className="num mono muted">{e.duration_seconds.toFixed(1)}s</td>
            <td className="mono muted">{e.git_hash.slice(0, 7) || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatDuration(s: number): string {
  if (s < 60) return `${s.toFixed(0)}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}
