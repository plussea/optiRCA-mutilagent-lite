import {
  AlertTriangle,
  Cable,
  CheckCircle2,
  ChevronLeft,
  HardDrive,
  Network,
  XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { DiagnosisResult, EvidenceEdge, EvidenceNode } from "../lib/types";
import { submitDecision } from "../lib/api";

interface Props {
  result: DiagnosisResult | null;
  selectedId?: string | null;
  onReviewOpen?: () => void;
}

function findNode(graph: DiagnosisResult["evidence_graph"], id: string): EvidenceNode | undefined {
  return graph.nodes.find((n) => n.id === id);
}

function findEdges(graph: DiagnosisResult["evidence_graph"], id: string): EvidenceEdge[] {
  return graph.edges.filter((e) => e.source === id || e.target === id);
}

function formatValue(value: unknown): string {
  if (value === undefined || value === null) return "-";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return value.toString();
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function ObjectDetail({ node, edges, onBack }: { node: EvidenceNode; edges: EvidenceEdge[]; onBack: () => void }) {
  const label =
    node.device_id ?? node.port_id ?? node.link_id ?? node.alarm_id ?? node.service_id ?? node.id;

  const fields = useMemo(() => {
    const skip = new Set(["id", "type"]);
    return Object.entries(node).filter(([key]) => !skip.has(key));
  }, [node]);

  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-xs font-semibold text-sky-400 transition hover:text-sky-300"
      >
        <ChevronLeft className="h-4 w-4" />
        返回摘要
      </button>

      <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
        <div className="flex items-center gap-3">
          {node.type === "Device" && <HardDrive className="h-6 w-6 text-sky-400" />}
          {node.type === "Port" && <Network className="h-6 w-6 text-emerald-400" />}
          {node.type === "Link" && <Cable className="h-6 w-6 text-sky-400" />}
          {node.type === "Alarm" && <AlertTriangle className="h-6 w-6 text-rose-400" />}
          {node.type === "Service" && <Network className="h-6 w-6 text-slate-400" />}
          <div>
            <p className="text-sm font-semibold text-slate-100">{label}</p>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">{node.type}</p>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">属性</p>
        <dl className="mt-3 space-y-2">
          {fields.map(([key, value]) => (
            <div key={key} className="flex justify-between text-xs">
              <dt className="text-slate-500">{key}</dt>
              <dd className="max-w-[180px] truncate font-mono text-slate-300">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      </section>

      {edges.length > 0 && (
        <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">关联</p>
          <ul className="mt-3 space-y-2">
            {edges.map((edge, idx) => (
              <li key={idx} className="text-xs text-slate-300">
                <span className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-sky-300">{edge.type}</span>
                {" "}
                <span className="text-slate-500">{edge.source} → {edge.target}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function RightDrawer({ result, selectedId, onReviewOpen }: Props) {
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!result) {
    return (
      <aside className="flex w-[360px] shrink-0 flex-col border-l border-slate-800 bg-slate-900/60 p-5">
        <p className="text-sm text-slate-500">诊断结果将在这里显示详细证据与审核入口。</p>
      </aside>
    );
  }

  const isDegraded = result.status === "degraded";
  const needsReview = result.requires_human_review;
  const rootId =
    result.root_cause && "root_cause" in result.root_cause ? result.root_cause.root_cause : null;

  async function handle(decision: "approved" | "rejected" | "escalated") {
    if (!result?.session_id) return;
    setBusy(true);
    try {
      await submitDecision(result.session_id, decision, notes);
      setSubmitted(true);
    } catch (err) {
      // swallow for UI simplicity
    } finally {
      setBusy(false);
    }
  }

  const selectedNode = selectedId ? findNode(result.evidence_graph, selectedId) : undefined;

  return (
    <aside className="flex w-[360px] shrink-0 flex-col overflow-y-auto border-l border-slate-800 bg-slate-900/70 p-5">
      {selectedNode ? (
        <ObjectDetail
          node={selectedNode}
          edges={findEdges(result.evidence_graph, selectedNode.id)}
          onBack={() => onReviewOpen?.()}
        />
      ) : (
        <div className="space-y-5">
          <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">诊断结论</p>
            <div className="mt-3 flex items-center gap-3">
              {isDegraded ? (
                <XCircle className="h-6 w-6 text-rose-400" />
              ) : needsReview ? (
                <AlertTriangle className="h-6 w-6 text-amber-400" />
              ) : (
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              )}
              <div>
                <p className="text-lg font-semibold text-slate-100">{rootId ?? "暂无根因"}</p>
                <p className="text-xs text-slate-400">
                  置信度{" "}
                  <span className="font-mono font-semibold text-sky-300">
                    {result.confidence ? `${Math.round(result.confidence * 100)}%` : "-"}
                  </span>
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">处置建议</p>
            <p className="mt-3 text-sm leading-6 text-slate-300">{result.suggestion}</p>
          </section>

          <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">证据链</p>
            <ul className="mt-3 space-y-2">
              {(result.evidence_chain ?? []).map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                  {item}
                </li>
              ))}
            </ul>
          </section>

          {result.critic_verdict && (
            <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Critic 复核</p>
              <p className="mt-3 text-sm text-slate-300">{result.critic_verdict}</p>
            </section>
          )}

          {result.degradation_reason && (
            <section className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-400">降级原因</p>
              <p className="mt-3 text-sm text-rose-200">{result.degradation_reason}</p>
            </section>
          )}

          <section className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">元数据</p>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Session</span>
                <span className="font-mono text-slate-300">{result.session_id.slice(0, 16)}…</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">完成阶段</span>
                <span className="text-right text-slate-300">
                  {(result.metadata?.phases_completed ?? []).join(", ") || "-"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">回退轮数</span>
                <span className="font-mono text-slate-300">{result.metadata?.fallback_rounds ?? 0}</span>
              </div>
            </div>
          </section>

          {needsReview && !submitted && (
            <section className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                <p className="text-sm font-bold text-amber-200">需要人工审核</p>
              </div>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="填写审核意见…"
                disabled={busy}
                className="mt-3 h-24 w-full resize-none rounded-lg border border-amber-500/20 bg-slate-900/50 p-3 text-sm text-slate-200 outline-none placeholder:text-slate-500 focus:border-amber-500/50"
              />
              <div className="mt-3 grid grid-cols-3 gap-2">
                <button
                  disabled={busy}
                  onClick={() => handle("approved")}
                  className="rounded-lg bg-emerald-600 px-2 py-2 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-60"
                >
                  批准
                </button>
                <button
                  disabled={busy}
                  onClick={() => handle("rejected")}
                  className="rounded-lg bg-rose-600 px-2 py-2 text-xs font-semibold text-white transition hover:bg-rose-500 disabled:opacity-60"
                >
                  驳回
                </button>
                <button
                  disabled={busy}
                  onClick={() => handle("escalated")}
                  className="rounded-lg bg-slate-600 px-2 py-2 text-xs font-semibold text-white transition hover:bg-slate-500 disabled:opacity-60"
                >
                  升级
                </button>
              </div>
            </section>
          )}

          {submitted && (
            <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                <p className="text-sm font-bold text-emerald-200">审核意见已提交</p>
              </div>
            </section>
          )}
        </div>
      )}
    </aside>
  );
}
