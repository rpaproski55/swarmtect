// Minimal judge cockpit: scenario buttons call the REAL API, counters come from /api/metrics.
// Build with Vite + React + TS (npm create vite@latest) — this file is the app entry component.
import { useEffect, useState } from "react";

const SECRET = "demo-operator-secret-change-me"; // demo only; real deployments use a server-side secret

export default function App() {
  const [metrics, setMetrics] = useState<any>(null);
  const [episodes, setEpisodes] = useState<any[]>([]);
  const refresh = async () => {
    setMetrics(await (await fetch("/api/metrics")).json());
    setEpisodes(await (await fetch("/api/episodes")).json());
  };
  useEffect(() => { refresh(); }, []);
  const run = async (scenario: string) => {
    await fetch("/api/demo/reset", { method: "POST", headers: { "x-operator-secret": SECRET } });
    await fetch("/api/demo/run", { method: "POST", headers: { "Content-Type": "application/json", "x-operator-secret": SECRET }, body: JSON.stringify({ scenario }) });
    refresh();
  };
  return (
    <div style={{ background: "#0b0f14", color: "#e6edf3", fontFamily: "system-ui", padding: 24, minHeight: "100vh" }}>
      <h1>SwarmGuard — coordination episode cockpit</h1>
      <p>Backend: {metrics?.store_backend} · Events: {metrics?.events_processed} · Blocked before effect: {metrics?.blocked_before_effect} · Episodes: {metrics?.episodes_detected} · Quarantined: {metrics?.agents_quarantined}</p>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => run("S1")}>Run BENIGN collaboration (challenge)</button>
        <button onClick={() => run("S2")} style={{ background: "#7a1f1f", color: "#fff" }}>Trigger unauthorized shared board</button>
        <button onClick={() => run("S3")}>Run fragmented coordination</button>
        <button onClick={() => run("S4")}>Run trace mismatch</button>
      </div>
      {episodes.map((ep) => (
        <div key={ep._id} style={{ border: "1px solid #30363d", borderRadius: 8, padding: 16, marginTop: 16 }}>
          <strong>{ep._id}</strong> — {ep.status} · risk {ep.risk_score} · rules {ep.triggered_rules.join(", ")}
          <div>Agents: {ep.agent_ids.join(", ")}</div>
          <div>Evidence events: {ep.evidence_event_ids.join(", ")}</div>
          <div>{ep.explanation}</div>
        </div>
      ))}
      {episodes.length === 0 && <p style={{ marginTop: 16 }}>No episodes. Benign work is not flagged.</p>}
    </div>
  );
}
