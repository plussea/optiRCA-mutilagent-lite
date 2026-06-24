import type { SessionState } from "../lib/types";

interface Props {
  state: SessionState | null;
}

export function ReportPanel({ state }: Props) {
  if (!state) {
    return (
      <section className="glass flex min-h-[280px] items-center justify-center rounded-3xl p-8 text-center shadow-soft">
        <div>
          <p className="text-lg font-semibold text-ink">等待输入</p>
          <p className="mt-2 text-sm text-slate-500">上传一份告警 CSV 后，这里会生成 Case Report。</p>
        </div>
      </section>
    );
  }

  const diagnosis = state.diagnosis ?? {};
  const plan = state.planning?.final_plan ?? {};
  const validation = state.solution_validation ?? {};

  return (
    <section className="glass rounded-3xl p-6 shadow-soft">
      <div className="flex items-center justify-between border-b border-slate-100 pb-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Case Report</p>
          <h2 className="mt-1 text-xl font-bold text-ink">{state.session_id.slice(0, 8)}</h2>
        </div>
        <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
          {state.status}
        </span>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card title="根因判断">
          <p className="text-base font-semibold text-ink">{diagnosis.root_cause ?? "暂无"}</p>
          <p className="mt-2 text-sm text-slate-500">
            置信度: {diagnosis.confidence ? `${Math.round(diagnosis.confidence * 100)}%` : "-"}
          </p>
          <ul className="mt-3 space-y-1 text-sm text-slate-500">
            {(diagnosis.evidence ?? []).map((item: string) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </Card>

        <Card title="修复方案">
          <p className="text-base font-semibold text-ink">{plan.title ?? "暂无"}</p>
          <ol className="mt-3 space-y-2 text-sm text-slate-500">
            {(plan.steps ?? []).map((step: string, index: number) => (
              <li key={step}>{index + 1}. {step}</li>
            ))}
          </ol>
        </Card>

        <Card title="风险校验">
          <p className="text-sm text-slate-500">方案有效: {validation.solution_valid ? "是" : "否"}</p>
          <p className="mt-2 text-sm text-slate-500">风险等级: {validation.risk_level ?? "-"}</p>
          <p className="mt-2 text-sm text-slate-500">{validation.notes ?? ""}</p>
          {state.closure?.summary && (
            <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-700">
              {state.closure.summary}
            </p>
          )}
        </Card>
      </div>
    </section>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </div>
  );
}
