import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileDown,
  ShieldCheck,
  UserRoundSearch,
  XCircle,
} from "lucide-react";
import type {
  BusinessTopology,
  DiagnosisEvent,
  DiagnosisResult,
  ReviewState,
  RootCauseCandidate,
} from "../lib/types";

function rootLabel(root?: string) {
  if (!root) return "未形成唯一根因";
  if (root.startsWith("link:")) return `${root.slice(5)} 光纤链路故障`;
  if (root.startsWith("dev:")) return `${root.slice(4)} 设备故障`;
  if (root.startsWith("port:")) return `${root.slice(5)} 端口故障`;
  return root;
}

interface ReviewProps {
  sessionId: string;
  topology: BusinessTopology;
  candidates: RootCauseCandidate[];
  review: ReviewState;
  result: DiagnosisResult;
  onReview: (
    decision: "confirmed" | "corrected" | "expert_review_requested",
    notes: string,
    rootCause?: string,
  ) => Promise<void>;
}

function ReviewPanel({ topology, candidates, review, result, onReview }: ReviewProps) {
  const [mode, setMode] = useState<"corrected" | "expert_review_requested" | null>(null);
  const [root, setRoot] = useState(candidates[1]?.root_cause ?? "");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const options = useMemo(
    () => [
      ...topology.links.map((link) => ({ value: `link:${link.link_id}`, label: `链路 · ${link.link_id}` })),
      ...topology.devices.map((device) => ({ value: `dev:${device.device_id}`, label: `设备 · ${device.device_id}` })),
      ...topology.ports.map((port) => ({ value: `port:${port.port_id}`, label: `端口 · ${port.port_id}` })),
    ],
    [topology],
  );

  if (review.status !== "unreviewed") {
    return (
      <div className="review-saved">
        <CheckCircle2 size={20} />
        <div>
          <strong>反馈已写入诊断案卷</strong>
          <span>
            {review.status === "confirmed" && "已人工确认系统根因"}
            {review.status === "corrected" && `已纠正为 ${rootLabel(review.ground_truth?.root_cause)}`}
            {review.status === "expert_review_requested" && "等待专家复核"}
          </span>
        </div>
      </div>
    );
  }

  async function submit(
    decision: "confirmed" | "corrected" | "expert_review_requested",
    selectedRoot?: string,
  ) {
    setSaving(true);
    try {
      await onReview(decision, notes, selectedRoot);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={`review-panel${result.status === "degraded" ? " is-required" : ""}`}>
      <div className="review-panel__heading">
        <ClipboardCheck size={18} />
        <div>
          <strong>{result.status === "degraded" ? "需要人工审核" : "人工结论审核"}</strong>
          <span>审核不会覆盖系统原始预测</span>
        </div>
      </div>
      <div className="review-actions">
        <button type="button" onClick={() => submit("confirmed")} disabled={saving || !("root_cause" in result.root_cause)}>
          <Check size={15} /> 确认根因
        </button>
        <button type="button" onClick={() => setMode("corrected")} disabled={saving}>
          <XCircle size={15} /> 标记结论错误
        </button>
        <button type="button" onClick={() => setMode("expert_review_requested")} disabled={saving}>
          <UserRoundSearch size={15} /> 请求专家复核
        </button>
      </div>
      {mode && (
        <div className="review-form">
          {mode === "corrected" && (
            <label>
              正确根因
              <select value={root} onChange={(event) => setRoot(event.target.value)}>
                <option value="">从业务拓扑选择</option>
                {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          )}
          <label>
            审核说明（可选）
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="补充现场证据或复核要求" />
          </label>
          <button
            type="button"
            className="button button--primary"
            disabled={saving || (mode === "corrected" && !root)}
            onClick={() => submit(mode, mode === "corrected" ? root : undefined)}
          >提交审核</button>
        </div>
      )}
    </section>
  );
}

interface Props {
  result: DiagnosisResult;
  events: DiagnosisEvent[];
  review: ReviewState;
  demoExpectedRoot?: string | null;
  onReview: ReviewProps["onReview"];
}

export function ResultPanel({ result, events, review, demoExpectedRoot, onReview }: Props) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const root = "root_cause" in result.root_cause ? result.root_cause.root_cause : undefined;
  const alarmCount = result.evidence_graph.nodes.filter((node) => node.type === "Alarm").length;
  const affectedDevices = new Set(
    result.evidence_graph.nodes
      .filter((node) => node.type === "Alarm")
      .map((node) => node.device_id)
      .filter(Boolean),
  ).size;
  const stageEvents = events.filter(
    (event): event is Extract<DiagnosisEvent, { type: "stage.completed" }> => event.type === "stage.completed",
  );
  const totalMs = stageEvents.reduce((sum, event) => sum + event.elapsed_ms, 0);
  const topology = result.input.topology ?? { source: "provided", confidence: 1, devices: [], ports: [], links: [] };
  const candidates = result.candidates ?? [];
  const expectedPass = !demoExpectedRoot || root === demoExpectedRoot;

  return (
    <aside className="result-panel">
      <section className={`conclusion-card ${result.status}`} data-testid="conclusion-card">
        <div className="conclusion-card__status">
          {result.status === "success" ? <ShieldCheck size={18} /> : <AlertTriangle size={18} />}
          {result.status === "success" ? "自动诊断完成" : "自动诊断未完整收敛"}
        </div>
        <p>最可能根因</p>
        <h2>{rootLabel(root)}</h2>
        <div className="confidence-row">
          <span>可信度</span>
          <div><i style={{ width: `${Math.round(result.confidence * 100)}%` }} /></div>
          <strong>{Math.round(result.confidence * 100)}%</strong>
        </div>
        <div className="conclusion-facts">
          <div><strong>{alarmCount}</strong><span>条告警</span></div>
          <div><strong>{affectedDevices}</strong><span>台异常设备</span></div>
          <div><strong>{(totalMs / 1000).toFixed(2)}s</strong><span>阶段耗时</span></div>
        </div>
        <p className="conclusion-explanation">
          {result.status === "success"
            ? `${alarmCount} 条并发告警由 1 个物理故障统一解释，传播方向与链路两端告警一致。`
            : `现有证据未能支持唯一根因：${result.degradation_reason ?? "可信度复核未通过"}。`}
        </p>
        <div className="suggestion">
          <strong>建议动作</strong>
          <span>{result.status === "success" ? `优先检查 ${rootLabel(root)} 的光功率与物理连通性。` : "保留现有证据，转人工或专家复核。"}</span>
        </div>
        {demoExpectedRoot && (
          <div className={`demo-check ${expectedPass ? "pass" : "fail"}`} data-testid="demo-expectation">
            {expectedPass ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
            Demo 独立预期：{expectedPass ? "根因匹配" : `期望 ${demoExpectedRoot}`}
          </div>
        )}
      </section>

      <section className="critic-card">
        <div className="panel-title"><ShieldCheck size={17} /><strong>可信度检查</strong><span>Critic</span></div>
        {(result.critic_checks ?? []).map((check) => (
          <div className="check-row" key={check.id}>
            <span className={check.passed ? "pass" : "fail"}>{check.passed ? <Check size={13} /> : <XCircle size={13} />}</span>
            <div><strong>{check.label}</strong><small>{check.reason}</small></div>
          </div>
        ))}
      </section>

      <button type="button" className="details-toggle" onClick={() => setDetailsOpen((open) => !open)}>
        <span>候选与事件详情</span><ChevronDown className={detailsOpen ? "is-open" : ""} size={16} />
      </button>
      {detailsOpen && (
        <section className="details-panel">
          <h3>Top {Math.min(candidates.length, 3)} 候选</h3>
          {candidates.slice(0, 3).map((candidate, index) => (
            <div className="candidate-row" key={`${candidate.root_cause}-${index}`}>
              <span>{index + 1}</span>
              <div><strong>{rootLabel(candidate.root_cause)}</strong><small>{candidate.evidence_chain?.[0] ?? "证据链见诊断案卷"}</small></div>
              <b>{Math.round(candidate.confidence * 100)}%</b>
            </div>
          ))}
          <h3>真实事件</h3>
          <div className="event-list">
            {events.map((event, index) => <code key={`${event.timestamp}-${index}`}>{event.timestamp.slice(11, 19)} · {event.type}</code>)}
          </div>
        </section>
      )}

      <ReviewPanel
        sessionId={result.session_id}
        topology={topology}
        candidates={candidates}
        review={review}
        result={result}
        onReview={onReview}
      />

      <button type="button" className="button button--report" onClick={() => window.print()}>
        <FileDown size={16} /> 导出诊断报告 / PDF
      </button>
    </aside>
  );
}
