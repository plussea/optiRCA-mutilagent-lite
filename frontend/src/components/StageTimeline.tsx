import { Play, Pause, RotateCcw, SkipBack, SkipForward } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { DiagnosisResult } from "../lib/types";

export type StageId = "perception" | "topology" | "judge" | "rank" | "critic" | "assemble";

export interface StageState {
  id: StageId;
  label: string;
  state: "idle" | "running" | "done" | "error";
}

interface Props {
  result: DiagnosisResult | null;
  currentStage: StageId | null;
  playing: boolean;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (stage: StageId) => void;
  onReplay: () => void;
}

const STAGES: StageId[] = ["perception", "topology", "judge", "rank", "critic", "assemble"];
const STAGE_LABELS: Record<StageId, string> = {
  perception: "感知",
  topology: "拓扑",
  judge: "Judge",
  rank: "Rank",
  critic: "Critic",
  assemble: "组装",
};

export function useStagePlayback(result: DiagnosisResult | null) {
  const [currentStage, setCurrentStage] = useState<StageId | null>(null);
  const [playing, setPlaying] = useState(false);

  const completed = useMemo(() => new Set(result?.metadata?.phases_completed ?? []), [result]);

  const hasError = useMemo(() => {
    if (!result) return false;
    const degraded = result.status === "degraded";
    const failedAssemble =
      degraded && result.degradation_reason &&
      (result.degradation_reason.includes("timeout") ||
        result.degradation_reason.includes("failure") ||
        result.degradation_reason === "max_fallback_exceeded");
    return failedAssemble;
  }, [result]);

  const stages: StageState[] = useMemo(
    () =>
      STAGES.map((id) => {
        let state: StageState["state"] = "idle";
        if (currentStage === id) state = playing ? "running" : "running";
        else if (completed.has(id)) state = "done";
        else if (id === "assemble" && hasError) state = "error";
        return { id, label: STAGE_LABELS[id], state };
      }),
    [completed, currentStage, hasError, playing],
  );

  // Auto-play when result arrives.
  useEffect(() => {
    if (!result) {
      setCurrentStage(null);
      setPlaying(false);
      return;
    }
    setCurrentStage(null);
    setPlaying(true);
  }, [result]);

  // Advance stages on a timer while playing.
  useEffect(() => {
    if (!playing || !result) return;
    if (currentStage === "assemble") {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => {
      setCurrentStage((prev) => {
        const idx = prev === null ? -1 : STAGES.indexOf(prev);
        const next = STAGES[idx + 1] ?? "perception";
        return next;
      });
    }, 900);
    return () => window.clearTimeout(timer);
  }, [playing, currentStage, result]);

  const seek = (stage: StageId) => {
    setCurrentStage(stage);
    setPlaying(false);
  };

  const play = () => setPlaying(true);
  const pause = () => setPlaying(false);
  const replay = () => {
    setCurrentStage(null);
    setPlaying(true);
  };

  return {
    stages,
    currentStage,
    playing,
    seek,
    play,
    pause,
    replay,
  };
}

export function StageTimeline({
  result,
  currentStage,
  playing,
  onPlay,
  onPause,
  onSeek,
  onReplay,
}: Props) {
  const completed = useMemo(() => new Set(result?.metadata?.phases_completed ?? []), [result]);

  const stages: StageState[] = useMemo(
    () =>
      STAGES.map((id) => {
        let state: StageState["state"] = "idle";
        if (currentStage === id) state = playing ? "running" : "running";
        else if (completed.has(id)) state = "done";
        return { id, label: STAGE_LABELS[id], state };
      }),
    [completed, currentStage, playing],
  );

  return (
    <div className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-800 bg-slate-900/40 px-4">
      <div className="flex items-center gap-2">
        <button
          onClick={playing ? onPause : onPlay}
          disabled={!result}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-sky-400 ring-1 ring-slate-700 transition hover:bg-slate-700 hover:text-sky-300 disabled:opacity-50"
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
        <button
          onClick={onReplay}
          disabled={!result}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-400 ring-1 ring-slate-700 transition hover:bg-slate-700 hover:text-slate-200 disabled:opacity-50"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>

      <div className="h-6 w-px bg-slate-800" />

      <div className="flex flex-1 items-center gap-1">
        {stages.map((stage, index) => {
          const isLast = index === stages.length - 1;
          const colorClass =
            stage.state === "done"
              ? "border-sky-500/50 bg-sky-500/15 text-sky-300"
              : stage.state === "running"
                ? "border-amber-400/60 bg-amber-400/15 text-amber-300 node-breathe"
                : stage.state === "error"
                  ? "border-rose-500/50 bg-rose-500/15 text-rose-300"
                  : "border-slate-700 bg-slate-800/60 text-slate-500";

          return (
            <div key={stage.id} className="flex flex-1 items-center">
              <button
                onClick={() => onSeek(stage.id)}
                disabled={!result}
                className={[
                  "flex flex-1 items-center justify-center gap-2 rounded-lg border py-2 text-xs font-semibold transition",
                  colorClass,
                  result ? "hover:brightness-110" : "",
                ].join(" ")}
              >
                <span className="hidden sm:inline">{stage.label}</span>
                <span className="sm:hidden">{index + 1}</span>
              </button>
              {!isLast && (
                <div className="mx-1 h-px w-3 bg-slate-700" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
