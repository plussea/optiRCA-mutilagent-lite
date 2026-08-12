# Context: optiRCA Lite

## Domain overview

光网络告警溯源系统。输入为告警流与拓扑数据，输出为根因报告、证据链、处置建议与诊断案卷。核心挑战：单点物理故障沿拓扑向下游扩散，形成告警风暴，派生告警数量远超根因告警。

## Agent taxonomy

系统由 **7 个一级 Agent** 与 **1 个编排中枢** 组成。编排中枢不直接推理。

| 层级 | Agent | 内部子模块（如有） | 职责 |
|---|---|---|---|
| 感知层 | Alarm Parser | — | 告警字段抽取、标准化、时间窗切分、去噪 |
| 感知层 | Topology Builder | — | 拓扑解析、弱拓扑推断、业务路径还原、边置信度计算 |
| 判断层 | Propagation Judge | Chain Hypothesis Generator、Chain Validator | 生成并校验候选传播链 |
| 判断层 | Root Cause Ranker | Feature Scorer、Rank Aggregator | 特征打分与候选根因排序 |
| 复核层 | Critic Reviewer | — | 反事实挑战、伪根因拦截 |
| 归档迭代层 | Case Archivist | — | 案卷归档、案例抽取、传播模板生成 |
| 归档迭代层 | Evaluator | — | 自动化评测、错误归因、回归监控 |
| 归档迭代层 | Strategy Optimizer (GEPA) | — | 策略提案生成、灰度验证、版本迭代 |
| 编排中枢 | Orchestrator | — | 任务编排、调度、冲突仲裁、超时降级、结论组装、回退控制 |

术语约定：
- **Agent**：具独立输入输出、可独立部署或调度的逻辑单元。
- **子模块**：同一 Agent 内部的并行或串行组件，不单独对外暴露接口。
- **共享黑板**：单个诊断运行内的异构证据图，所有 Agent 通过读写该运行的图数据交换中间产物，禁止 Agent 间直接调用；不同诊断运行之间不得共享可变图状态。

## Key quality targets

| 指标 | Phase 1 | 生产 |
|---|---|---|
| Top-1 准确率 | ≥ 75% | ≥ 85% |
| Top-3 召回率 | ≥ 85% | ≥ 90% |
| Critic 伪根因召回率 | ≥ 80% | ≥ 80% |
| Critic 真根因误拦截率 | ≤ 10% | ≤ 10% |
| 全链路结构化留痕率 | 100% | 100% |
| 策略迭代周期（Evaluator 发现 → GEPA 提案） | ≤ 4h | ≤ 4h |

基线：当前规则基线 Top-1 准确率 ≈ 55%。

## Core decisions

1. **Agent 间禁止直接调用，统一通过异构证据图通信。**
2. **Judge/Ranker 内部拆分以支持并行化，但仍视为一级 Agent。**
3. **Critic 输出必须包含复核结论与排除理由；Orchestrator 最多允许 2 轮回退。**
4. **GEPA 染色体编码为 `<Prompts, Weights, Cases>`；默认种群大小 5，最大代数 10，精英比例 40%。**
5. **`:PROPAGATES` 边起点为 `:Port`/`:Link`，告警不直接从 `:Device` 传播。**
6. **诊断案卷采用五层结构：input_layer、intermediate_layer、output_layer、feedback_layer、metadata。**
7. **所有诊断结果（成功或降级）均归档为案卷，人工审核闭环更新 feedback_layer。**

## API seams

| 端点 | 用途 |
|---|---|
| `POST /api/v1/diagnose` | 端到端诊断主入口 |
| `GET /v1/dossier/{dossier_id}` | 获取完整诊断案卷 |
| `POST /v1/evaluate` | 离线回归评测 |
| `GET /v1/evaluate/{evaluation_id}` | 获取评测报告 |
| `POST /v1/gepa` | 策略优化提案 |
| `GET /v1/gepa/{optimization_id}` | 获取 GEPA 报告 |
| `POST /v1/refactor/parse` | 感知层 seam |
| `POST /v1/refactor/judge-rank` | Judge + Ranker seam |
| `POST /v1/refactor/critic` | Critic seam |
| `POST /v1/sessions/{id}/human-decision` | 人工审核闭环 |

## Ubiquitous language

| 术语 | 定义 |
|---|---|
| 异构证据图 | 包含 `:Device`、`:Port`、`:Link`、`:Alarm`、`:Service` 五类节点与四类边的属性图 |
| 传播链 | 从候选根因到下游告警的拓扑路径与告警子集 |
| 反事实挑战 | 假设候选根因不成立，检验剩余证据是否自洽 |
| GEPA | Genetic-Pareto，遗传-帕累托优化框架 |
| Diagnosis Dossier | 诊断案卷，包含 input/intermediate/output/feedback/metadata 五层结构 |
| 弱拓扑推断 | 对缺失拓扑关系按可审计规则进行补全，并标注置信度与推断依据；业务拓扑视图以虚线呈现推断关系、实线呈现用户提供的权威关系，后者可替换前者并触发重新预检 |
| 规则基线 | 超时或 Agent 失败时的降级输出，通常直接上报最高 Severity 告警 |
| 染色体 | GEPA 策略编码 `<Prompts, Weights, Cases>` |
| 项目评审者 | 具备光网络业务理解、负责判断系统业务价值与诊断可信度的演示第一受众；不以执行日常告警处置或调试 Agent 为主要任务 |
| 诊断样本 | 一次根因诊断的输入单元，必须包含一份告警 CSV，可选包含一份拓扑 JSON；未提供拓扑时仅适用于系统能够从告警信息推断拓扑的简单场景 |
| 拓扑预检 | 正式诊断前，系统根据告警 CSV 中的设备、端口与链路标识判断能否形成唯一可用的推断拓扑；无法可靠推断时必须阻止正式诊断并要求用户补充拓扑 JSON，不允许用户绕过，也不让用户手动选择场景复杂度 |
| 业务拓扑视图 | 面向项目评审者的主要诊断视图，默认按设备与物理链路聚合，呈现根因链路、直接告警节点、受影响节点与正常节点；端口、单条告警和异构证据关系仅在选中对象后下钻，不承担主叙事 |
| 诊断结论卡 | 诊断完成后的首要信息摘要，只呈现根因、可信度、告警收敛解释与建议动作；候选排序、Critic 结果、案卷标识和 Agent 日志属于下钻详情 |
| 轻量审核闭环 | 针对所有正式诊断结果的人工反馈：确认根因、标记结论错误或请求专家复核，可附简短意见，并写回诊断案卷；成功结果可选审核，降级结果必须突出审核，不包含工单流转、审核队列或权限系统 |
| 诊断视觉语义 | 面向项目评审者的克制型业务配色：红色表示根因或严重告警，橙色表示受影响或待审核，绿色表示正常或审核通过，青蓝表示系统推理或选中状态；装饰效果不得改变这些含义 |
| 推理过程摘要 | 多 Agent 执行过程的评审者视图：诊断中展示真实阶段、阶段产物与实际耗时，完成后收缩为阶段数、总耗时和 Critic 结论；候选评分、挑战与日志仅在下钻时展开 |
| 输入未就绪 | 拓扑预检未通过的样本状态；系统可展示已解析事实、歧义与缺失项，但不得开始正式诊断、生成诊断案卷或计入诊断质量统计 |
| 单页诊断工作台 | 单个诊断样本从输入准备、正式诊断到结果查看的连续界面；三个状态在同一页面内转换，开始新样本时才清空当前结果 |
| 诊断报告 | 面向项目评审与复盘的单次诊断可导出快照，包含输入摘要、业务拓扑与传播路径、诊断结论、推理过程摘要、Critic 结论、人工审核状态、案卷标识和时间；审核前标记“未经人工确认”，确认后记录审核时间，错误案例同时保留系统预测与人工真值，降级案例标记“自动诊断未完成”；不承担在线分享或协作功能 |
| 降级诊断 | 拓扑预检通过且正式诊断已开始后，因 Agent 失败、超时或回退耗尽而未形成完整自动结论的结果；保留案卷、已完成阶段与部分证据，规则候选仅作为人工复核线索，不称为最终根因 |
| 人工真值 | 经人工审核确认的正确根因物理对象：确认系统结论时取当前根因，标记结论错误时必须另选设备、端口或链路，请求专家复核时不产生真值；写入诊断案卷供 Evaluator 使用 |
| 可信度检查 | Critic Reviewer 面向项目评审者的业务解释，包括告警解释完整性、链路两端一致性与单一故障合理性；界面必须展示各项结果和失败后的回退动作，而非只显示 `pass` 或 `reject` |
| 取消诊断 | 用户在正式诊断完成前主动终止当前运行；系统停止后续 Agent 调度、保留上传输入和已产生的阶段事件，但不生成正式诊断案卷，也不计为系统失败 |
| 诊断运行 | 一个输入就绪的诊断样本触发的一次独立正式执行，对应唯一 session；修改 CSV 或拓扑后重试必须创建新的诊断运行和案卷，既有案卷不可覆盖，工作台只展示当前最新运行 |
| 评审界面语言 | 面向项目评审者的界面以中文业务术语表达结论、动作、状态与错误；英文 Agent 名称仅作为辅助技术标签，不替代业务含义 |
| 诊断摘要 | 由当前诊断运行动态生成的一句话业务结论，说明告警规模、异常设备范围、实际耗时、收敛后的根因数量或对象、告警解释覆盖率与可信度检查结果；任何样本数字均不得硬编码 |
| 示例验收 | 使用仓库内真实示例文件执行与普通上传相同的诊断链路，并将实际结果与示例预期真值比较；结果不一致时必须如实展示并标记验收失败，不得伪造成功结论或使用成功样式 |
| 样本预期 | 仓库内开发测试样本可附带的 `expected.json`，至少声明预期根因，并可声明预期影响对象与最低告警覆盖率；只供自动测试和示例验收使用，禁止进入 Agent 诊断输入或推理上下文 |

## ADR index

- ADR-0001：共享黑板（异构证据图）作为 Agent 间唯一通信方式
- ADR-0002：Propagation Judge 与 Root Cause Ranker 作为一级 Agent，内部拆分子模块
- ADR-0003：Critic 质量门控与回退终止策略
- ADR-0004：GEPA 染色体编码与超参数
- ADR-0005：`:PROPAGATES` 边起点为 `:Port` 或 `:Link`
- ADR-0006：Ranker → Critic 流水线中的轻量复核边界
- ADR-0007：诊断降级输出形态
- ADR-0008：GEPA 染色体中的案例视图与案例库版本管理
- ADR-0009：拓扑预检作为正式诊断硬门禁
- ADR-0010：异步诊断运行与 SSE 事件流
- ADR-0011：异构证据图按诊断运行隔离
- ADR-0012：首版诊断限定为单根因场景

## Current status (2026-08-04)

重构主线 #9-#13 已完成：
- #9：LangGraph 统一编排 workflow (`perception → topology → judge → rank → critic → assemble`)
- #10：Critic 三挑战清单（unexplained alarms、bidirectional LOS、multi-cluster）
- #11：Case Archivist 五层案卷 + 向量模板索引
- #12：Evaluator 离线回归指标 + 错误归因
- #13：GEPA Strategy Optimizer Pareto 前沿与推荐策略

剩余方向：
- Judge/Ranker 内部子模块拆分（Generator/Validator、Feature Scorer/Aggregator）。
- Topology Builder 弱拓扑推断与边置信度。
- Judge/Critic 引入 LLM 增强推理并保留规则回退。
- 故障注入仿真与灰度发布机制。

## References

- `project_prd_refactor.md` — 产品需求与模块详细设计
- `spec_prd_refactor.md` — 重构 Spec 与测试 seams
- `spec_gepa_optimizer.md` — GEPA/Evaluator/Archivist 详细 Spec
- `docs/agents/domain.md` — Agent 如何消费领域文档
- `docs/agents/issue-tracker.md` — 问题追踪流程
