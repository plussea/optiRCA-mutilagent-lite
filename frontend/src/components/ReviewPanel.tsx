import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { SessionState } from "../lib/types";

interface Props {
  state: SessionState | null;
  onDecision: (decision: "approved" | "rejected" | "escalated", notes: string) => void;
}

export function ReviewPanel({ state, onDecision }: Props) {
  const [notes, setNotes] = useState("");
  if (!state?.pending_human) return null;

  return (
    <section className="rounded-3xl border border-amber-200 bg-amber-50/90 p-5 shadow-soft">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-amber-100 p-3 text-amber-700">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-amber-900">需要人工审核</h2>
          <p className="text-xs text-amber-700">批准后写入本地知识库，驳回或升级会结束本次流程。</p>
        </div>
      </div>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        placeholder="填写审核意见..."
        className="mt-4 h-24 w-full resize-none rounded-2xl border border-amber-200 bg-white/80 p-3 text-sm outline-none focus:ring-2 focus:ring-amber-300"
      />
      <div className="mt-4 grid grid-cols-3 gap-2">
        <button className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white" onClick={() => onDecision("approved", notes)}>
          批准
        </button>
        <button className="rounded-xl bg-rose-600 px-3 py-2 text-sm font-semibold text-white" onClick={() => onDecision("rejected", notes)}>
          驳回
        </button>
        <button className="rounded-xl bg-slate-800 px-3 py-2 text-sm font-semibold text-white" onClick={() => onDecision("escalated", notes)}>
          升级
        </button>
      </div>
    </section>
  );
}
