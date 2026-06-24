import { UploadCloud } from "lucide-react";

interface Props {
  busy: boolean;
  onUpload: (file: File) => void;
  onRunDemo: () => void;
}

export function UploadCard({ busy, onUpload, onRunDemo }: Props) {
  return (
    <section className="glass relative overflow-hidden rounded-[2rem] p-6 shadow-soft">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyanline/70 to-transparent" />
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyanline">OptiRCA Lite</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-ink">Agent Runtime Command Center</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
            以可审计的 Workflow 视图追踪感知、诊断、规划、人工审核与经验回收。节点状态、连线流向和运行证据会随执行实时更新。
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            disabled={busy}
            onClick={onRunDemo}
            className="rounded-2xl border border-cyanline/30 bg-cyanline/10 px-5 py-4 text-sm font-semibold text-cyan-100 transition hover:-translate-y-0.5 hover:border-cyanline/70 disabled:cursor-not-allowed disabled:opacity-60"
          >
            运行 true_example.csv
          </button>
          <label className="group flex cursor-pointer items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5 hover:bg-cyan-100">
            <UploadCloud className="h-5 w-5" />
            {busy ? "提交中..." : "上传 CSV"}
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
      </div>
    </section>
  );
}
