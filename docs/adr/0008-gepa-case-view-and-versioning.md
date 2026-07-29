# ADR-0008: GEPA 染色体中的案例视图与案例库版本管理

**状态**：已接受  
**日期**：2026-07-27  
**决策人**：[姓名]

## 背景

GEPA 染色体中的 `cases` 段控制 Ranker 在计算 `case_sim` 特征时使用哪些案例。需要明确：

1. `added`/`removed` 是物理变更全局案例库，还是仅影响当前染色体的检索视图；
2. 案例库是否版本化，染色体如何引用历史案例；
3. `retrieval_k` 的作用范围。

## 决策

### `cases.added` 与 `cases.removed` 是逻辑视图操作

- `added`：将指定案例加入当前染色体的检索视图，**不修改全局案例库**。新增案例必须来自候选池（如人工标注正确案卷、Evaluator 确认的高分案卷）。
- `removed`：将指定案例从当前染色体的检索视图中**逻辑排除**，**不物理删除**。全局案例库中仍然存在该案例，其他染色体可继续引用。

### 全局案例库不可变追加

- 案例库为 **append-only**，每个案例写入后不可修改，只能标记为 `deprecated`。
- 每个案例包含 `case_id` 与 `case_version`。
- 染色体默认引用最新版本：`"case-007"` 等价于 `"case-007@latest"`。
- 如需锁定版本，使用 `"case-007@v3"` 格式。

### `retrieval_k` 作用范围

- `retrieval_k` 当前仅用于 **Ranker 的 `case_sim` 特征检索**。
- 若未来 Judge 或 Critic 也需要案例检索，各自在染色体中独立配置字段（如 `judge_retrieval_k`、`critic_retrieval_k`），不共享 `retrieval_k`。

## 理由

- **避免 GEPA 破坏共享知识**：染色体变异不应物理删除或污染全局案例库，防止劣质策略导致历史正确案例丢失。
- **可复现**：锁定版本后，历史染色体可在任意时刻复现其策略行为。
- **最小职责**：`retrieval_k` 仅绑定 Ranker，避免一个参数隐性影响多个 Agent。

## 后果

### 正面

- 多个 GEPA 运行可并发试验不同案例视图，互不干扰。
- 案例库历史完整，便于错误归因和审计。
- 染色体可审计、可回滚。

### 负面

- 案例库持续增长，需要定期归档 `deprecated` 案例或压缩旧版本。
- 染色体引用 `case_id@latest` 时，全局库追加新版本可能导致策略行为漂移。

## 相关

- `CONTEXT.md` → Ubiquitous language（GEPA、Diagnosis Dossier）
- `project_prd_refactor.md` → 4.9.1 染色体编码
- `docs/adr/0004-gepa-chromosome-and-hyperparameters.md` → 染色体整体结构

## 备注

建议上线后默认使用锁定版本引用，避免 `latest` 漂移；仅在人工确认案例更新时允许染色体升级到新版案例。
