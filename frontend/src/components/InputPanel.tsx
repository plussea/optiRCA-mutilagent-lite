import { useRef } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileJson2,
  FileSpreadsheet,
  FlaskConical,
  LoaderCircle,
  Play,
  UploadCloud,
} from "lucide-react";
import type { PreflightResult, WorkbenchStatus } from "../lib/types";

interface Props {
  alarmFile: File | null;
  topologyFile: File | null;
  status: WorkbenchStatus;
  preflight: PreflightResult | null;
  onAlarmFile: (file: File | null) => void;
  onTopologyFile: (file: File | null) => void;
  onLoadDemo: () => void;
  onStart: () => void;
}

function UploadBox({
  kind,
  title,
  hint,
  file,
  required,
  accept,
  onFile,
}: {
  kind: "csv" | "json";
  title: string;
  hint: string;
  file: File | null;
  required?: boolean;
  accept: string;
  onFile: (file: File | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const Icon = kind === "csv" ? FileSpreadsheet : FileJson2;
  return (
    <button className={`upload-box${file ? " has-file" : ""}`} type="button" onClick={() => input.current?.click()}>
      <input
        ref={input}
        hidden
        type="file"
        accept={accept}
        onChange={(event) => onFile(event.currentTarget.files?.[0] ?? null)}
      />
      <span className="upload-box__icon"><Icon size={22} /></span>
      <span className="upload-box__body">
        <span className="upload-box__title">
          {title} {required ? <em>必需</em> : <small>可选</small>}
        </span>
        <span className="upload-box__file">{file ? file.name : hint}</span>
      </span>
      <span className="upload-box__action">{file ? "更换" : <><UploadCloud size={14} /> 选择文件</>}</span>
    </button>
  );
}

function PreflightSummary({ preflight }: { preflight: PreflightResult }) {
  const summary = preflight.sample_summary;
  const sourceLabel = preflight.topology.source === "provided" ? "权威拓扑" : "系统推断拓扑";
  return (
    <section className={`preflight-card ${preflight.status}`} aria-live="polite">
      <div className="preflight-card__header">
        {preflight.status === "ready" ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
        <div>
          <strong>{preflight.status === "ready" ? "输入已就绪" : "输入尚不能诊断"}</strong>
          <span>
            {preflight.status === "ready"
              ? `${sourceLabel} · 可信度 ${Math.round(preflight.topology.confidence * 100)}%`
              : "请补充能消除拓扑歧义的信息"}
          </span>
        </div>
      </div>

      {preflight.status === "ready" ? (
        <div className="summary-grid">
          <div><span>告警总数</span><strong>{summary.alarm_count}</strong></div>
          <div><span>涉及设备</span><strong>{summary.device_count}</strong></div>
          <div><span>拓扑设备</span><strong>{preflight.topology.devices.length}</strong></div>
          <div><span>物理链路</span><strong>{preflight.topology.links.length}</strong></div>
          <div className="summary-grid__wide">
            <span>时间窗口</span>
            <strong>{summary.time_window.start || "—"} 至 {summary.time_window.end || "—"}</strong>
          </div>
          <div className="summary-grid__wide">
            <span>告警类型</span>
            <strong>{summary.alarm_types.join(" · ") || "—"}</strong>
          </div>
        </div>
      ) : (
        <div className="issue-list">
          {preflight.issues.map((issue) => (
            <div key={issue.code}>
              <code>{issue.code}</code>
              <p>{issue.message}</p>
              {issue.required_fields && <small>需补充：{issue.required_fields.join("、")}</small>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function InputPanel({
  alarmFile,
  topologyFile,
  status,
  preflight,
  onAlarmFile,
  onTopologyFile,
  onLoadDemo,
  onStart,
}: Props) {
  const checking = status === "preflighting";
  return (
    <main className="input-page">
      <section className="input-hero">
        <span className="eyebrow">SINGLE-SAMPLE DIAGNOSIS</span>
        <h1>从并发告警中，定位一个可执行的物理根因</h1>
        <p>上传告警 CSV。复杂拓扑可附带 JSON；简单场景由系统推断，存在歧义时会在诊断前阻止运行。</p>
      </section>

      <section className="input-card">
        <div className="section-heading">
          <div><span>01</span><h2>准备诊断样本</h2></div>
          <p>文件只用于当前诊断，不会在浏览器本地保存内容</p>
        </div>
        <div className="upload-grid">
          <UploadBox
            kind="csv"
            title="告警 CSV"
            hint="选择包含设备、告警类型、时间等字段的文件"
            required
            accept=".csv,text/csv"
            file={alarmFile}
            onFile={onAlarmFile}
          />
          <UploadBox
            kind="json"
            title="业务拓扑 JSON"
            hint="复杂拓扑建议上传；未上传时将尝试推断"
            accept=".json,application/json"
            file={topologyFile}
            onFile={onTopologyFile}
          />
        </div>

        <div className="input-actions">
          <button type="button" className="button button--secondary" onClick={onLoadDemo} disabled={checking}>
            <FlaskConical size={16} /> 加载真实 Demo
          </button>
          <span className="input-actions__status">
            {checking && <><LoaderCircle className="spin" size={16} /> 正在解析告警并检查拓扑…</>}
            {!checking && !alarmFile && "请先选择告警 CSV"}
            {!checking && alarmFile && !preflight && "等待预检"}
          </span>
        </div>

        {preflight && <PreflightSummary preflight={preflight} />}

        <div className="start-row">
          <div>
            <strong>开始后将依次执行 6 个真实诊断阶段</strong>
            <span>告警解析 · 拓扑构建 · 传播判断 · 根因排序 · 可信度复核 · 案卷组装</span>
          </div>
          <button
            type="button"
            className="button button--primary button--large"
            onClick={onStart}
            disabled={preflight?.status !== "ready" || checking}
          >
            <Play size={17} fill="currentColor" /> 开始诊断
          </button>
        </div>
      </section>
    </main>
  );
}
