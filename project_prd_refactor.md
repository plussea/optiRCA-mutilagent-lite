# PRD：面向光网络告警溯源的自迭代多 Agent 系统

**文档版本**：v1.0  
**撰写日期**：2026-07-25  
**产品负责人**：[姓名]  
**技术负责人**：[姓名]  
**状态**：评审中

---

## 1. 项目概述

### 1.1 背景

光网络运维中，单点物理故障（光纤断裂、端口异常）会沿拓扑向下游扩散，引发多层级告警风暴。下游派生告警数量远超根因告警，导致运维人员难以快速定位最小故障源。现有规则阈值、相关性分析、通用 LLM Agent 等方法或因维护成本高、或因缺乏物理约束、或因过程黑盒，无法满足生产环境对可靠性、可审计性、可复盘性的要求。

### 1.2 目标

构建一套**面向光网络告警溯源的自迭代多 Agent 系统**，核心目标：

| 目标 | 指标 | 目标值 | 基线/来源 | 备注 |
|---|---|---|---|---|
| 根因定位准确率 | Top-1 准确率 | ≥ 75%（Phase 1）<br>≥ 85%（生产） | 当前规则基线 ≈ 55% | 基于 8 节点 Demo + 历史故障标注集 |
| 根因定位召回 | Top-K（K=3）召回率 | ≥ 85%（Phase 1）<br>≥ 90%（生产） | — | K=3 覆盖单根因场景；多根因场景见 4.6 |
| Critic 质量 | 伪根因召回率 | ≥ 80% | 无基线 | Critic 成功拦截的伪根因 / 全部伪根因 |
| Critic 质量 | 真根因误拦截率 | ≤ 10% | — | Critic 错误驳回的真根因 / 全部真根因 |
| 推理可审计性 | 全链路结构化留痕率 | 100% | — | 每份案卷包含 5 层结构 |
| 系统迭代效率 | 策略迭代周期 | ≤ 4 小时 | — | 从 Evaluator 发现指标退回到 GEPA 生成新策略提案；不含人工审批与灰度发布 |

### 1.3 范围

**包含**：
- 异构证据图建模与动态构建
- **7 个一级 Agent** 的设计、开发与协作流程
  - 感知层：Alarm Parser、Topology Builder
  - 判断层：Propagation Judge（内部分 Generator + Validator）、Root Cause Ranker（内部分 Scorer + Aggregator）
  - 复核层：Critic Reviewer
  - 归档迭代层：Case Archivist、Evaluator、Strategy Optimizer (GEPA)
- Orchestrator 编排中枢（非推理 Agent）
- 在线诊断主链路（输入 → 输出）
- 反事实复核与质量门控
- 诊断案卷与 GEPA 自迭代闭环

**不包含**：
- 光网络设备侧探针/采集 Agent 开发（假设告警数据已接入）
- 通用 NLP 大模型的预训练（基于现有 LLM API/私有化部署）
- 跨域光网络（如城域-骨干联合，二期规划）

---

## 2. 用户与场景

### 2.1 目标用户

| 角色 | 诉求 |
|---|---|
| NOC 运维工程师 | 快速获得可信的根因结论与处置建议，减少人工排查 |
| 运维专家 | 复盘疑难故障，验证系统推理逻辑，优化策略配置 |
| 算法工程师 | 基于案卷数据与评测反馈，持续优化子 Agent 策略 |

### 2.2 核心场景

**场景 1：光纤断裂告警风暴**  
8 节点拓扑中 B-C 光纤断裂，触发 B/C 端口 LOS、下游设备光功率异常、4 条业务中断。系统需在 30 秒内输出根因报告。

**场景 2：长尾故障首次出现**  
某新型 ROADM 设备在特定温度下产生罕见告警组合，系统无历史案例。系统需通过物理约束推理定位根因，并将正确案例沉淀入库。

**场景 3：策略迭代与灰度发布**  
算法工程师发现某类场景 Top-K 准确率下降，通过 GEPA 生成新策略配置，经离线回归与灰度验证后全量发布。

---

## 3. 系统架构

### 3.1 总体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        数据接入层                            │
│         告警流 (CSV/Kafka) + 拓扑数据 (JSON/CMDB)            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator 编排中枢                     │
│  任务分解 · 调度 · 冲突仲裁 · 超时降级 · 结论组装 · 回退控制    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      异构证据图 (共享黑板)                     │
│     设备 · 端口 · 链路 · 告警 · 业务 (节点 + 边)              │
└─────────────────────────────────────────────────────────────┘
        ↑↓                    ↑↓                    ↑↓
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   感知层      │    │      判断层       │    │    复核层     │
│ Alarm Parser │    │ Propagation Judge│    │ Critic Reviewer│
│Topology Builder│   │ ├─Generator      │   │              │
│              │    │ └─Validator      │   │              │
│              │    │ Root Cause Ranker│   │              │
│              │    │ ├─Feature Scorer │   │              │
│              │    │ └─Rank Aggregator│   │              │
└──────────────┘    └──────────────────┘    └──────────────┘
        ↑↓                    ↑↓                    ↑↓
┌─────────────────────────────────────────────────────────────┐
│                     归档与迭代层                             │
│  Case Archivist · Evaluator · Strategy Optimizer (GEPA)     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                        输出层                                │
│              根因报告 · 证据链 · 处置建议 · 诊断案卷            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 架构要点

1. **Orchestrator 不直接推理**：仅负责任务编排与生命周期管理，诊断推理由子 Agent 完成；
2. **异构证据图 = 共享黑板**：所有子 Agent 通过读写图数据交换中间产物，禁止 Agent 间直接调用；
3. **外层自迭代闭环**：Evaluator 与 Strategy Optimizer 接入评测回归与策略优化，形成外部反馈。

---

## 4. 模块详细设计

### 4.1 Orchestrator 编排中枢

| 项 | 说明 |
|---|---|
| **核心职责** | 任务编排、调度、冲突仲裁、超时降级、结论组装、回退控制 |
| **输入** | 原始告警 + 拓扑 + 业务数据 |
| **输出** | 调度指令 + 最终诊断报告 |
| **负载** | 中 |
| **技术方案** | 状态机引擎（State Machine），管理诊断生命周期 |

**关键行为**：
- 接收输入后，并行触发 Alarm Parser 与 Topology Builder；
- 感知层完成后，按流水线调度 Judge → Ranker → Critic；Ranker 每产出一个 Top-K 候选即可触发 Critic 的轻量复核，但最终结论以全量复核为准；
- 监控各 Agent 超时（如 Judge > 10s 则降级为规则基线）；
- 维护诊断回退计数器，最多允许 2 轮回退；超过则终止自动推理，输出部分结果并标记人工复核；
- 处理 Critic 回退信号，决定重排/补链/人工介入。

### 4.2 Alarm Parser

| 项 | 说明 |
|---|---|
| **核心职责** | 告警字段抽取、标准化、时间窗切分、去噪 |
| **输入** | 原始告警 CSV / Kafka 流 |
| **输出** | 标准告警事实表（JSON Schema） |
| **负载** | 中 |
| **技术方案** | 正则 + LLM 抽取混合，轻量模型 |

**输出 Schema 示例**：
```json
{
  "alarm_id": "ALM-20260725-001",
  "type": "LOS",
  "severity": "Critical",
  "timestamp": "2026-07-25T10:23:45Z",
  "device_id": "OLT-B",
  "port_id": "Port-B1",
  "raw_text": "..."
}
```

### 4.3 Topology Builder

| 项 | 说明 |
|---|---|
| **核心职责** | 拓扑解析、弱拓扑推断、业务路径还原、边置信度计算 |
| **输入** | 拓扑 JSON / CMDB 查询结果 |
| **输出** | 异构证据图（节点 + 边 + 置信度） |
| **负载** | 中高 |
| **技术方案** | 图数据库（Neo4j/NebulaGraph）+ 规则补全 |

**关键行为**：
- 导入静态拓扑，识别孤立节点并标记；
- 对缺失链路做弱拓扑推断（基于同设备端口对推断）；
- 计算拓扑边置信度（如 CMDB 直接录入为 1.0，推断为 0.6）。

### 4.4 Propagation Judge（极高负载，已拆分）

#### 4.4.1 Chain Hypothesis Generator

| 项 | 说明 |
|---|---|
| **核心职责** | 并行生成候选传播链假设 |
| **输入** | 事实表 + 异构证据图 |
| **输出** | 候选传播链列表 `[{root, path, alarms}]` |
| **技术方案** | 多线程 BFS + LLM 局部展开 |

**关键行为**：
- 枚举与告警连通的所有 {设备, 端口, 链路} 作为候选根因；
- 从候选出发沿光信号方向做 2-3 跳局部展开；
- 每条假设独立推理，互不阻塞。

#### 4.4.2 Chain Validator

| 项 | 说明 |
|---|---|
| **核心职责** | 方向、时间、覆盖度三重校验 |
| **输入** | 候选传播链列表 |
| **输出** | 通过校验的传播链 + 淘汰理由 |
| **技术方案** | 规则引擎 + 物理公式计算 |

**校验规则**：
- 方向一致：路径边方向与端口 in/out 属性一致；
- 时间可解：`delta_t = alarm_time - root_time`，`0 <= delta_t <= distance_km / (2e5 km/s) * safety_factor`；
- 覆盖度：`cover >= 20%`。

### 4.5 Root Cause Ranker（极高负载，已拆分）

#### 4.5.1 Feature Scorer

| 项 | 说明 |
|---|---|
| **核心职责** | 并行计算六维特征分 |
| **输入** | 传播链 + 案例库 + 规则库 |
| **输出** | 六维特征向量 `[upstream, time_lead, coverage, priority, case_sim, conflict]` |
| **技术方案** | 图算法（最短路径、子图匹配）+ 向量检索 |

#### 4.5.2 Rank Aggregator

| 项 | 说明 |
|---|---|
| **核心职责** | 加权融合、冲突惩罚、Top-K 输出 |
| **输入** | 六维特征向量列表 |
| **输出** | Top-K 候选 + 评分拆解表 |
| **技术方案** | 加权求和 + 冲突惩罚项 |

**融合公式**：
```
Score = w1*upstream + w2*time_lead + w3*coverage + w4*priority + w5*case_sim - w6*conflict
```

### 4.6 Critic Reviewer

| 项 | 说明 |
|---|---|
| **核心职责** | 反事实挑战、伪根因拦截、复核输出 |
| **输入** | Top-K 候选 + 异构证据图 |
| **输出** | 复核结论（通过/驳回）+ 排除理由 |
| **负载** | 高 |
| **技术方案** | LLM + 图操作（节点移除、连通性检查） |

**反事实挑战清单**：
1. 移除候选根因，检查剩余告警是否可解释；
2. 链路断裂检查双向告警一致性；
3. 检查是否存在多告警簇（遗漏多根因）。

**回退信号**：
- `FALLBACK_TO_RANKER`：要求重排；
- `FALLBACK_TO_JUDGE`：要求对未覆盖子图补链。

### 4.7 Case Archivist

| 项 | 说明 |
|---|---|
| **核心职责** | 案卷归档、案例抽取、传播模板生成 |
| **输入** | 全链路产物 + 人工反馈 |
| **输出** | 标准案卷（Diagnosis Dossier）+ 案例库更新 |
| **负载** | 中 |

**案卷五层结构**：
```json
{
  "input_layer": {...},
  "intermediate_layer": {
    "hypotheses": [...],
    "validation_results": [...],
    "scores": [...],
    "critic_challenges": [...]
  },
  "output_layer": {...},
  "feedback_layer": {...},
  "metadata": {...}
}
```

### 4.8 Evaluator

| 项 | 说明 |
|---|---|
| **核心职责** | 自动化评测、错误归因、回归监控 |
| **输入** | 案卷 + 标注真值 |
| **输出** | 评测报告 + 错误归因文本 |
| **负载** | 中 |

**评测指标**：
- 端到端：Top-1/Top-3 Accuracy、MRR；
- 子 Agent：F1、NDCG、拦截率；
- 回归门禁：核心指标不回退。

### 4.9 Strategy Optimizer (GEPA)

| 项 | 说明 |
|---|---|
| **核心职责** | 策略提案生成、灰度验证、版本迭代 |
| **输入** | 评测报告 + 历史案卷 |
| **输出** | 策略更新提案（Prompt/权重/案例） |
| **负载** | 中高 |
| **技术方案** | GEPA（遗传-帕累托）框架 |

#### 4.9.1 GEPAAdapter 子模块

为将 GEPA 嵌入现有自迭代闭环，Strategy Optimizer 内部实现 `GEPAAdapter`，负责：

1. **解码染色体**：将染色体中的 Prompt 哈希、权重、案例视图解码为可部署策略；
2. **部署候选策略**：把解码后的策略临时应用到子 Agent（不覆盖生产配置）；
3. **执行回归评测**：在离线回归集/故障注入仿真集上运行完整诊断链路，采集执行轨迹；
4. **计算适应度**：调用 Evaluator 得到多目标指标；
5. **生成文本反馈**：调用 Evaluator 的错误归因与 Critic 排除理由，组装为反射模型输入；
6. **反射变异**：由 Reflection LM 输出定向修订提案，编码为新染色体。

伪代码示例：

```python
class OpticalNetworkGEPAAdapter:
    def evaluate(self, candidate, minibatch):
        # 1. 部署候选策略到子 Agent（隔离环境）
        deploy(candidate.prompts, candidate.weights, candidate.cases)
        # 2. 在 minibatch 上运行全链路
        traces = run_pipeline(minibatch)
        # 3. 计算多目标指标
        scores = {
            'top1_acc': evaluator.top1_acc(traces),
            'top3_recall': evaluator.top3_recall(traces),
            'critic_recall': critic.recall(traces),
            'critic_false_reject': critic.false_reject(traces),
            'avg_latency': avg_steps(traces)
        }
        # 4. 生成文本反馈
        feedback = evaluator.error_attribution(traces)
        return scores, feedback
```

#### 4.9.2 染色体编码

基因型为 `<Prompts, Weights, Cases>` 的文本化表示，示例如下：

```json
{
  "prompts": {
    "judge_system": "sha256:...",
    "judge_few_shot_ids": ["case-001", "case-003"],
    "ranker_system": "sha256:...",
    "critic_system": "sha256:..."
  },
  "weights": {
    "upstream": 0.20,
    "time_lead": 0.20,
    "coverage": 0.25,
    "priority": 0.15,
    "case_sim": 0.15,
    "conflict_penalty": 0.05
  },
  "cases": {
    "added": ["case-042"],
    "removed": ["case-007"],
    "retrieval_k": 5
  }
}
```

约束：
- `weights` 各项 ∈ [0, 1] 且总和为 1.0；
- `prompts` 不存全文，存模板版本号 + 内容哈希，便于审计与版本管理；
- `cases.added` 与 `cases.removed` 互斥，同一案例不能同时出现在两列。

#### 4.9.3 变异算子

| 算子 | 作用域 | 说明 |
|---|---|---|
| `MUTATE_WEIGHT` | weights | 高斯扰动后重新归一化 |
| `SWAP_FEW_SHOT` | prompts.few_shot_ids | 从案例库随机替换 1–3 个 few-shot 样本 |
| `ADD_CASE` / `REMOVE_CASE` | cases | 基于 Evaluator 错误归因文本定向增删 |
| `REGENERATE_PROMPT` | prompts.*_system | LLM 基于错误样本重写 system prompt |

#### 4.9.4 适应度函数

多目标向量，在离线回归集上计算：

```
F = [Top1_Acc, Top3_Recall, Critic_Recall, -Critic_False_Reject, -AvgLatency]
```

帕累托前沿：新候选不被现有候选全面支配则加入前沿池。

#### 4.9.5 迭代控制

| 参数 | 默认值 | 说明 |
|---|---|---|
| 种群大小 | 5 | 每代保留 5 个染色体 |
| 最大代数 | 10 | 早停：连续 3 代前沿无变化则停止 |
| 精英比例 | 40% | 每代直接保留前 2 名 |
| 交叉概率 | 0.6 | 仅对 weights 和 cases 做交叉 |
| 变异概率 | 0.3 | 每个算子独立触发 |

**计算成本估算**：每代 5 个染色体 × 离线回归集 500 条 × 单次诊断平均 8 次 LLM 调用 ≈ 20,000 次 LLM 调用/代；完整运行约 20 万次调用。按单次 LLM 调用平均 1–2 秒估算，单次 GEPA 运行可在 4 小时内完成（可并行后更短），满足策略迭代周期目标。

**GEPA 发布流程**：离线回归 → 灰度 AB → 全量/回退。

---

## 5. 数据模型

### 5.1 异构证据图 Schema

**节点属性**：

| 标签 | 必填属性 | 可选属性 |
|---|---|---|
| `:Device` | device_id, type | vendor, location, layer |
| `:Port` | port_id, device_id, direction | rate, status |
| `:Link` | link_id, endpoint_a, endpoint_b | length_km, loss_db |
| `:Alarm` | alarm_id, type, severity, timestamp | port_id, raw_text |
| `:Service` | service_id, path | sla, bandwidth |

**边属性**：

| 类型 | 起始 | 终止 | 属性 |
|---|---|---|---|
| `:BELONGS_TO` | `:Alarm` | `:Port` | confidence=1.0 |
| `:TOPOLOGY` | `:Device`/`:Port` | `:Port`/`:Link` | distance_km, latency_ms, confidence |
| `:PROPAGATES` | `:Port`/`:Link` | `:Alarm` | probability, delay_ms |
| `:CARRIES` | `:Service` | `:Device`/`:Link` | bandwidth_ratio |

### 5.2 诊断案卷 Schema

见 4.7 节案卷五层结构。

---

## 6. 核心流程

### 6.1 在线诊断主链路（时序图）

> 说明：感知层（Parser、Topology）并行执行；Judge → Ranker → Critic 按流水线调度。Ranker 每产出一个 Top-K 候选即可触发 Critic 的轻量复核，但最终结论以全量复核为准。

```
运维人员/系统    Orchestrator    Parser    Topology    Judge    Ranker    Critic    Archivist
     |                |             |          |          |         |         |          |
     |---告警+拓扑---->|             |          |          |         |         |          |
     |                |---并行调度------------------------------------------->|          |
     |                |             |          |          |         |         |          |
     |                |<--事实表-----|          |          |         |         |          |
     |                |<--证据图----------------|          |         |         |          |
     |                |             |          |          |         |         |          |
     |                |---流水线调度 Judge → Ranker → Critic------------------>|          |
     |                |             |          |          |         |         |          |
     |                |<--传播链---------------------------|         |         |          |
     |                |<--Top-K--------------------------------------|         |          |
     |                |<--复核结论----------------------------------------------|          |
     |                |             |          |          |         |         |          |
     |                |[若通过]--------------------------------------------------------->|
     |                |             |          |          |         |         |          |
     |<--根因报告-----|             |          |          |         |         |          |
```

### 6.2 质量门控与回退逻辑

```
Critic 输出
    |
    ├─ 通过 ──→ 质量门控通过 ──→ 输出根因报告
    |
    └─ 驳回 ──→ 检查回退次数
                  |
                  ├─ 次数 < 2 ──→ Orchestrator 决策
                  │                 |
                  │                 ├─ 回退至 Ranker ──→ 扩大 K / 调整权重 ──→ 重新排序
                  │                 |
                  │                 └─ 回退至 Judge ──→ 对未覆盖子图补链 ──→ 重新生成假设
                  │
                  └─ 次数 ≥ 2 ──→ 输出“置信度不足”报告 + 人工介入标记
```

回退终止条件：
- 单次诊断最多允许 **2 轮回退**（含 Ranker 重排与 Judge 补链）；
- 达到上限仍未通过 Critic，则终止自动推理，输出当前最优候选 + 不确定性说明，并标记 `requires_human_review`；
- Orchestrator 记录回退原因，供 Evaluator 与 GEPA 后续分析。

### 6.3 自迭代闭环流程

```
Collect(案卷入库) 
    → Evaluate(Evaluator 全量回归，多目标评分) 
    → Propose(Strategy Optimizer/GEPA 生成变异提案) 
    → Validate(离线回归集，核心指标门禁) 
    → Canary(灰度 AB，对比基线) 
    → Rollout(显著优于基线则全量，否则回退)
```

---

## 7. 接口定义

### 7.1 Agent 间接口（通过共享黑板）

所有 Agent 通过图数据库读写实现间接通信，接口即图 Schema。

### 7.2 系统对外接口

**POST /api/v1/diagnose**
- **请求**：`{"alarms": [...], "topology_id": "topo-001", "timestamp": "..."}`
- **响应**：`{"root_cause": {...}, "evidence_chain": [...], "confidence": 0.92, "dossier_id": "DOS-20260725-001"}`

**GET /api/v1/dossier/{dossier_id}**
- **响应**：完整诊断案卷（五层结构）

**POST /api/v1/feedback**
- **请求**：`{"dossier_id": "...", "ground_truth": {...}, "human_review": "..."}`
- **作用**：触发案卷更新与评测回归

---

## 8. 非功能性需求

| 类别 | 需求 | 方案 | 降级/失败输出 |
|---|---|---|---|
| **性能** | 单次诊断 P99 < 30s | Judge/Ranker 并行化；图数据库索引优化 | 超时后输出规则基线结果 + `degraded=true` 标记 |
| **可靠性** | 单 Agent 失败不影响全局 | Orchestrator 超时降级；失败回退策略 | 失败 Agent 输出空结果或默认值，由 Orchestrator 组装部分报告 |
| **可审计** | 100% 留痕 | Diagnosis Dossier 不可变存储 | — |
| **安全** | 策略迭代不回退核心指标 | 离线回归门禁 + 灰度 AB | 灰度未通过自动回退上一版本策略 |
| **扩展性** | 支持新设备类型接入 | SOP 八要素标准化；Schema 可扩展 | — |

---

## 9. 迭代计划（Roadmap）

### Phase 1：MVP（4 周）
- [ ] Alarm Parser + Topology Builder 跑通
- [ ] 异构证据图基座建立
- [ ] Propagation Judge（单模块）+ Root Cause Ranker（单模块）基础版本
- [ ] 8 节点光纤断裂 Demo 验证

### Phase 2：工程化（4 周）
- [ ] Judge/Ranker 拆分为并行子 Agent
- [ ] Critic Reviewer 反事实复核上线
- [ ] SOP 八要素标准化落地
- [ ] 质量门控与回退机制完善

### Phase 3：闭环（4 周）
- [ ] Diagnosis Dossier 案卷系统上线
- [ ] Evaluator 自动化评测 + 故障注入仿真
- [ ] Strategy Optimizer (GEPA) 接入
- [ ] 灰度发布机制完善

### Phase 4：扩展（后续）
- [ ] 跨域光网络支持
- [ ] 多根因识别能力
- [ ] 生产环境全量上线

---

## 10. 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|---|---|---|---|
| LLM 推理延迟过高 | 诊断超时 | 中 | Judge/Ranker 拆分并行；引入轻量模型降级 |
| 拓扑数据不准确 | 传播链假设错误 | 高 | Topology Builder 弱拓扑推断 + 置信度标记 |
| GEPA 变异产生劣化策略 | 线上指标下降 | 中 | 离线回归门禁 + 灰度 AB 双保险 |
| 长尾故障样本持续稀缺 | 案例知识层迭代受限 | 高 | 故障注入仿真扩充；人工专家标注闭环 |
| 多 Agent 协作冲突 | 结论不一致 | 低 | Orchestrator 冲突仲裁；SOP 契约约束 |

---

## 11. 附录

### 11.1 术语表

| 术语 | 说明 |
|---|---|
| 异构证据图 | 包含设备、端口、链路、告警、业务五类节点与四类边的属性图 |
| 传播链 | 从候选根因到下游告警的拓扑路径与告警子集 |
| 反事实挑战 | 假设候选根因不成立，检验剩余证据是否自洽 |
| GEPA | Genetic-Pareto，遗传-帕累托优化框架 |
| Diagnosis Dossier | 诊断案卷，包含五层全链路留痕数据 |

### 11.2 参考文档

- 系统架构设计文档
- 异构证据图 Schema 详细定义
- 子 Agent Prompt 模板库
- GEPA 框架接入规范

---

**审批记录**

| 版本 | 日期 | 审批人 | 意见 |
|---|---|---|---|
| v0.1 | 2026-07-20 | [姓名] | 初稿 |
| v1.0 | 2026-07-25 | [姓名] | 评审通过，进入开发 |
