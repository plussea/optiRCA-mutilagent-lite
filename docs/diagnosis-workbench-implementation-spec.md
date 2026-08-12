# OptiRCA Lite 诊断工作台实施规格

状态：已确认
日期：2026-08-12
第一受众：懂光网络业务的项目评审者

## 1. 目标

将当前前端改造为桌面端单样本诊断工作台，并同步补齐支撑该体验所需的后端能力。评审者应能上传一份告警 CSV、按需补充拓扑 JSON，在 30 秒内看到真实的多 Agent 执行过程，并通过业务拓扑、诊断结论、可信度检查和人工审核判断结果是否可信。

当前 Demo 的业务验收目标是：使用仓库内 `demo/alarm1.csv` 与 `demo/topology.json`，稳定得到根因 `link:N1-N2`，并解释 8 条告警如何收敛为一个物理故障。

## 2. 已确认的范围

### 2.1 首版包含

- 单份告警 CSV 上传，拓扑 JSON 可选且分别上传。
- 无拓扑时自动执行拓扑预检；信息不足或存在歧义时阻止诊断。
- 单页三状态：输入准备、正式诊断、结果查看。
- 异步诊断 session、SSE 实时事件、取消与刷新恢复。
- 每个诊断运行独立的异构证据图。
- 设备/链路级业务拓扑主视图，端口/告警/异构证据关系按需下钻。
- 动态诊断摘要、四项诊断结论、Top-3 解释与 Critic 可信度检查。
- 所有正式诊断均可人工审核，并将人工真值写入诊断案卷。
- 可打印或导出为 PDF 的单次诊断报告。
- 当前一个内置示例及其真实结果验收。
- 桌面浏览器，设计基准 1440×900，最低可用 1280×720。

### 2.2 首版不包含

- 批量上传、样本集管理、历史运行列表和结果横向比较。
- Evaluator、GEPA 的可操作页面。
- 多根因正式支持；疑似多故障场景按降级诊断处理。
- 工单系统、审核队列、权限体系和在线分享。
- 手机和平板适配。

## 3. 当前实现缺口

以下问题必须作为改造前置，而不能通过视觉调整掩盖：

1. `frontend/src/lib/demo.ts` 复制并硬编码 Demo 数据，没有读取 `demo/` 的真实文件。
2. 模块级 `evidence_graph.json` 跨请求共享；连续运行会因重复节点报错并返回 `agent_failure`。
3. `useStagePlayback` 在收到最终响应后按 900ms 定时回放，不代表真实 Agent 进度。
4. 自定义 React Flow 节点缺少连接 Handle，业务图中的所有边创建失败。
5. E2E 在初始状态即可匹配 `data-risk="normal"`，没有证明诊断真实完成。
6. `/api/v1/diagnose` 将拓扑定义为必填字段，前端也强制解析 JSON。
7. 当前弱拓扑推断只补充已知设备端口中的局部缺失链路，不能承担纯 CSV 的完整预检。
8. 案卷已有 `ground_truth`，但人工审核接口不接收也不写入该字段。
9. 当前审核接口只允许 `pending_human=true` 的 session 提交反馈，与“成功结果也可审核”冲突。
10. 当前同步诊断入口无法支持真实进度、取消或断线续传。

## 4. 状态模型

工作台使用以下明确状态，不从零散布尔值推断页面：

| 状态 | 含义 | session | 案卷 |
|---|---|---:|---:|
| `empty` | 尚未选择 CSV | 否 | 否 |
| `preflighting` | 正在解析输入并检查拓扑充分性 | 否 | 否 |
| `input_not_ready` | 预检未通过，等待拓扑 JSON 或更换 CSV | 否 | 否 |
| `ready` | 输入已就绪，可开始诊断 | 否 | 否 |
| `running` | 正式诊断执行中 | 是 | 否 |
| `success` | 完整自动诊断完成 | 是 | 是 |
| `degraded` | 正式诊断开始后未形成完整自动结论 | 是 | 是 |
| `cancelled` | 用户主动取消 | 是 | 否 |

审核状态与诊断状态正交：

- `unreviewed`
- `confirmed`
- `corrected`
- `expert_review_requested`

## 5. 输入与拓扑预检

### 5.1 输入区

- 告警 CSV 是主输入，必须提供。
- 拓扑 JSON 是可选输入，可晚于 CSV 添加、替换或移除。
- 两个文件各自显示文件名、解析结果、更换和移除入口。
- 不显示可直接编辑的裸 JSON 文本框。
- CSV 上传或拓扑变更后自动重新预检。
- 诊断开始后锁定输入；发现错误需先取消。
- 诊断完成后修改输入会创建新的诊断运行，不覆盖旧案卷。

### 5.2 预检通过规则

未提供拓扑 JSON 时，仅以下情形允许进入正式诊断：

1. 全部相关告警明确收敛于同一设备，可建立单设备拓扑。
2. 端口或定位字段能够唯一识别链路两端，不存在连接歧义、方向冲突或无法配对的端点。

以下任一情形必须返回 `input_not_ready`：

- 多设备但无法唯一确定连接关系。
- 同一端口存在多个可能远端。
- 链路只有不可解释的单端信息。
- 设备或端口标识缺失、格式无效或相互矛盾。
- 需要判断分支、环路或多条传播路径，但 CSV 无法唯一还原。

用户提供拓扑 JSON 后，它作为权威拓扑，但仍需检查 JSON 结构、端点引用和告警对象映射是否合法。

### 5.3 预检输出

预检至少返回：

```json
{
  "status": "ready",
  "preflight_id": "PF-...",
  "sample_summary": {
    "alarm_count": 8,
    "severity_counts": {"critical": 2, "major": 6},
    "device_count": 4,
    "alarm_types": ["OTS_LOS", "OSC_LOS", "OMS_LOS_P", "OCH_LOS_P"],
    "time_window": {"start": "...", "end": "..."}
  },
  "topology": {
    "source": "provided",
    "confidence": 1.0,
    "devices": [],
    "links": [],
    "inference_explanations": []
  },
  "issues": []
}
```

失败时 `status` 为 `input_not_ready`，`issues` 必须提供稳定错误码、自然中文说明、受影响对象和需要补充的字段。预检失败不得创建 session 或案卷。

`preflight_id` 是短期输入准备标识，不是诊断 session；开始诊断时后端必须校验输入摘要或内容哈希未发生变化。

## 6. 后端接口

保留现有同步 `POST /api/v1/diagnose` 供兼容调用；新工作台使用以下异步接口：

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/v1/preflight` | 上传 CSV 和可选 JSON，返回输入摘要与拓扑预检结果 |
| `POST` | `/api/v1/diagnoses` | 使用已通过的 `preflight_id` 创建诊断运行，返回 `202` 与 session 标识 |
| `GET` | `/api/v1/diagnoses/{session_id}` | 恢复当前运行状态、结果和审核状态 |
| `GET` | `/api/v1/diagnoses/{session_id}/events` | SSE 实时事件流及断线续传 |
| `POST` | `/api/v1/diagnoses/{session_id}/cancel` | 取消当前运行 |
| `POST` | `/api/v1/diagnoses/{session_id}/review` | 提交确认、纠错或专家复核请求 |
| `GET` | `/v1/dossier/{dossier_id}` | 获取完整诊断案卷，继续保留 |
| `GET` | `/api/v1/examples/demo` | 加载仓库内真实示例文件和独立样本预期 |

### 6.1 创建诊断运行

请求：

```json
{
  "preflight_id": "PF-...",
  "max_fallback_rounds": 2
}
```

响应：

```json
{
  "session_id": "...",
  "status": "running",
  "events_url": "/api/v1/diagnoses/.../events"
}
```

同一页面在已有 `running` session 时不得再次创建运行。后端仍需保证接口幂等或拒绝重复提交，不能只依赖按钮禁用。

### 6.2 SSE 事件

每条事件使用 SQLite 自增 ID 作为 SSE `id`，支持浏览器通过 `Last-Event-ID` 补取遗漏事件。事件至少包含：

```typescript
type DiagnosisEvent =
  | { type: "diagnosis.started"; timestamp: string }
  | { type: "stage.started"; stage: StageId; timestamp: string }
  | { type: "stage.completed"; stage: StageId; timestamp: string; elapsed_ms: number; summary: string; artifact?: object }
  | { type: "topology.updated"; timestamp: string; topology: BusinessTopology }
  | { type: "candidates.updated"; timestamp: string; candidates: RootCauseCandidate[] }
  | { type: "critic.checked"; timestamp: string; checks: CredibilityCheck[]; fallback_action?: string }
  | { type: "diagnosis.completed"; timestamp: string; result: DiagnosisResult }
  | { type: "diagnosis.degraded"; timestamp: string; result: DiagnosisResult }
  | { type: "diagnosis.cancelled"; timestamp: string };
```

阶段固定为：告警解析、拓扑构建、传播判断、根因排序、可信度复核、案卷组装。界面显示中文业务名称，英文 Agent 名作为辅助标签。

完成后的“回放诊断”必须消费已持久化的同一批事件，不再生成定时伪事件。

### 6.3 取消

- 取消接口设置 session 取消标记，并停止调度尚未开始的 Agent。
- 正在执行且不可中断的原子操作完成后不得进入下一阶段。
- 已产生事件保留，状态变为 `cancelled`。
- 不生成正式案卷，不计入诊断失败率。
- 前端返回 `ready`，保留已上传输入。

### 6.4 审核与人工真值

请求：

```json
{
  "decision": "confirmed | corrected | expert_review_requested",
  "ground_truth": {"root_cause": "link:N1-N2"},
  "notes": "可选说明"
}
```

规则：

- `confirmed`：`ground_truth` 使用当前系统根因。
- `corrected`：必须从业务拓扑选择设备、端口或链路作为正确根因。
- `expert_review_requested`：不得生成 `ground_truth`。
- 成功和降级诊断均允许提交；降级结果在界面中突出审核要求。
- 审核更新现有案卷，不覆盖系统预测、候选列表和原始事件。

## 7. 证据图与业务拓扑

### 7.1 session 隔离

- 禁止请求路径继续使用单个模块级可变 `EvidenceGraph()` 存储。
- 通过明确的 session 级仓库，例如 `EvidenceGraphRepository.for_session(session_id)`，向各 Agent 提供同一运行内的共享黑板。
- 新 session 必须从空图开始。
- 最终图快照进入诊断案卷；旧案卷不可因重试或新样本而改变。
- 需要支持至少三个连续运行和合理并发，不出现重复节点或交叉污染。

### 7.2 业务拓扑投影

主画布不是异构证据图的直接渲染，而是从其投影出的设备/链路视图：

```typescript
interface BusinessTopologyNode {
  id: string;
  label: string;
  deviceType?: string;
  state: "root" | "direct_alarm" | "affected" | "normal" | "unknown";
  alarmCount: number;
}

interface BusinessTopologyEdge {
  id: string;
  source: string;
  target: string;
  state: "root" | "affected" | "normal" | "unknown";
  sourceKind: "provided" | "inferred";
  confidence: number;
  inferenceExplanation?: string;
}
```

- 默认只展示设备与物理链路。
- 点击对象后在侧栏展示端口、告警、证据链和推断依据。
- 权威拓扑使用实线，推断拓扑使用虚线。
- 相同拓扑使用确定性布局；允许缩放、平移、临时拖动和一键复位。
- 自定义图节点必须提供合法连接点，浏览器控制台不得出现连线创建警告。

## 8. 前端信息架构

### 8.1 全局框架

- 顶部品牌：`OptiRCA Lite` / `光网络告警根因诊断工作台`。
- 中文业务语言为主，英文 Agent 名为小型辅助标签。
- 桌面端单页，无业务路由跳转。
- 当前 session ID 存入浏览器本地状态，仅用于刷新恢复；不读取或持久化本地文件内容。

### 8.2 输入准备态

主体由四部分组成：

1. 告警 CSV 上传卡。
2. 可选拓扑 JSON 上传卡。
3. 告警摘要与拓扑预检结果。
4. “开始诊断”主按钮与“加载示例”次按钮。

原始告警默认显示摘要：总数、严重级别分布、设备数、时间窗口和告警类型；“查看全部告警”展开只读表格，并支持按设备、级别和类型筛选。

### 8.3 诊断运行态

- 保留收缩后的输入摘要。
- 主区域显示逐步形成的业务拓扑。
- 上方显示真实阶段、阶段产物和实际耗时。
- 当前阶段只呈现一句面向业务的产物摘要，原始日志放入下钻详情。
- 提供“取消诊断”。

### 8.4 成功结果态

第一层结论只包含：

1. 根因，例如 `N1–N2 光纤链路故障`。
2. 可信度。
3. 告警收敛解释，例如 `8 条告警由 1 个物理故障解释`。
4. 建议动作。

同时生成动态诊断摘要，例如：

> 8 条并发告警涉及 4 台异常设备。系统在 8.4 秒内将告警收敛为 1 个物理故障：N1–N2 光纤链路异常。该结论解释全部 8 条告警，并通过三项可信度检查。

所有数字来自当前运行，不得硬编码。

完成后 Agent 进度收缩为一行，例如：`6 个阶段 · 8.4 秒 · 可信度复核已通过`。点击后展开真实事件、Top-3 候选、候选业务理由、评分细节、回退记录和日志。

### 8.5 可信度检查

Critic 不只显示 `pass/reject`，而是呈现：

- 告警解释完整性。
- 链路两端一致性。
- 单一故障合理性。

每项显示通过、未通过、业务理由及触发的回退动作。疑似多个独立告警簇时输出“疑似多故障场景”的降级结果，不强行选择最终根因。

### 8.6 降级结果态

- 不使用绿色成功样式。
- 显示失败阶段、降级原因、已完成阶段和部分证据。
- 规则候选只能称为“人工复核线索”。
- 明确标记“自动诊断未完成”，突出审核入口。
- 仍生成案卷并允许导出报告。

### 8.7 审核

所有正式结果提供：

- 确认根因。
- 标记结论错误。
- 请求专家复核。

标记错误时，先显示 Top-3 快速选项，再允许从业务拓扑选择其他设备、端口或链路。提交后明确显示“反馈已写入诊断案卷”。

## 9. 视觉规范

- 整体采用浅灰白画布、白色面板和深海军蓝结构色。
- 红色只表示根因或严重告警。
- 橙色只表示受影响对象或待审核状态。
- 绿色只表示正常状态或审核通过。
- 青蓝表示系统推理、交互选中和信息状态。
- 状态不得只依赖颜色，必须同时使用文字、图标或线型。
- 减少玻璃拟态、霓虹光晕、循环呼吸和无业务含义的动画。
- 尊重 `prefers-reduced-motion`。
- 所有主要操作支持键盘；首版不要求完整 WCAG 审计。

具体色值是可调整的设计 token，不属于领域契约。

## 10. 诊断报告

使用独立的打印布局或报告组件，不直接截图当前工作台。报告包含：

- 输入文件与拓扑来源摘要。
- 业务拓扑、根因和传播路径。
- 四项诊断结论与动态诊断摘要。
- Agent 阶段、实际耗时与 Critic 检查。
- 系统预测、Top-3 和降级信息。
- 人工审核状态、人工真值和审核时间。
- session、案卷 ID 与生成时间。

审核状态：

- 审核前：`自动诊断结果 · 未经人工确认`。
- 已确认：`已人工确认`。
- 已纠错：同时展示系统预测和人工确认根因。
- 专家复核：`等待专家复核`。
- 降级：`自动诊断未完成`。

首版可采用打印优化 HTML + 浏览器“保存为 PDF”，不要求引入服务端 PDF 生成器。

## 11. Demo 与样本预期

目录约定：

```text
demo/
  alarm1.csv
  topology.json
  expected.json
```

建议的 `expected.json`：

```json
{
  "root_cause": "link:N1-N2",
  "minimum_alarm_coverage": 1.0,
  "expected_affected_devices": ["N1", "N2", "N4", "N5"]
}
```

“加载示例”从上述文件加载 CSV 和拓扑，进入与普通上传相同的预检和诊断链路。`expected.json` 只保留在示例验收或自动测试上下文中，禁止进入预检 token、Agent state、Prompt、工具调用或诊断案卷的输入层。

若实际结果与样本预期不一致：

- 如实展示实际结果。
- 明确提示“示例预期根因为 N1–N2，当前结果不一致”。
- 不使用成功样式，不生成“演示通过”摘要。
- 允许查看证据、失败阶段和报告。

## 12. 测试与验收

### 12.1 后端

- CSV 单设备收敛场景预检通过。
- CSV 唯一链路场景预检通过。
- 歧义、多远端、缺失标识、分支或环路场景预检阻止诊断。
- 预检失败不创建 session、案卷或评测记录。
- 用户拓扑通过时标记为 `provided`，推断拓扑标记为 `inferred` 并包含依据。
- SSE 事件按顺序持久化，支持 `Last-Event-ID` 续传。
- 取消后不再调度后续阶段且不生成案卷。
- 成功、纠错和专家复核正确写入审核状态与人工真值。
- 疑似多故障场景返回降级结果。
- 三个连续 Demo 运行均返回 `success`、`link:N1-N2`，且证据图互不污染。
- 原有 `backend/tests/` 保持全绿。

### 12.2 前端 E2E

- 加载示例后显示真实文件名和预检摘要，不自动诊断。
- 开始诊断后收到真实 `stage.started/stage.completed` 事件。
- 完成条件必须等待 `diagnosis.completed`，不得通过初始 DOM 属性误判。
- Demo 根因是 `link:N1-N2`，状态非降级，传播路径可见。
- 浏览器控制台没有 React Flow 连线警告或未处理异常。
- 同页连续运行三次均成功，并得到不同 session/案卷 ID。
- 刷新可恢复运行中或已完成 session。
- 取消后保留输入并返回可诊断状态。
- 无拓扑歧义样本被阻止，补充 JSON 后可开始诊断。
- 成功结果可确认；错误结果必须选择人工真值；专家复核不写真值。
- 报告中的审核与降级标记正确。
- 1280×720 下所有主要操作可见且可键盘完成。

### 12.3 Demo 验收门槛

- 端到端耗时小于 30 秒。
- 根因严格等于 `link:N1-N2`。
- 告警覆盖率满足 `expected.json`。
- 业务拓扑正确区分根因、直接告警、受影响和正常对象。
- 三项可信度检查均有业务解释。
- 连续运行三次稳定通过。

## 13. 实施顺序

### 阶段 A：建立可信后端基座

1. 增加 `expected.json` 与真实 Demo 回归测试。
2. 将异构证据图改为 session 级隔离。
3. 增加拓扑预检服务与阻断测试。
4. 先让同步诊断连续三次稳定通过 Demo。

### 阶段 B：异步运行闭环

1. 增加异步诊断创建、状态查询、SSE 和取消接口。
2. 规范并持久化阶段产物、耗时与最终事件。
3. 支持断线续传和刷新恢复。
4. 保持同步 `/api/v1/diagnose` 兼容。

### 阶段 C：审核与案卷

1. 扩展审核接口和状态模型。
2. 写入人工真值，并保证系统预测不可变。
3. 覆盖成功、降级、纠错和专家复核测试。

### 阶段 D：重建前端工作台

1. 建立显式状态机和分离上传区。
2. 接入预检与真实 SSE 进度。
3. 实现业务拓扑投影、确定性布局和对象下钻。
4. 实现结论卡、诊断摘要、Top-3 与可信度检查。
5. 实现审核和刷新恢复。

### 阶段 E：报告与最终验收

1. 实现打印版诊断报告。
2. 补齐基础无障碍、减少动态效果和桌面布局。
3. 重写 Playwright E2E，消除假阳性。
4. 完成连续三次 Demo 和 30 秒门槛验收。

## 14. 完成定义

只有同时满足以下条件，前端重做才算完成：

- 当前 Demo 使用真实仓库文件并稳定得到 `link:N1-N2`。
- 项目评审者可以不理解内部图 Schema，就判断系统找到了什么、为什么可信、该做什么。
- 界面显示的 Agent 进度和耗时全部来自真实后端事件。
- 输入不足时系统知道停止，正式失败时系统如实降级，用户取消时不污染质量数据。
- 每个诊断运行和案卷可独立审计，人工反馈能形成 Evaluator 可用的真值。
- 视觉、交互和报告共同服务于业务拓扑与诊断结论，不再以技术组件堆叠作为演示主体。
