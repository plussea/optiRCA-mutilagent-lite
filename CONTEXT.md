# Context: optiRCA-mutilagent-lite

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
- **共享黑板**：异构证据图，所有 Agent 通过读写图数据交换中间产物，禁止 Agent 间直接调用。

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

## Ubiquitous language

| 术语 | 定义 |
|---|---|
| 异构证据图 | 包含 `:Device`、`:Port`、`:Link`、`:Alarm`、`:Service` 五类节点与四类边的属性图 |
| 传播链 | 从候选根因到下游告警的拓扑路径与告警子集 |
| 反事实挑战 | 假设候选根因不成立，检验剩余证据是否自洽 |
| GEPA | Genetic-Pareto，遗传-帕累托优化框架 |
| Diagnosis Dossier | 诊断案卷，包含 input/intermediate/output/feedback/metadata 五层结构 |
| 弱拓扑推断 | 对缺失链路基于同设备端口对等规则补全，并标注置信度（如 0.6） |
| 规则基线 | 超时或 Agent 失败时的降级输出，通常直接上报最高 Severity 告警 |

## ADR index

暂无。后续架构决策按 `docs/adr/NNNN-title.md` 格式沉淀。

## References

- `project_prd_refactor.md` — 产品需求与模块详细设计
- `docs/agents/domain.md` — Agent 如何消费领域文档
- `docs/agents/issue-tracker.md` — 问题追踪流程
