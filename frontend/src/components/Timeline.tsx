import { CheckCircle2, Circle, Clock3 } from "lucide-react";
import type { SessionStatus } from "../lib/types";

const steps = [
  ["perceived", "感知"],
  ["diagnosed", "诊断"],
  ["diagnosis_validated", "校验"],
  ["planned", "规划"],
  ["solution_validated", "方案校验"],
  ["waiting_review", "人工审核"],
  ["closed", "闭环"],
] as const;

interface Props {
  status?: SessionStatus;
}

export function Timeline({ status = "init" }: Props) {
  const current = steps.findIndex(([id]) => id === status);
  const effective = status === "closed" ? steps.length - 1 : current;

  return (
    <section className="glass rounded-3xl p-5 shadow-soft">
      <h2 className="text-sm font-semibold text-slate-700">Workflow</h2>
      <div className="mt-5 space-y-3">
        {steps.map(([id, label], index) => {
          const done = effective >= index || status === "closed";
          const active = id === status;
          return (
            <div key={id} className="flex items-center gap-3">
              <div
                className={[
                  "flex h-9 w-9 items-center justify-center rounded-full",
                  done ? "bg-brand text-white" : "bg-slate-100 text-slate-400",
                ].join(" ")}
              >
                {done ? <CheckCircle2 className="h-5 w-5" /> : active ? <Clock3 className="h-5 w-5" /> : <Circle className="h-4 w-4" />}
              </div>
              <div>
                <p className="text-sm font-medium text-ink">{label}</p>
                <p className="text-xs text-slate-400">{id}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
