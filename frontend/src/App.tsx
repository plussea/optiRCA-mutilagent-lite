import { useState } from "react";
import { diagnose } from "./lib/api";
import { runDemoDiagnose } from "./lib/demo";
import type { DiagnosisResult } from "./lib/types";
import { ConclusionBar } from "./components/ConclusionBar";
import { EvidenceGraphView } from "./components/EvidenceGraphView";
import { RightDrawer } from "./components/RightDrawer";
import { StageTimeline, useStagePlayback } from "./components/StageTimeline";
import { TopologyInput } from "./components/TopologyInput";

export function App() {
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [topologyInput, setTopologyInput] = useState(
    JSON.stringify({ devices: [], ports: [], links: [] }, null, 2),
  );

  const { currentStage, playing, seek, play, pause, replay } = useStagePlayback(result);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    setSelectedId(null);
    try {
      const topology = JSON.parse(topologyInput);
      const response = await diagnose(file, topology);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRunDemo() {
    setBusy(true);
    setError(null);
    setResult(null);
    setSelectedId(null);
    try {
      const response = await runDemoDiagnose();
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const body: DiagnosisResult = await response.json();
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-200">
      <ConclusionBar
        result={result}
        busy={busy}
        onUpload={handleUpload}
        onRunDemo={handleRunDemo}
        onOpenReview={() => {}}
      />

      <StageTimeline
        result={result}
        currentStage={currentStage}
        playing={playing}
        onPlay={play}
        onPause={pause}
        onSeek={seek}
        onReplay={replay}
      />

      <div className="relative flex min-h-0 flex-1">
        <main className="relative flex min-h-0 flex-1 flex-col">
          {!result ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8">
              <div className="text-center">
                <p className="text-2xl font-bold text-slate-100">OptiRCA Lite</p>
                <p className="mt-2 text-sm text-slate-400">
                  上传告警 CSV 与拓扑 JSON，或运行 Demo 查看智能根因诊断。
                </p>
              </div>
              <TopologyInput value={topologyInput} onChange={setTopologyInput} />
              {error && (
                <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-sm rounded-xl border border-slate-700/60 bg-slate-900/80 p-3 backdrop-blur"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  拓扑输入（JSON）
                </p>
                <TopologyInput compact value={topologyInput} onChange={setTopologyInput} />
              </div>
              <EvidenceGraphView
                graph={result.evidence_graph}
                rootCause={
                  result.root_cause && "root_cause" in result.root_cause
                    ? result.root_cause.root_cause
                    : undefined
                }
                currentStage={currentStage}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
              {error && (
                <div className="absolute bottom-4 left-4 z-10 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}
            </>
          )}
        </main>

        <RightDrawer result={result} selectedId={selectedId} />
      </div>
    </div>
  );
}
