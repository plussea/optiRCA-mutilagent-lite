import { UploadCloud } from "lucide-react";

interface Props {
  busy: boolean;
  onUpload: (file: File) => void;
}

export function UploadCard({ busy, onUpload }: Props) {
  return (
    <section className="glass rounded-3xl p-6 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-brand">OptiRCA Lite</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-ink">轻量根因分析工作台</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
            上传 CSV 告警，系统会通过编译时 Workflow 推进流程，并在每个阶段由 State-Aware Runtime 选择合适 Skill。
          </p>
        </div>
        <label className="group flex cursor-pointer items-center gap-3 rounded-2xl bg-ink px-5 py-4 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-black">
          <UploadCloud className="h-5 w-5" />
          {busy ? "分析中..." : "上传 CSV"}
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
    </section>
  );
}
