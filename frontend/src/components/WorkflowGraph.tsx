import {
  Activity,
  BrainCircuit,
  CheckCircle2,
  Circle,
  Clock3,
  Database,
  GitBranch,
  ShieldCheck,
  UserCheck,
  XCircle,
} from "lucide-react";
import type { SessionState, WorkflowEvent } from "../lib/types";

type NodeKind = "Agent" | "Guardrail" | "Human" | "Memory";
type NodeRuntimeState = "idle" | "running" | "done" | "waiting" | "error";

export const workflowNodes = [
  {
    id: "perception",
    label: "感知",
    kind: "Agent" as NodeKind,
    status: "perceived",
    role: "CSV 解析 / 告警归一",
    x: 4,
    y: 16,
    hasSubgraph: true,
  },
  {
    id: "diagnosis",
    label: "诊断",
    kind: "Agent" as NodeKind,
    status: "diagnosed",
    role: "RAG + 拓扑 + LLM RCA",
    x: 29,
    y: 16,
    hasSubgraph: true,
  },
  {
    id: "validation",
    label: "诊断校验",
    kind: "Guardrail" as NodeKind,
    status: "diagnosis_validated",
    role: "置信度 / 证据完整性",
    x: 54,
    y: 16,
  },
  {
    id: "planning",
    label: "方案规划",
    kind: "Agent" as NodeKind,
    status: "planned",
    role: "SOP 检索 / 修复计划",
    x: 78,
    y: 16,
  },
  {
    id: "solution_validation",
    label: "方案校验",
    kind: "Guardrail" as NodeKind,
    status: "solution_validated",
    role: "风险 / 回滚 / 资源",
    x: 78,
    y: 66,
  },
  {
    id: "human_review",
    label: "人工审核",
    kind: "Human" as NodeKind,
    status: "waiting_review",
    role: "批准 / 驳回 / 升级",
    x: 54,
    y: 66,
  },
  {
    id: "closure",
    label: "经验回收",
    kind: "Memory" as NodeKind,
    status: "closed",
    role: "案例沉淀 / 知识库更新",
    x: 29,
    y: 66,
  },
] as const;

const edges = [
  ["perception", "diagnosis", "reasoning"],
  ["diagnosis", "validation", "reasoning"],
  ["validation", "planning", "condition"],
  ["planning", "solution_validation", "reasoning"],
  ["solution_validation", "human_review", "handoff"],
  ["human_review", "closure", "memory"],
] as const;

interface Props {
  state: SessionState | null;
  events: WorkflowEvent[];
  selectedNode: string;
  onSelectNode: (nodeId: string) => void;
}

export function WorkflowGraph({ state, events, selectedNode, onSelectNode }: Props) {
  const eventSet = new Set(events.map((event) => event.phase));

  function nodeState(nodeId: string, doneStatus: string): NodeRuntimeState {
    if (state?.status === "error") return "error";
    if (eventSet.has(`${nodeId}.start`) && !eventSet.has(`${nodeId}.end`)) return "running";
    if (nodeId === "human_review" && state?.pending_human) return "waiting";
    if (eventSet.has(`${nodeId}.end`)) return "done";
    if (state?.status === doneStatus) return nodeId === "human_review" ? "waiting" : "done";
    return "idle";
  }

  function edgeState(from: string, to: string): "idle" | "active" | "done" {
    if (eventSet.has(`${to}.start`) && !eventSet.has(`${to}.end`)) return "active";
    if (eventSet.has(`${from}.end`) && !eventSet.has(`${to}.end`)) return "active";
    if (eventSet.has(`${to}.end`)) return "done";
    return "idle";
  }

  const completed = workflowNodes.filter((node) => nodeState(node.id, node.status) === "done").length;
  const active = workflowNodes.find((node) => ["running", "waiting"].includes(nodeState(node.id, node.status)));

  return (
    <section className="glass relative min-h-[620px] overflow-hidden rounded-[2rem] p-6 shadow-soft">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_35%_12%,rgba(56,213,255,0.16),transparent_30rem)]" />
      <div className="pointer-events-none absolute inset-x-10 top-[47%] h-px bg-gradient-to-r from-transparent via-slate-600/40 to-transparent" />
      <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.26em] text-cyanline">Runtime Topology</p>
          <h2 className="mt-2 text-xl font-bold text-ink">可回溯 Agent Workflow</h2>
          <p className="mt-2 max-w-xl text-sm text-slate-400">
            控制流、审核分支和经验回收路径在同一张图内呈现；选择节点可查看子图、工具调用和输出。
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <Metric label="状态" value={state?.status ?? "idle"} />
          <Metric label="完成节点" value={`${completed}/${workflowNodes.length}`} />
          <Metric label="当前节点" value={active?.label ?? "-"} />
        </div>
      </div>

      <div className="absolute inset-x-8 top-40 h-[430px]">
        <div className="absolute left-0 top-0 rounded-full border border-cyanline/20 bg-cyanline/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-cyan-100">
          Reasoning Lane
        </div>
        <div className="absolute left-0 top-[54%] rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-100">
          Review & Memory Lane
        </div>
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="edge-reasoning" x1="0%" x2="100%">
              <stop offset="0%" stopColor="#38d5ff" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#7c8cff" stopOpacity="0.95" />
            </linearGradient>
            <linearGradient id="edge-memory" x1="0%" x2="100%">
              <stop offset="0%" stopColor="#34d399" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#34d399" stopOpacity="0.95" />
            </linearGradient>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="3" markerHeight="3" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#7dd3fc" opacity="0.75" />
            </marker>
          </defs>
          {edges.map(([from, to, kind]) => {
            const a = workflowNodes.find((node) => node.id === from)!;
            const b = workflowNodes.find((node) => node.id === to)!;
            const status = edgeState(from, to);
            const stroke =
              status === "idle"
                ? "rgba(100,116,139,0.32)"
                : kind === "memory"
                  ? "url(#edge-memory)"
                  : kind === "condition"
                    ? "#fbbf24"
                    : "url(#edge-reasoning)";
            const sameLane = Math.abs(a.y - b.y) < 8;
            const path = sameLane
              ? `M ${a.x + 9} ${a.y + 7} C ${a.x + 17} ${a.y + 7}, ${b.x - 8} ${b.y + 7}, ${b.x + 1} ${b.y + 7}`
              : `M ${a.x + 9} ${a.y + 8} C ${a.x + 17} ${a.y + 32}, ${b.x + 17} ${b.y - 18}, ${b.x + 9} ${b.y}`;
            return (
              <path
                key={`${from}-${to}`}
                d={path}
                fill="none"
                stroke={stroke}
                strokeWidth={status === "active" ? 0.9 : 0.55}
                markerEnd={status === "idle" ? undefined : "url(#arrow)"}
                className={status === "active" ? "edge-flow" : ""}
                opacity={status === "idle" ? 0.45 : 1}
              />
            );
          })}
        </svg>

        {workflowNodes.map((node) => {
          const runtimeState = nodeState(node.id, node.status);
          const selected = selectedNode === node.id;
          return (
            <button
              key={node.id}
              onClick={() => onSelectNode(node.id)}
              className={[
                "absolute w-[172px] rounded-[1.2rem] border p-4 text-left transition-all duration-300",
                "bg-slate-950/70 backdrop-blur-xl",
                selected ? "scale-[1.035] border-cyanline/80 shadow-glow" : "border-slate-600/40",
                runtimeState === "running" ? "node-breathe border-cyanline/80" : "",
                runtimeState === "waiting" ? "border-amber-300/70 shadow-[0_0_30px_rgba(251,191,36,0.15)]" : "",
                runtimeState === "done" ? "border-emerald-300/45" : "",
              ].join(" ")}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <KindIcon kind={node.kind} />
                  <span className="rounded-full border border-slate-600/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                    {node.kind}
                  </span>
                </div>
                <StatusIcon status={runtimeState} />
              </div>
              <p className="mt-3 text-sm font-bold text-ink">{node.label}</p>
              <p className="mt-1 min-h-7 text-[11px] leading-4 text-slate-400">{node.role}</p>
              <div className="mt-3 flex items-center justify-between">
                <span className={statusChip(runtimeState)}>{runtimeState}</span>
                {"hasSubgraph" in node && node.hasSubgraph && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-cyanline">
                    <GitBranch className="h-3.5 w-3.5" />
                    子图
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-700/60 bg-slate-950/50 px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-1 max-w-[130px] truncate text-xs font-bold text-ink">{value}</p>
    </div>
  );
}

function KindIcon({ kind }: { kind: NodeKind }) {
  const className = "h-4 w-4";
  if (kind === "Agent") return <BrainCircuit className={`${className} text-cyanline`} />;
  if (kind === "Guardrail") return <ShieldCheck className={`${className} text-violet-300`} />;
  if (kind === "Human") return <UserCheck className={`${className} text-amber-300`} />;
  return <Database className={`${className} text-emerald-300`} />;
}

function StatusIcon({ status }: { status: NodeRuntimeState }) {
  if (status === "done") return <CheckCircle2 className="h-5 w-5 text-emerald-300" />;
  if (status === "running") return <Clock3 className="h-5 w-5 animate-pulse text-cyanline" />;
  if (status === "waiting") return <Activity className="h-5 w-5 animate-pulse text-amber-300" />;
  if (status === "error") return <XCircle className="h-5 w-5 text-rose-400" />;
  return <Circle className="h-5 w-5 text-slate-500" />;
}

function statusChip(status: NodeRuntimeState) {
  const base = "rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em]";
  if (status === "done") return `${base} bg-emerald-400/10 text-emerald-200`;
  if (status === "running") return `${base} bg-cyan-400/10 text-cyan-100`;
  if (status === "waiting") return `${base} bg-amber-400/10 text-amber-100`;
  if (status === "error") return `${base} bg-rose-400/10 text-rose-100`;
  return `${base} bg-slate-700/40 text-slate-400`;
}
