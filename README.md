# OptiRCA Lite

轻量版光网络根因分析 Agent。它不依赖 Docker、PostgreSQL、Redis、Neo4j 或 ChromaDB，默认使用本地 SQLite、嵌入式 LanceDB 和 JSON 图存储，适合快速启动、演示和后续重构实验。

## 设计目标

- 编译时 Workflow 保证流程稳定、可观测、可测试。
- State-Aware Runtime 在每个阶段内根据状态选择 Skill。
- Skill 封装“工具 + 策略 + Pydantic 输出结构”，Tool 保持原子化。
- LanceDB 作为本地向量数据库，不需要启动独立服务。
- 前端采用 Vite + React + Tailwind，界面简洁轻量。

## 架构

```text
LangGraph Workflow
  -> AgentRuntime
  -> SkillRegistry
  -> Skill with Pydantic schema
  -> ToolRegistry
  -> SQLite / LanceDB / JSON graph / OpenAI-compatible LLM
```

## 快速启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m optirc_lite.api.main
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

示例文件：

```text
examples/demo_alarm.csv
```

## 环境变量

复制 `.env.example` 为 `.env`，然后填入你的 OpenAI-compatible LLM 配置：

```text
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
```

`LLM_BASE_URL` 可以填 API 根地址，也可以填完整 `/chat/completions` 地址，后端会自动归一化。

## 当前能力

- CSV 告警解析与关键字段归一化。
- LanceDB 本地向量检索，默认内置光网络知识和 SOP 种子数据。
- JSON 拓扑图邻居查询。
- OpenAI-compatible LLM Tool，失败时自动回退到启发式诊断/规划。
- 根因诊断 Skill。
- 诊断 Critic 与方案 Critic。
- 修复方案生成 Skill。
- 人工审核与批准后知识闭环。
- Runtime Trace 前端展示。

## 目录

```text
backend/optirc_lite/
  api/            FastAPI API
  workflow/       LangGraph 编译时流程
  runtime/        State-Aware Runtime
  skills/         可复用 Agent 能力与 Pydantic schema
  tools/          原子工具注册表，包括 LLM Tool
  storage/        SQLite / LanceDB / JSON 图存储
frontend/
  src/            Vite React UI
examples/
  demo_alarm.csv
```

## 后续建议

- 用真实 embedding 模型替换当前轻量 hash embedding。
- 给 Tool 也增加输入输出 schema。
- 把人工审核升级为 LangGraph 原生 interrupt + SQLite checkpointer。
- 增加 E2E 测试：上传 CSV -> 等待审核 -> 批准 -> 闭环。
