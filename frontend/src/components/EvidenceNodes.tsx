import { AlertTriangle, Cable, HardDrive, Network } from "lucide-react";
import type { EvidenceNode } from "../lib/types";

interface DeviceNodeProps {
  data: EvidenceNode & { isRoot?: boolean };
  selected?: boolean;
}

export function DeviceNode({ data, selected }: DeviceNodeProps) {
  const label = data.device_id ?? data.id;
  return (
    <div
      data-testid={`node-${data.id}`}
      className={[
        "relative flex w-36 flex-col rounded-lg border bg-gradient-to-b from-slate-700 to-slate-800 p-2 shadow-lg",
        data.isRoot
          ? "border-rose-500/70 shadow-rose-500/30 pulse-glow"
          : selected
            ? "border-sky-400 shadow-sky-500/30"
            : "border-slate-600 shadow-black/40",
      ].join(" ")}
    >
      <div className="absolute -top-1.5 left-1/2 h-1.5 w-8 -translate-x-1/2 rounded-full bg-slate-600" />
      <div className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-900/60 text-sky-400 ring-1 ring-slate-600">
          <HardDrive className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-bold text-slate-100">{label}</p>
          <p className="text-[10px] uppercase tracking-wide text-slate-400">{data.type}</p>
        </div>
      </div>
      <div className="mt-2 flex justify-between px-1">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
        <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
      </div>
    </div>
  );
}

export function PortNode({ data, selected }: DeviceNodeProps) {
  const label = data.port_id ?? data.id;
  const directionColor = data.direction === "out" ? "bg-sky-400" : "bg-emerald-400";
  return (
    <div
      data-testid={`node-${data.id}`}
      className={[
        "flex w-24 items-center gap-2 rounded-md border bg-slate-800 p-1.5 shadow-md",
        selected ? "border-sky-400 shadow-sky-500/30" : "border-slate-600 shadow-black/40",
      ].join(" ")}
    >
      <div className={["h-3 w-3 rounded-sm", directionColor].join(" ")} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[10px] font-semibold text-slate-200">{label}</p>
      </div>
    </div>
  );
}

export function LinkNode({ data, selected }: DeviceNodeProps) {
  const label = data.link_id ?? data.id;
  return (
    <div
      data-testid={`node-${data.id}`}
      className={[
        "flex w-28 items-center gap-2 rounded-full border bg-slate-800 px-3 py-1.5 shadow-md",
        data.isRoot
          ? "border-rose-500/70 shadow-rose-500/30 pulse-glow"
          : selected
            ? "border-sky-400 shadow-sky-500/30"
            : "border-slate-600 shadow-black/40",
      ].join(" ")}
    >
      <Cable className="h-3.5 w-3.5 text-sky-400" />
      <p className="truncate text-[10px] font-semibold text-slate-200">{label}</p>
    </div>
  );
}

function severityColor(severity?: string) {
  const s = (severity ?? "").toLowerCase();
  if (s === "critical") return "bg-rose-500 shadow-rose-500/50";
  if (s === "major") return "bg-amber-500 shadow-amber-500/50";
  if (s === "minor") return "bg-blue-400 shadow-blue-400/50";
  return "bg-slate-400 shadow-slate-400/50";
}

export function AlarmDot({ data, selected }: DeviceNodeProps) {
  const label = data.alarm_id ?? data.id;
  return (
    <div
      data-testid={`node-${data.id}`}
      className={[
        "group flex items-center gap-2 rounded-full border bg-slate-900/90 px-2 py-1 shadow-lg",
        selected ? "border-sky-400" : "border-slate-700",
      ].join(" ")}
    >
      <span
        className={[
          "h-3 w-3 shrink-0 rounded-full animate-pulse",
          severityColor(data.severity),
        ].join(" ")}
      />
      <span className="max-w-[120px] truncate text-[10px] font-semibold text-slate-200">
        {label}
      </span>
      <span className="text-[9px] uppercase tracking-wide text-slate-500">{data.severity}</span>
    </div>
  );
}

export function DefaultNode({ data, selected }: DeviceNodeProps) {
  const label =
    data.device_id ?? data.port_id ?? data.link_id ?? data.alarm_id ?? data.service_id ?? data.id;
  return (
    <div
      data-testid={`node-${data.id}`}
      className={[
        "flex w-28 items-center gap-2 rounded-lg border bg-slate-800 p-2 shadow-md",
        selected ? "border-sky-400" : "border-slate-600",
      ].join(" ")}
    >
      <Network className="h-4 w-4 text-slate-400" />
      <p className="truncate text-[10px] font-semibold text-slate-200">{label}</p>
    </div>
  );
}
