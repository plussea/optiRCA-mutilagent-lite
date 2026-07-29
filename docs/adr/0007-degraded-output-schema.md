# ADR-0007: 诊断降级输出形态

**状态**：已接受  
**日期**：2026-07-27  
**决策人**：[姓名]

## 背景

系统承诺 P99 < 30s 且单 Agent 失败不影响全局，因此必须定义清晰的降级输出。否则 Orchestrator 在不同失败路径下会返回不一致的响应，导致上游调用方无法正确处理。

## 决策

### 规则基线

当性能超时或关键 Agent 失败时，采用规则基线输出：

- 优先选择告警集中 **时间最早且拓扑最上游** 的 `:Alarm` 节点作为根因；
- 若无法判断上游，则选择 **Severity 最高** 的告警；
- 若仍无法确定，返回空根因并标记 `requires_human_review`。

### 响应状态

正常响应：

```json
{
  "status": "success",
  "root_cause": {...},
  "evidence_chain": [...],
  "confidence": 0.92,
  "dossier_id": "DOS-20260725-001",
  "suggestion": "...",
  "requires_human_review": false
}
```

降级响应：

```json
{
  "status": "degraded",
  "root_cause": {...},
  "evidence_chain": [...],
  "confidence": 0.0,
  "dossier_id": "DOS-20260725-001",
  "suggestion": "自动推理降级，请人工复核拓扑与告警时间线。",
  "requires_human_review": true,
  "degradation_reason": "judge_timeout"
}
```

### 缺失字段填充规则

| 字段 | 降级时填充规则 |
|---|---|
| `root_cause` | 按规则基线填充；无法确定时为空对象 |
| `evidence_chain` | 填充到已完成的 Agent 阶段，未执行阶段为空数组 |
| `confidence` | 固定为 `0.0`，禁止给出虚假高置信度 |
| `suggestion` | 输出通用人工复核建议；若能提供部分建议则补充 |
| `requires_human_review` | 降级输出统一为 `true` |
| `degradation_reason` | 必填，枚举值：`judge_timeout`、`ranker_timeout`、`critic_timeout`、`agent_failure`、`max_fallback_exceeded` |

### 人工介入标记

统一使用字段名 **`requires_human_review`**。触发场景：

- 任意降级输出；
- Critic 2 轮回退后仍未通过；
- 用户显式请求人工复核。

## 理由

- **调用方可预期**：`status` 字段明确区分成功与降级，便于 SLA 统计与告警路由。
- **避免虚假置信度**：降级时 `confidence = 0.0`，防止运维人员误信低质量结论。
- **统一人工入口**：单一字段 `requires_human_review` 驱动后续工单/告警工作流。
- **规则基线有物理意义**：时间最早 + 拓扑最上游与多数单点故障模式一致，是合理的保守猜测。

## 后果

### 正面

- Orchestrator 输出一致性提升。
- 监控与告警规则可直接基于 `status` 和 `degradation_reason`。
- 案卷系统可完整记录降级路径，供 GEPA 优化。

### 负面

- 规则基线可能在多根因场景下给出错误引导，需配套人工复核 SLA。
- 部分 Agent 失败时组装部分报告，可能让下游误以为证据链完整。

## 相关

- `CONTEXT.md` → Ubiquitous language（规则基线）
- `project_prd_refactor.md` → 4.1 Orchestrator、6.2 回退逻辑、8 非功能性需求
- `docs/adr/0003-critic-gate-with-fallback-limit.md` → `max_fallback_exceeded` 降级原因
- `docs/adr/0006-pipeline-light-review-boundary.md` → Critic 超时降级原因

## 备注

规则基线未来可被 GEPA 优化为“轻量专家规则集”，但当前版本保持简单可解释，避免引入新的黑盒。
