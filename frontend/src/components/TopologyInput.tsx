interface Props {
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
}

export function TopologyInput({ value, onChange, compact }: Props) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={compact ? 4 : 6}
      className={[
        "rounded-xl border border-slate-700 bg-slate-900/80 p-3 font-mono text-xs text-slate-300 outline-none",
        "placeholder:text-slate-600 focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/20",
        compact ? "w-full" : "w-full max-w-xl",
      ].join(" ")}
      placeholder='{"devices":[],"ports":[],"links":[]}'
    />
  );
}
