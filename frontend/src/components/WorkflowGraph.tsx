import { Activity, CheckCircle2, Circle, Clock3, GitBranch, XCircle } from "lucide-react";
import type { SessionState, WorkflowEvent } from "../lib/types";

export const workflowNodes = [
  { id: "perception", label: "感知", status: "perceived", x: 7, y: 24, hasSubgraph: true },
  { id: "diagnosis", label: "诊断", status: "diagnosed", x: 25, y: 24, hasSubgraph: true },
  { id: "validation", label: "诊断校验", status: "diagnosis_validated", x: 43, y: 24 },
  { id: "planning", label: "方案规划", status: "planned", x: 61, y: 24 },
  { id: "solution_validation", label: "方案校验", status: "solution_validated", x: 79, y: 24 },
  { id: "human_review", label: "人工审核", status: "waiting_review", x: 43, y: 70 },
] as const;

const edges = [
  ["perception", "diagnosis"],
  ["diagnosis", "validation"],
  ["validation", "planning"],
  ["planning", "solution_validation"],
  ["solution_validation", "human_review"],
] as const;

interface Props {
  state: SessionState | null;
  events: WorkflowEvent[];
  selectedNode: string;
  onSelectNode: (nodeId: string) => void;
}

export function WorkflowGraph({ state, events, selectedNode, onSelectNode }: Props) {
  const eventSet = new Set(events.map((event) => event.phase));

  function nodeState(nodeId: string, doneStatus: string) {
    if (state?.status === "error") return "error";
    if (eventSet.has(`${nodeId}.start`) && !eventSet.has(`${nodeId}.end`)) return "running";
    if (eventSet.has(`${nodeId}.end`)) return "done";
    if (state?.status === doneStatus) return "done";
    return "idle";
  }

  function edgeState(from: string, to: string) {
    if (eventSet.has(`${to}.start`)) return "active";
    if (eventSet.has(`${from}.end`)) return "ready";
    return "idle";
  }

  return (
    <section className="glass relative min-h-[460px] overflow-hidden rounded-3xl p-6 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Runtime Workflow</p>
          <h2 className="mt-1 text-xl font-bold text-ink">可回溯执行视图</h2>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white">
          <Activity className="h-3.5 w-3.5" />
          {state?.status ?? "idle"}
        </div>
      </div>

      <div className="absolute inset-x-6 top-24 h-[320px]">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          {edges.map(([from, to]) => {
            const a = workflowNodes.find((node) => node.id === from)!;
            const b = workflowNodes.find((node) => node.id === to)!;
            const status = edgeState(from, to);
            const color =
              status === "active" ? "#5b5ce2" : status === "ready" ? "#94a3b8" : "#e2e8f0";
            return (
              <line
                key={`${from}-${to}`}
                x1={a.x + 6}
                y1={a.y + 5}
                x2={b.x + 6}
                y2={b.y + 5}
                stroke={color}
                strokeWidth={status === "active" ? 0.9 : 0.55}
                strokeDasharray={status === "idle" ? "2 2" : "0"}
                className={status === "active" ? "animate-pulse" : ""}
              />
            );
          })}
        </svg>

        {workflowNodes.map((node) => {
          const status = nodeState(node.id, node.status);
          const selected = selectedNode === node.id;
          return (
            <button
              key={node.id}
              onClick={() => onSelectNode(node.id)}
              className={[
                "absolute w-[150px] rounded-2xl border p-4 text-left transition-all",
                selected ? "scale-[1.03] border-brand bg-white shadow-soft" : "border-white/80 bg-white/75",
                status === "running" ? "ring-4 ring-brand/10" : "",
              ].join(" ")}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <div className="flex items-center justify-between">
                <StatusIcon status={status} />
                {"hasSubgraph" in node && node.hasSubgraph && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-brand">
                    <GitBranch className="h-3 w-3" />
                    子图
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm font-bold text-ink">{node.label}</p>
              <p className="mt-1 text-xs text-slate-400">{node.id}</p>
              <p className="mt-3 text-[11px] font-medium uppercase text-slate-500">{status}</p>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "done") return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
  if (status === "running") return <Clock3 className="h-5 w-5 animate-pulse text-brand" />;
  if (status === "error") return <XCircle className="h-5 w-5 text-rose-500" />;
  return <Circle className="h-5 w-5 text-slate-300" />;
}
