import { GitBranch, ScrollText } from "lucide-react";
import type { SessionState, WorkflowEvent } from "../lib/types";

const subgraphs: Record<string, Array<{ id: string; label: string }>> = {
  perception: [
    { id: "detect_input", label: "识别输入" },
    { id: "parse_csv", label: "解析 CSV" },
    { id: "normalize_fields", label: "字段归一" },
    { id: "summarize", label: "生成摘要" },
  ],
  diagnosis: [
    { id: "build_query", label: "构造查询" },
    { id: "vector_search", label: "LanceDB 检索" },
    { id: "graph_context", label: "拓扑上下文" },
    { id: "llm_rca", label: "LLM 根因分析" },
    { id: "fallback", label: "启发式兜底" },
  ],
};

interface Props {
  state: SessionState | null;
  events: WorkflowEvent[];
  selectedNode: string;
}

export function NodeInspector({ state, events, selectedNode }: Props) {
  const nodeEvents = events.filter((event) => event.phase.startsWith(`${selectedNode}.`));
  const output = (state as any)?.[selectedNode] ?? {};
  const trace = state?.decision_trace?.filter((item) => item.phase === selectedNode) ?? [];
  const tools = state?.tool_calls?.filter((item) => item.phase === selectedNode) ?? [];
  const children = subgraphs[selectedNode] ?? [];

  return (
    <aside className="glass rounded-3xl p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Node Inspector</p>
          <h2 className="mt-1 text-lg font-bold text-ink">{selectedNode}</h2>
        </div>
        <ScrollText className="h-5 w-5 text-brand" />
      </div>

      {children.length > 0 && (
        <div className="mt-5 rounded-2xl border border-indigo-100 bg-indigo-50/70 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-brand">
            <GitBranch className="h-4 w-4" />
            子图
          </div>
          <div className="space-y-2">
            {children.map((child, index) => (
              <div key={child.id} className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white text-xs font-bold text-brand">
                  {index + 1}
                </span>
                <span className="text-sm text-slate-700">{child.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Section title="审计事件">
        {nodeEvents.length ? (
          nodeEvents.map((event) => (
            <div key={`${event.phase}-${event.created_at}`} className="rounded-xl bg-white/70 p-3">
              <p className="text-xs font-semibold text-slate-700">{event.phase}</p>
              <p className="mt-1 text-[11px] text-slate-400">{new Date(event.created_at).toLocaleString()}</p>
            </div>
          ))
        ) : (
          <Empty text="暂无节点事件" />
        )}
      </Section>

      <Section title="Runtime 决策">
        {trace.length ? (
          trace.map((item, index) => (
            <div key={index} className="rounded-xl bg-white/70 p-3 text-xs text-slate-600">
              <p>Skill: {item.skill ?? "none"}</p>
              <p>Reason: {item.reason ?? "-"}</p>
            </div>
          ))
        ) : (
          <Empty text="暂无决策记录" />
        )}
      </Section>

      <Section title="工具调用">
        {tools.length ? (
          tools.map((item, index) => (
            <p key={index} className="rounded-xl bg-white/70 p-3 text-xs text-slate-600">
              {(item.tools ?? []).join(", ")}
            </p>
          ))
        ) : (
          <Empty text="暂无工具调用" />
        )}
      </Section>

      <Section title="节点输出">
        <pre className="max-h-72 overflow-auto rounded-2xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">
          {JSON.stringify(output, null, 2)}
        </pre>
      </Section>
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 text-sm font-semibold text-slate-700">{title}</h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-xl bg-white/60 p-3 text-xs text-slate-400">{text}</p>;
}
