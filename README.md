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

当前主链路基于 PRD 重构：

```text
POST /api/v1/diagnose
  -> Alarm Parser + Topology Builder（感知层）
  -> Propagation Judge（判断层）
  -> Root Cause Ranker（排序层）
  -> Critic Reviewer（复核层）
  -> Case Archivist / Evaluator / GEPA（归档与自迭代层）
```

所有 Agent 通过异构证据图共享状态，不直接调用；最终输出诊断案卷（Diagnosis Dossier）。

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

- CSV 告警解析与关键字段归一化（Alarm Parser）。
- JSON 拓扑解析与异构证据图构建（Topology Builder）。
- 候选传播链生成（Propagation Judge）。
- 六维特征打分与 Top-K 排序（Root Cause Ranker）。
- 三挑战反事实复核与回退控制（Critic Reviewer）。
- 降级输出（ADR-0007）与规则基线回退。
- 五层结构诊断案卷归档（Case Archivist）。
- 离线回归指标与错误归因（Evaluator）。
- 遗传-帕累托策略优化器（GEPA）。
- OpenAI-compatible LLM Tool，失败时自动回退到启发式诊断/规划。
- Runtime Trace 前端展示。

## API 速查

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v1/diagnose` | POST | 端到端诊断：CSV + 拓扑 JSON |
| `/v1/dossier/{dossier_id}` | GET | 获取诊断案卷 |
| `/v1/evaluate` | POST | 对一批案卷运行离线回归 |
| `/v1/evaluate/{evaluation_id}` | GET | 获取评测报告 |
| `/v1/gepa` | POST | 从评测报告生成策略提案 |
| `/v1/gepa/{optimization_id}` | GET | 获取 GEPA 优化报告 |
| `/v1/refactor/parse` | POST | 感知层 seam |
| `/v1/refactor/judge-rank` | POST | Judge + Ranker seam |
| `/v1/refactor/critic` | POST | Critic seam |
| `/v1/sessions` | POST | 旧版会话入口（向后兼容） |
| `/v1/sessions/{id}` | GET | 获取会话状态 |
| `/v1/sessions/{id}/human-decision` | POST | 人工审核闭环 |

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

## 关键文档

- `CONTEXT.md` — 领域模型、Agent 分类、术语表、质量目标
- `project_prd_refactor.md` — 产品需求与模块详细设计
- `spec_prd_refactor.md` — 重构 Spec 与测试 seams
- `spec_gepa_optimizer.md` — GEPA/Evaluator/Archivist 详细 Spec
- `docs/adr/` — 架构决策记录（ADR-0001 至 ADR-0008）

## 后续建议

- 用真实 embedding 模型替换当前轻量 hash embedding。
- 把 Topology Builder 升级为弱拓扑推断 + 边置信度。
- 拆分 Judge/Ranker 内部子模块（Generator/Validator、Feature Scorer/Aggregator）。
- 在 Judge 和 Critic 中引入 LLM 增强推理，保留规则回退。
- 增加故障注入仿真与灰度发布机制。
- 增加 E2E 测试：上传 CSV -> 等待审核 -> 批准 -> 闭环。
