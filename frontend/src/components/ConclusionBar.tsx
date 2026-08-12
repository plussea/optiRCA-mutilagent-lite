import { AlertTriangle, CheckCircle2, Clock, UploadCloud, XCircle } from "lucide-react";
import type { DiagnosisResult } from "../lib/types";

interface Props {
  result: DiagnosisResult | null;
  busy: boolean;
  onUpload: (file: File) => void;
  onRunDemo: () => void;
  onOpenReview: () => void;
}

export function ConclusionBar({ result, busy, onUpload, onRunDemo, onOpenReview }: Props) {
  const isDegraded = result?.status === "degraded";
  const needsReview = result?.requires_human_review ?? false;
  const rootId =
    result?.root_cause && "root_cause" in result.root_cause
      ? result.root_cause.root_cause
      : null;

  return (
    <header
      data-testid="conclusion-bar"
      data-risk={needsReview ? "review" : isDegraded ? "degraded" : "normal"}
      className={[
        "flex h-16 shrink-0 items-center justify-between border-b px-5",
        "transition-colors duration-300",
        needsReview
          ? "border-amber-500/30 bg-amber-500/10"
          : isDegraded
            ? "border-rose-500/30 bg-rose-500/10"
            : "border-sky-500/20 bg-slate-900/60",
      ].join(" ")}
    >
      <div className="flex items-center gap-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800 text-sky-400 ring-1 ring-sky-500/20">
          {needsReview ? (
            <AlertTriangle className="h-5 w-5 text-amber-400" />
          ) : isDegraded ? (
            <XCircle className="h-5 w-5 text-rose-400" />
          ) : (
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          )}
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
            {result ? (needsReview ? "需要人工审核" : isDegraded ? "诊断降级" : "诊断完成") : "等待输入"}
          </p>
          <h1 className="text-sm font-semibold text-slate-100">
            {result ? rootId ?? "暂无根因" : "OptiRCA Lite 智能告警根因诊断"}
          </h1>
        </div>
        {result && (
          <div className="hidden items-center gap-3 md:flex">
            <div className="h-6 w-px bg-slate-700" />
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">置信度</span>
              <span className="font-mono font-semibold text-sky-300">
                {result.confidence ? `${Math.round(result.confidence * 100)}%` : "-"}
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">案卷</span>
              <span className="font-mono text-slate-300">{result.dossier_id.slice(0, 12)}…</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <Clock className="h-3 w-3 text-slate-500" />
              <span className="font-mono text-slate-300">
                {result.metadata?.diagnosed_at
                  ? new Date(result.metadata.diagnosed_at).toLocaleTimeString("zh-CN")
                  : "--:--:--"}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {result && needsReview && (
          <button
            onClick={onOpenReview}
            className="rounded-lg bg-amber-500 px-4 py-2 text-xs font-bold text-slate-900 shadow-lg shadow-amber-500/20 transition hover:bg-amber-400"
          >
            立即审核
          </button>
        )}
        <button
          disabled={busy}
          onClick={onRunDemo}
          className="rounded-lg border border-sky-500/30 bg-slate-800 px-4 py-2 text-xs font-semibold text-sky-300 transition hover:bg-sky-500/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "诊断中…" : "运行 Demo"}
        </button>
        <label className="group relative flex cursor-pointer items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60">
          <UploadCloud className="h-4 w-4" />
          {busy ? "上传中…" : "上传 CSV"}
          <input
            type="file"
            accept=".csv"
            disabled={busy}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(file);
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>
    </header>
  );
}
