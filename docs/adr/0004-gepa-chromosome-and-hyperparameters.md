# ADR-0004: GEPA 染色体编码与超参数

**状态**：已接受  
**日期**：2026-07-27  
**决策人**：[姓名]

## 背景

Strategy Optimizer 采用遗传-帕累托（GEPA）框架，根据 Evaluator 的评测反馈自动生成策略提案。需要确定：

1. 染色体编码哪些可变策略元素；
2. 适应度函数如何量化策略优劣；
3. 遗传算法超参数（种群大小、代数、精英比例等）。

## 决策

### GEPAAdapter 子模块

Strategy Optimizer 内部实现 `GEPAAdapter`，负责把染色体接入现有自迭代闭环：

1. **解码染色体**：将 Prompt 哈希、权重、案例视图解码为可部署策略；
2. **部署候选策略**：把解码后的策略临时应用到子 Agent，不覆盖生产配置；
3. **执行回归评测**：在离线回归集/故障注入仿真集上运行完整诊断链路，采集执行轨迹；
4. **计算适应度**：调用 Evaluator 得到多目标指标；
5. **生成文本反馈**：调用 Evaluator 的错误归因与 Critic 排除理由，组装为反射模型输入；
6. **反射变异**：由 Reflection LM 输出定向修订提案，编码为新染色体。

### 染色体编码

基因型为 `<Prompts, Weights, Cases>` 的 JSON 表示：

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
- `prompts` 存模板版本号 + 内容哈希，不存全文；
- `cases.added` 与 `cases.removed` 互斥。

### 适应度函数

多目标向量，在离线回归集上计算：

```
F = [Top1_Acc, Top3_Recall, Critic_Recall, -Critic_False_Reject, -AvgLatency]
```

新候选不被现有候选全面支配则加入帕累托前沿池。

### 反射策略

反射模型（Reflection LM）读取 Evaluator 的错误归因文本与 Critic 的排除理由，决定触发哪个变异算子：

| 错误归因指向 | 触发算子 | 示例 |
|---|---|---|
| 排序偏好错误（如 Coverage 权重过高导致下游告警主导排序） | `MUTATE_WEIGHT` | 降低 Coverage，提升 upstream |
| Few-shot 示例不足、不当或输出格式偏离 | `SWAP_FEW_SHOT` | 替换 Judge/Ranker/Critic 的 few-shot 案例 |
| 缺少相似案例或存在错误案例干扰 | `ADD_CASE` / `REMOVE_CASE` | 加入正确传播模板，移除误导性反例 |
| Prompt 理解偏差、推理步骤错误或输出格式问题 | `REGENERATE_PROMPT` | 重写对应 Agent 的 system prompt |

反射输出为定向修订提案，GEPA 将其编码为染色体变异。

### 超参数

| 参数 | 默认值 |
|---|---|
| 种群大小 | 5 |
| 最大代数 | 10 |
| 精英比例 | 40% |
| 交叉概率 | 0.6 |
| 变异概率 | 0.3 |
| 早停条件 | 连续 3 代前沿无变化 |

### 计算成本估算

每代 5 个染色体 × 离线回归集 500 条 × 单次诊断平均 8 次 LLM 调用 ≈ 20,000 次 LLM 调用/代；完整运行约 20 万次调用。按单次 LLM 调用平均 1–2 秒估算，单次 GEPA 运行可在 4 小时内完成（并行后更短）。

### GEPA 边界

GEPA 仅优化文本化策略参数，不触及以下领域：

| 不适用项 | 说明 | 由谁维护 |
|---|---|---|
| 异构证据图 Schema / 物理拓扑结构 | 图结构来自 CMDB 与人工建模，不是文本参数 | Topology Builder / 人工 SOP |
| LLM / 神经网络权重 | GEPA 不修改模型权重 | 模型提供方或独立微调流程 |
| 实时告警流的在线学习 | GEPA 是离线/准离线优化框架 | 不在本系统范围内 |
| 新设备类型接入规则 | 设备类型、告警码映射等由 SOP 流程维护 | 运维专家 / 数据治理流程 |

违反以上边界会导致优化空间失控，并可能污染生产数据。

## 理由

- **Prompt/Weights/Cases 覆盖主要可调变量**：分别对应 LLM 行为、排序偏好、案例知识三类杠杆。
- **小种群 + 少代数 + 高精英比例**：在 4 小时迭代周期约束下优先快速收敛，避免大量劣质候选消耗评测资源。
- **多目标适应度避免单指标过拟合**：同时优化准确率、召回、Critic 质量与延迟，帕累托前沿提供一组可选策略。

## 后果

### 正面

- 策略迭代周期可控，满足 ≤ 4 小时目标。
- 染色体可审计、可版本化，便于回滚。
- 超参数明确，便于后续做敏感性分析。

### 负面

- 小种群可能陷入局部最优；若核心指标长期停滞，需增大种群或引入更多变异算子。
- Prompt 变异由 LLM 生成，可能产生不可解释或不稳定输出，需人工审批后发布。

## 相关

- `CONTEXT.md` → Agent taxonomy、Key quality targets
- `docs/product/project_prd_refactor.md` → 4.9 Strategy Optimizer (GEPA)
- `docs/adr/0003-critic-gate-with-fallback-limit.md` → Critic 指标进入 GEPA 适应度函数

## 备注

GEPA 输出仅为策略提案，不直接上线。必须经过离线回归、灰度 AB、人工审批（如需）后才能全量发布。
