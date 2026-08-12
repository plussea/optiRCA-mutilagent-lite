import { Check, Circle, LoaderCircle, RotateCcw } from "lucide-react";
import type { DiagnosisEvent, StageId } from "../lib/types";

const STAGES: Array<{ id: StageId; label: string; agent: string }> = [
  { id: "perception", label: "告警解析", agent: "Perception" },
  { id: "topology", label: "拓扑构建", agent: "Topology" },
  { id: "judge", label: "传播判断", agent: "Judge" },
  { id: "rank", label: "根因排序", agent: "Ranker" },
  { id: "critic", label: "可信度复核", agent: "Critic" },
  { id: "dossier", label: "案卷组装", agent: "Archivist" },
];

interface Props {
  events: DiagnosisEvent[];
  running: boolean;
  replaying: boolean;
  onReplay: () => void;
}

export function StageRail({ events, running, replaying, onReplay }: Props) {
  const completed = new Map(
    events
      .filter((event): event is Extract<DiagnosisEvent, { type: "stage.completed" }> => event.type === "stage.completed")
      .map((event) => [event.stage, event]),
  );
  const active = [...events]
    .reverse()
    .find((event): event is Extract<DiagnosisEvent, { type: "stage.started" }> =>
      event.type === "stage.started" && !completed.has(event.stage),
    );
  const totalMs = [...completed.values()].reduce((sum, event) => sum + event.elapsed_ms, 0);

  return (
    <section className="stage-rail" aria-label="真实诊断阶段">
      <div className="stage-rail__items">
        {STAGES.map((stage, index) => {
          const done = completed.get(stage.id);
          const isActive = active?.stage === stage.id;
          return (
            <div className={`stage-item${done ? " is-done" : ""}${isActive ? " is-active" : ""}`} key={stage.id}>
              <span className="stage-item__number">
                {done ? <Check size={13} /> : isActive ? <LoaderCircle className="spin" size={14} /> : <Circle size={11} />}
              </span>
              <span className="stage-item__text">
                <strong>{stage.label}</strong>
                <small>{done ? `${(done.elapsed_ms / 1000).toFixed(2)}s` : stage.agent}</small>
              </span>
              {index < STAGES.length - 1 && <i />}
            </div>
          );
        })}
      </div>
      {!running && completed.size > 0 && (
        <button type="button" className="stage-replay" onClick={onReplay} disabled={replaying}>
          <RotateCcw size={14} /> {replaying ? "回放中" : `回放诊断 · ${(totalMs / 1000).toFixed(2)}s`}
        </button>
      )}
    </section>
  );
}
