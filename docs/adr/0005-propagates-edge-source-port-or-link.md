# ADR-0005: `:PROPAGATES` 边起点为 `:Port` 或 `:Link`

**状态**：已接受  
**日期**：2026-07-27  
**决策人**：[姓名]

## 背景

异构证据图需要表达“根因如何引发告警”的传播关系。`:PROPAGATES` 边的起点可以是：

1. `:Device`/`:Link` → `:Alarm`（较粗粒度，设备或链路直接产生告警）；
2. `:Port`/`:Link` → `:Alarm`（较细粒度，告警归属于具体端口或链路）。

## 决策

`:PROPAGATES` 边起点限定为 **`:Port`** 或 **`:Link`**，不直接从 `:Device` 引出。

## 理由

- **告警在光网络中最小可定位单元是端口或链路**：端口 LOS、光功率异常、链路断裂都有明确的物理位置。Device 级告警（如设备掉电）应通过 `:BELONGS_TO` 关联到 `:Port` 或 `:Device`，再由具体端口/链路传播。
- **传播链计算更精确**：从 Port/Link 出发沿拓扑展开，方向、时间、覆盖度校验都更有物理意义。
- **Critic 反事实挑战更可靠**：移除候选 Port/Link 后，可直接检查剩余告警是否自洽；若从 Device 出发，移除范围模糊。

## 后果

### 正面

- 图 Schema 与光网络物理层级一致，降低领域专家理解成本。
- Generator 枚举候选根因时只需遍历 Port 与 Link，减少搜索空间。
- Validator 的时间/方向校验可直接使用 Port/Link 属性。

### 负面

- 原始告警若只含 Device ID，需 Parser 或 Topology Builder 补充到 Port 层级。
- 少量 Device 级故障（如整机掉电）需要多 Port 同时标记为根因，增加建模复杂度。

## 相关

- `CONTEXT.md` → Ubiquitous language（异构证据图、传播链）
- `docs/product/project_prd_refactor.md` → 5.1 异构证据图 Schema
- `docs/adr/0001-shared-blackboard-over-direct-calls.md` → 共享黑板 Schema 变更影响所有 Agent

## 备注

若后续出现只能从 Device 层面解释的全局故障，可新增 `:DEVICE_LEVEL_ROOT` 标签或允许 `:Device` 通过 `:BELONGS_TO` 关联多个 `:Port` 作为复合根因，但不改变 `:PROPAGATES` 边的起点规则。
