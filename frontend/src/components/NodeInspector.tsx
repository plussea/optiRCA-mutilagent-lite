import { Database, GitBranch, ScrollText, TerminalSquare } from "lucide-react";
import type { SessionState, WorkflowEvent } from "../lib/types";

const subgraphs: Record<string, Array<{ id: string; label: string; type: string }>> = {
  perception: [
    { id: "detect_input", label: "识别输入", type: "Router" },
    { id: "parse_csv", label: "解析 CSV", type: "Tool" },
    { id: "normalize_fields", label: "字段归一", type: "Agent" },
    { id: "summarize", label: "生成摘要", type: "Agent" },
  ],
  diagnosis: [
    { id: "build_query", label: "构造查询", type: "Agent" },
    { id: "vector_search", label: "LanceDB 检索", type: "Tool" },
    { id: "graph_context", label: "拓扑上下文", type: "Tool" },
    { id: "llm_rca", label: "LLM 根因分析", type: "LLM" },
    { id: "fallback", label: "启发式兜底", type: "Guardrail" },
  ],
  closure: [
    { id: "case_pack", label: "案例打包", type: "Agent" },
    { id: "vector_write", label: "向量记忆写入", type: "Memory" },
    { id: "graph_write", label: "经验关系写入", type: "Memory" },
  ],
};

const titles: Record<string, string> = {
  perception: "感知",
  diagnosis: "诊断",
  validation: "诊断校验",
  planning: "方案规划",
  solution_validation: "方案校验",
  human_review: "人工审核",
  closure: "经验回收",
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
    <aside className="glass rounded-[2rem] p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-cyanline">Inspector</p>
          <h2 className="mt-1 text-xl font-bold text-ink">{titles[selectedNode] ?? selectedNode}</h2>
          <p className="mt-1 text-xs text-slate-500">{selectedNode}</p>
        </div>
        <div className="rounded-2xl border border-cyanline/20 bg-cyanline/10 p-3 text-cyanline">
          <ScrollText className="h-5 w-5" />
        </div>
      </div>

      {children.length > 0 && (
        <div className="mt-5 rounded-2xl border border-cyanline/20 bg-slate-950/50 p-4">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-cyanline">
            <GitBranch className="h-4 w-4" />
            子图拓扑
          </div>
          <div className="space-y-2">
            {children.map((child, index) => (
              <div key={child.id} className="flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/60 p-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-cyanline/10 text-xs font-bold text-cyanline">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-100">{child.label}</p>
                  <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{child.type}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Section title="审计事件" icon={<TerminalSquare className="h-4 w-4" />}>
        {nodeEvents.length ? (
          nodeEvents.map((event) => (
            <div key={`${event.phase}-${event.created_at}`} className="rounded-xl border border-slate-700/50 bg-slate-950/55 p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-slate-100">{event.phase}</p>
                <p className="text-[11px] text-slate-500">{new Date(event.created_at).toLocaleTimeString()}</p>
              </div>
              <p className="mt-2 line-clamp-2 text-xs text-slate-500">{JSON.stringify(event.payload)}</p>
            </div>
          ))
        ) : (
          <Empty text="暂无节点事件" />
        )}
      </Section>

      <Section title="Runtime 决策" icon={<GitBranch className="h-4 w-4" />}>
        {trace.length ? (
          trace.map((item, index) => (
            <div key={index} className="rounded-xl border border-slate-700/50 bg-slate-950/55 p-3 text-xs text-slate-300">
              <p>Skill: <span className="text-cyanline">{item.skill ?? "none"}</span></p>
              <p className="mt-1 text-slate-500">Reason: {item.reason ?? "-"}</p>
            </div>
          ))
        ) : (
          <Empty text="暂无决策记录" />
        )}
      </Section>

      <Section title="工具调用" icon={<Database className="h-4 w-4" />}>
        {tools.length ? (
          tools.map((item, index) => (
            <p key={index} className="rounded-xl border border-slate-700/50 bg-slate-950/55 p-3 text-xs text-slate-300">
              {(item.tools ?? []).join(", ")}
            </p>
          ))
        ) : (
          <Empty text="暂无工具调用" />
        )}
      </Section>

      <Section title="节点输出" icon={<ScrollText className="h-4 w-4" />}>
        <pre className="max-h-72 overflow-auto rounded-2xl border border-slate-800 bg-black/55 p-4 text-xs leading-5 text-slate-200">
          {JSON.stringify(output, null, 2)}
        </pre>
      </Section>
    </aside>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-200">
        <span className="text-cyanline">{icon}</span>
        {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-xl border border-slate-700/50 bg-slate-950/40 p-3 text-xs text-slate-500">{text}</p>;
}
