# 文档中心

这里集中存放 OptiRCA Lite 的产品、架构、实施和研究文档。项目根目录仅保留日常入口 `README.md`、Agent 约定 `AGENTS.md` 和领域上下文 `CONTEXT.md`。

## 产品需求

- [`product/project_prd_refactor.md`](product/project_prd_refactor.md)：多 Agent 根因诊断系统主 PRD。
- [`product/prd_frontend_advanced_ui.md`](product/prd_frontend_advanced_ui.md)：高级诊断工作台前端 PRD。

## 技术规格

- [`specs/diagnosis-workbench-implementation-spec.md`](specs/diagnosis-workbench-implementation-spec.md)：诊断工作台实施规格。
- [`specs/playback_event_contract.md`](specs/playback_event_contract.md)：回放事件契约。
- [`specs/spec_prd_refactor.md`](specs/spec_prd_refactor.md)：异构证据图多 Agent 重构规格。
- [`specs/spec_gepa_optimizer.md`](specs/spec_gepa_optimizer.md)：GEPA、Evaluator 与 Case Archivist 规格。

## 架构与协作约定

- [`adr/`](adr/)：架构决策记录。
- [`agents/domain.md`](agents/domain.md)：领域文档维护约定。
- [`agents/issue-tracker.md`](agents/issue-tracker.md)：GitHub Issue 工作流。
- [`agents/triage-labels.md`](agents/triage-labels.md)：Issue 分诊标签。

## 研究材料

- [`research/research_idea_brief_srro.md`](research/research_idea_brief_srro.md)：SRRO 研究方案。
- [`figures/srro_planning/`](figures/srro_planning/)：SRRO 规划图及导出版本。
- [`references/`](references/)：历史参考稿和外部方法笔记，不作为当前需求基线。

## Issue 快照

[`issues/`](issues/) 保存已从 GitHub Issue 导出的实施快照，仅用于追溯。本项目正式 Issue 状态以 GitHub 为准。

## 文档放置规则

- 产品范围、用户流程和验收目标放入 `product/`。
- API、事件契约和实现方案放入 `specs/`。
- 跨模块架构决策放入 `adr/`。
- 研究方案放入 `research/`，生成图放入 `figures/`。
- 参考资料放入 `references/`，不要与当前 PRD 混放。
