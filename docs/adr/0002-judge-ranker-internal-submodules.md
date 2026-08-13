# ADR-0002: Propagation Judge 与 Root Cause Ranker 作为一级 Agent，内部拆分子模块

**状态**：已接受  
**日期**：2026-07-27  
**决策人**：[姓名]

## 背景

Propagation Judge 与 Root Cause Ranker 是诊断链路中负载最高的两个环节。为提升吞吐，两者内部都需要并行化：

- Judge 需并行生成并校验大量候选传播链；
- Ranker 需并行计算多个候选的多维特征分。

存在两种拆分策略：

1. **拆分为独立 Agent**：Judge 拆成 Generator Agent + Validator Agent；Ranker 拆成 Scorer Agent + Aggregator Agent。
2. **保持一级 Agent，内部拆分子模块**：Generator/Validator/Scorer/Aggregator 作为同一 Agent 内的组件，不独立对外。

## 决策

保持 **Propagation Judge** 与 **Root Cause Ranker** 为一级 Agent，其内部子模块仅用于并行计算，不单独作为 Agent 暴露。

## 理由

- **语义边界清晰**：Judge 负责“生成并校验传播链”，Ranker 负责“打分并排序”。这两个职责对外是完整的，内部拆分属于实现优化。
- **避免 Orchestrator 调度爆炸**：若子模块独立为 Agent，Orchestrator 需管理 11 个以上节点，增加调度复杂度和超时回退成本。
- **共享状态更高效**：子模块在同一进程/容器内可通过内存共享中间结果，无需经过共享黑板反复序列化。
- **监控可聚合**：对外汇报时，Judge/Ranker 各有一个延迟/成功率指标，便于建立端到端 SLO。

## 后果

### 正面

- Orchestrator 生命周期仍围绕 7 个一级 Agent 管理，状态机简单。
- Judge/Ranker 可独立扩展副本，内部子模块自动随副本并行。
- 日志链路以 Agent 为单位，便于追踪单次诊断中的完整推理阶段。

### 负面

- 子模块无法独立部署或独立灰度升级；Judge/Ranker 任一子模块变更需整体发布。
- 子模块间错误可能相互影响，需通过进程内异常隔离或熔断机制缓解。

## 相关

- `CONTEXT.md` → Agent taxonomy
- `docs/product/project_prd_refactor.md` → 4.4、4.5 模块详细设计
- `docs/adr/0001-shared-blackboard-over-direct-calls.md` → 共享黑板约束不适用于同一 Agent 内部的子模块通信

## 备注

若未来 Judge/Ranker 内部子模块需要异构扩缩容（如 Generator 需要 GPU，Validator 不需要），可重新评估拆分为独立 Agent。
