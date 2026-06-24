import { useEffect, useRef, useState } from "react";
import { createDemoSession, createSession, fetchEvents, fetchSession, submitDecision } from "./lib/api";
import type { SessionState, WorkflowEvent } from "./lib/types";
import { AuditTrail } from "./components/AuditTrail";
import { NodeInspector } from "./components/NodeInspector";
import { ReportPanel } from "./components/ReportPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import { UploadCard } from "./components/UploadCard";
import { WorkflowGraph } from "./components/WorkflowGraph";

const terminalStatuses = new Set(["waiting_review", "closed", "rejected", "escalated", "error"]);

export function App() {
  const [state, setState] = useState<SessionState | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [selectedNode, setSelectedNode] = useState("perception");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  async function refresh(sessionId: string) {
    const [nextState, nextEvents] = await Promise.all([fetchSession(sessionId), fetchEvents(sessionId)]);
    setState(nextState);
    setEvents(nextEvents);
    return nextState;
  }

  function startPolling(sessionId: string) {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const next = await refresh(sessionId);
        if (terminalStatuses.has(next.status)) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        if (pollRef.current) window.clearInterval(pollRef.current);
      }
    }, 900);
  }

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    setEvents([]);
    setState(null);
    setSelectedNode("perception");
    try {
      const created = await createSession(file);
      await refresh(created.session_id);
      startPolling(created.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRunDemo() {
    setBusy(true);
    setError(null);
    setEvents([]);
    setState(null);
    setSelectedNode("perception");
    try {
      const created = await createDemoSession();
      await refresh(created.session_id);
      startPolling(created.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(decision: "approved" | "rejected" | "escalated", notes: string) {
    if (!state) return;
    setBusy(true);
    setError(null);
    try {
      await submitDecision(state.session_id, decision, notes);
      await refresh(state.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="runtime-grid min-h-screen overflow-hidden bg-mist">
      <div className="pointer-events-none fixed -left-32 -top-32 h-96 w-96 rounded-full bg-brand/20 blur-3xl" />
      <div className="pointer-events-none fixed -bottom-40 right-0 h-96 w-96 rounded-full bg-cyanline/20 blur-3xl" />
      <div className="relative mx-auto max-w-[1540px] space-y-6 px-6 py-8">
        <UploadCard busy={busy} onUpload={handleUpload} onRunDemo={handleRunDemo} />
        {error && (
          <div className="rounded-2xl border border-rose-400/40 bg-rose-950/60 p-4 text-sm text-rose-100">
            {error}
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_390px]">
          <WorkflowGraph
            state={state}
            events={events}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
          />
          <NodeInspector state={state} events={events} selectedNode={selectedNode} />
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_390px]">
          <ReportPanel state={state} />
          <div className="space-y-6">
            <ReviewPanel state={state} onDecision={handleDecision} />
            <AuditTrail events={events} />
          </div>
        </div>
      </div>
    </main>
  );
}
