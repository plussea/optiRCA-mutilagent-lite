import { useState } from "react";
import { createSession, fetchSession, submitDecision } from "./lib/api";
import type { SessionState } from "./lib/types";
import { ReportPanel } from "./components/ReportPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import { Timeline } from "./components/Timeline";
import { UploadCard } from "./components/UploadCard";

export function App() {
  const [state, setState] = useState<SessionState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const created = await createSession(file);
      const next = await fetchSession(created.session_id);
      setState(next);
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
      const next = await fetchSession(state.session_id);
      setState(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen overflow-hidden bg-mist">
      <div className="pointer-events-none fixed -left-32 -top-32 h-96 w-96 rounded-full bg-brand/20 blur-3xl" />
      <div className="pointer-events-none fixed -bottom-40 right-0 h-96 w-96 rounded-full bg-cyan-300/20 blur-3xl" />
      <div className="relative mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[320px_1fr]">
        <div className="space-y-6 lg:col-span-2">
          <UploadCard busy={busy} onUpload={handleUpload} />
          {error && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {error}
            </div>
          )}
        </div>
        <div className="space-y-6">
          <Timeline status={state?.status} />
          <ReviewPanel state={state} onDecision={handleDecision} />
        </div>
        <ReportPanel state={state} />
      </div>
    </main>
  );
}
