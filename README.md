# OptiRCA Lite

OptiRCA Lite 是一个面向光网络告警的本地根因诊断工作台。它把告警 CSV、可选业务拓扑和多阶段 Agent 推理组合成可回放、可审核的诊断流程，最终输出物理根因、传播解释、可信度检查和诊断案卷。

项目默认使用 SQLite、LanceDB 和 JSON 图存储，不要求 Docker、PostgreSQL、Redis 或 Neo4j。未配置大模型时仍可使用确定性的规则基线运行仓库内 Demo。

## 你可以用它做什么

- 逐个上传告警 CSV 并查看诊断结果。
- 复杂场景上传拓扑 JSON；简单场景由系统尝试推断拓扑。
- 在诊断前识别拓扑歧义，输入不足时阻止不可信推理。
- 通过 SSE 查看六个真实阶段的进度、产物和耗时。
- 在业务拓扑中查看根因链路、首发告警和受影响设备。
- 确认系统结论、纠正根因或请求专家复核。
- 刷新后恢复当前诊断，并使用同一批持久化事件回放过程。
- 通过浏览器打印功能导出诊断报告或保存为 PDF。

## 一键启动（推荐）

### 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- Node.js 18 或更高版本（包含 npm）

在项目根目录运行：

```powershell
.\start.ps1
```

也可以直接双击 `start.cmd`。第一次启动会自动：

1. 创建根目录 `.venv` Python 虚拟环境；
2. 安装后端依赖；
3. 安装前端依赖；
4. 在后台启动前后端；
5. 等待健康检查通过并打开工作台。

后续启动会复用已经安装的依赖和正在运行的服务。

访问地址：

- 工作台：<http://127.0.0.1:5173>
- API 文档：<http://127.0.0.1:8010/docs>

停止由脚本启动的服务：

```powershell
.\stop.ps1
```

或双击 `stop.cmd`。

常用参数：

```powershell
# 启动后不自动打开浏览器
.\start.ps1 -NoBrowser

# 已确认依赖完整时跳过安装检查
.\start.ps1 -SkipInstall
```

运行日志保存在 `.run/`。如果启动失败，可查看：

```text
.run/logs/backend.stderr.log
.run/logs/frontend.stderr.log
```

## 用真实 Demo 完成第一次诊断

1. 打开工作台。
2. 点击“加载真实 Demo”。
3. 等待输入预检显示“输入已就绪”。
4. 点击“开始诊断”。
5. 等待六个阶段完成。

Demo 使用仓库中的真实文件：

```text
demo/01/alarm.csv
demo/01/topology.json
demo/01/expected.json
```

预期根因为：

```text
link:N1-N2
```

`expected.json` 只用于结果验收，不会进入推理输入。

`demo/` 中共提供 10 组可逐个上传的告警样本，覆盖光纤断纤、线路衰减过大、光放大器失效和色散补偿异常。文件对应关系与预期根因见 [Demo 样本索引](demo/README.md)。

## 输入文件

### 告警 CSV（必需）

系统会尝试识别以下中英文字段：

| 业务含义 | 常见字段 |
|---|---|
| 设备 | `device_id`、`device`、`设备`、`网元` |
| 告警类型 | `alarm_type`、`alarm_name`、`告警名称` |
| 端口 | `port_id`、`port`、`端口` |
| 严重级别 | `severity`、`level`、`告警级别` |
| 时间 | `timestamp`、`time`、`最近发生时间` |

设备和告警类型是正式诊断的核心字段。没有拓扑 JSON 时，端口字段决定系统能否唯一推断多设备之间的链路。

### 拓扑 JSON（可选）

复杂拓扑、分支、环路或多传播路径场景建议提供：

```json
{
  "devices": [
    { "device_id": "N1", "type": "OADM" },
    { "device_id": "N2", "type": "OXC" }
  ],
  "ports": [
    { "port_id": "N1:N1-N2", "device_id": "N1", "direction": "out" },
    { "port_id": "N2:N1-N2", "device_id": "N2", "direction": "in" }
  ],
  "links": [
    {
      "link_id": "N1-N2",
      "endpoint_a": "N1:N1-N2",
      "endpoint_b": "N2:N1-N2"
    }
  ]
}
```

如果未提供拓扑且 CSV 无法唯一还原连接关系，预检会返回需要补充的字段，不会创建诊断会话或污染质量统计。

## 手动启动

需要分别调试前后端时，可以使用传统方式。

后端：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .\backend
cd backend
python -m optirc_lite.api.main
```

前端（新终端）：

```powershell
cd frontend
npm install
npm run dev
```

## 可选的大模型配置

规则基线无需大模型即可运行。需要启用 OpenAI-compatible LLM 增强时，将 `.env.example` 复制为 `.env`，并配置：

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=30
```

`LLM_BASE_URL` 可以是 API 根地址，也可以是完整的 `/chat/completions` 地址。调用失败时系统会回退到规则诊断。

## 诊断流程

```text
告警 CSV + 可选拓扑 JSON
        │
        ▼
输入预检 ──歧义──> 阻止诊断并提示补充信息
        │ 就绪
        ▼
告警解析 → 拓扑构建 → 传播判断 → 根因排序 → 可信度复核 → 案卷组装
        │
        ▼
业务拓扑 + 根因结论 + 人工审核 + 诊断报告
```

同一诊断运行内的 Agent 共享 session 级异构证据图；不同运行完全隔离，避免重复运行和并发请求产生交叉污染。

## API 速查

新工作台使用以下接口：

| 方法 | 接口 | 用途 |
|---|---|---|
| `POST` | `/api/v1/preflight` | 上传 CSV 和可选拓扑，执行输入预检 |
| `POST` | `/api/v1/diagnoses` | 从已通过的预检创建异步诊断 |
| `GET` | `/api/v1/diagnoses/{session_id}` | 获取或恢复会话状态 |
| `GET` | `/api/v1/diagnoses/{session_id}/events` | SSE 事件流与断线续传 |
| `POST` | `/api/v1/diagnoses/{session_id}/cancel` | 取消运行中的诊断 |
| `POST` | `/api/v1/diagnoses/{session_id}/review` | 提交人工审核和真值 |
| `GET` | `/api/v1/examples/demo` | 读取仓库内真实 Demo |
| `GET` | `/v1/dossier/{dossier_id}` | 获取五层诊断案卷 |

兼容和离线接口：

| 方法 | 接口 | 用途 |
|---|---|---|
| `POST` | `/api/v1/diagnose` | 兼容的同步端到端诊断 |
| `POST` | `/v1/evaluate` | 对诊断案卷进行离线评测 |
| `POST` | `/v1/gepa` | 从评测结果生成策略优化提案 |

## 项目结构

```text
backend/optirc_lite/
  api/                  FastAPI 接口
  workflow/             LangGraph 诊断流程
  runtime/              State-Aware Agent Runtime
  skills/               Perception / Topology / Judge / Rank / Critic 等能力
  storage/              SQLite / LanceDB / session 级证据图
frontend/src/
  components/           输入、业务拓扑、阶段进度和结果审核组件
  lib/                  API 客户端与类型契约
demo/                   可直接运行的真实示例及独立预期
docs/                   产品、规格、架构、研究和历史 Issue 文档
scripts/                研究绘图等辅助脚本
start.ps1 / stop.ps1    一键启停脚本
```

## 测试

后端全量测试：

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
```

前端构建：

```powershell
cd frontend
npm run build
```

浏览器端到端测试（会启动前后端）：

```powershell
cd frontend
npx playwright test
```

关键回归覆盖拓扑预检、异步 session、SSE 续传、取消、人工真值、刷新恢复，以及 Demo 连续运行三次时的证据图隔离。

## 关键文档

- [`CONTEXT.md`](CONTEXT.md)：领域模型、术语和系统边界。
- [`docs/README.md`](docs/README.md)：全部文档的分类索引。
- [`docs/specs/diagnosis-workbench-implementation-spec.md`](docs/specs/diagnosis-workbench-implementation-spec.md)：工作台完整实施规格。
- [`docs/adr/`](docs/adr/)：关键架构决策。
- [`docs/product/project_prd_refactor.md`](docs/product/project_prd_refactor.md)：Agent 重构 PRD。

## 常见问题

### PowerShell 禁止执行脚本

直接使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

或双击 `start.cmd`。

### 端口被占用

项目默认使用：

- 前端：`5173`
- 后端：`8010`

如果这些端口已经由可访问的 OptiRCA 服务占用，启动脚本会直接复用；如果被其他程序占用，请先释放端口。

### 前端显示服务不可用

检查 `.run/logs/backend.stderr.log`，然后访问 <http://127.0.0.1:8010/docs> 确认后端是否已启动。
