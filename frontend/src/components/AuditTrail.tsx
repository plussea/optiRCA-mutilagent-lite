import type { WorkflowEvent } from "../lib/types";

interface Props {
  events: WorkflowEvent[];
}

export function AuditTrail({ events }: Props) {
  return (
    <section className="glass rounded-[2rem] p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyanline">Audit Trail</p>
          <h2 className="mt-1 text-lg font-bold text-ink">运行审计</h2>
        </div>
        <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1 text-xs font-semibold text-slate-400">
          {events.length} events
        </span>
      </div>
      <div className="mt-4 max-h-72 space-y-2 overflow-auto pr-1">
        {events.length ? (
          events.map((event, index) => (
            <div key={`${event.phase}-${index}`} className="rounded-2xl border border-slate-700/50 bg-slate-950/50 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-100">{event.phase}</p>
                <p className="text-[11px] text-slate-400">
                  {new Date(event.created_at).toLocaleTimeString()}
                </p>
              </div>
              <p className="mt-1 truncate text-xs text-slate-400">
                {JSON.stringify(event.payload)}
              </p>
            </div>
          ))
        ) : (
          <p className="rounded-2xl border border-slate-700/50 bg-slate-950/50 p-4 text-sm text-slate-500">暂无事件</p>
        )}
      </div>
    </section>
  );
}
