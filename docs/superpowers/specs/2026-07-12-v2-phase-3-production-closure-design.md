# Novel Agent v2 Phase 3：生产闭环收尾设计

> 日期：2026-07-12
> 状态：已确认
> 范围：完成 Phase 3 动态剧情规划与写作协作的生产闭环，不进入 Phase 4。

## 1. 目标

本阶段解决当前 Phase 3 已实现但尚未完全交付的问题：

- 规划接口必须使用真实 `DeepSeekWritingGenerator`，测试仍可注入 Fake。
- 统一 DeepSeek、Fake 和服务层之间的结构化协议。
- 将 Phase 3 剧情规划真正接入现有前端写作工作台。
- 完成决策卡、局部修订、作者确认和发布边界的状态闭环。
- 保证 AI 失败、资料变更、过期决策和锁定章节不会产生半成品或错误覆盖。
- 建立确定性测试、真实 AI 集成测试和最终验收门槛。

## 2. 非目标

本阶段不包含：

- 新的完整小说长期大纲生成能力。
- 发布后章节重写或版本回滚。
- 向量检索、复杂 RAG 或多 Agent 并发编排。
- Phase 4 新功能设计。
- 与 Phase 3 无关的全局前端重构。

## 3. 当前基线与关键问题

当前 Phase 3 的确定性后端测试为 30/30，前端单测为 29/29，类型检查和构建通过，但仍有以下缺口：

1. `PlotPlanningService` 默认使用 `FakePhase3WritingGenerator`，生产规划接口没有注入真实生成器。
2. `DeepSeekWritingGenerator.generate_plot_plan()` 返回 `PlotPlanOutput`，而服务层只接受 `dict`。
3. `WritingWorkspaceView.vue` 虽然定义了 Phase 3 handler 并导入 `PlotUnitPanel`，但模板没有渲染它；现有写作请求也没有传递 `plot_plan_revision_id` 和 `author_input`。
4. 决策卡处理使用第一张 pending 卡，无法保证选择的是用户实际点击的卡片。
5. `DraftRevisionDiff` 的应用动作仍是前端占位提示，没有完成候选版本到当前草稿的状态转换。
6. 草稿审查产生叙事冲突时没有完整设置规划阻塞状态。
7. `ConflictOutput.evidence` 是列表，而 `PlanningDecisionOut.evidence_json` 要求字典，真实冲突可能导致 API 响应校验失败。
8. 决策选择没有持久化作者选中的方案或自定义意图。

## 4. 总体架构

采用“后端生产链路 → 前端工作台 → 决策/修订闭环 → 全量验收”的顺序。

### 4.1 后端 AI 入口

`PlotPlanningService` 的默认生成器改为 `DeepSeekWritingGenerator`。构造函数继续保留 `generator` 参数，确定性测试通过该参数注入 `FakePhase3WritingGenerator`。

生产代码不能在 DeepSeek 失败时静默回退到 Fake。AI 失败必须转为明确的失败状态或业务错误。

### 4.2 结构化协议边界

服务层建立统一的协议归一化逻辑：

- `PlotPlanOutput` 转为 `model_dump()` 后保存到 `plan_json`。
- `DraftGenerationOutput`、`DraftReviewOutput` 和 `LocalRevisionOutput` 保持 Pydantic 对象，在业务层读取其字段。
- 任何供应商结果在写数据库前都必须经过 Pydantic 校验。
- 决策证据统一保存为字典：

```json
{
  "items": []
}
```

### 4.3 选择记录

`PlanningDecision` 增加以下可空字段：

- `selected_option_index: int | null`
- `custom_intent: Text | null`

选择方案时只允许二选一：填写 `selected_option_index` 或填写 `custom_intent`。决策进入 `resolved` 时，必须同时保存作者选择和选择时间。

## 5. 后端状态与事务设计

### 5.1 生成计划

计划生成流程为：

```text
读取作者资料、剧情单元和已发布正典
→ 调用 DeepSeek
→ 校验 PlotPlanOutput
→ 转换为 dict
→ 创建 draft 计划版本
```

生成失败时不创建计划记录，不改变当前 active 或 stale 计划。

### 5.2 生成冲突

生成阶段发现冲突时：

- 创建 `PlanningDecision(status="pending")`。
- 关联 `writing_run_id`、`plot_plan_revision_id` 和剧情单元。
- 将相关运行设置为 `planning_blocked=True`、`status="decision_required"`。
- 保存冲突前已生成的未发布正文作为候选内容。
- 将相关计划标记为 `blocked`。

### 5.3 审查冲突

草稿审查发现叙事冲突时，复用生成阶段的冲突归一化器和决策结构：

- 创建相同字段形状的 `PlanningDecision`。
- 将写作运行设置为 `planning_blocked=True`。
- 未接受的运行设置为 `decision_required`；已接受但尚未发布的运行保留 `accepted` 状态并保持阻塞。
- 普通风格、字数和表达问题继续进入 Phase 2 `ReviewIssue`，不创建规划决策。

### 5.4 选择决策与局部修订

`choose_decision()` 的事务顺序为：

1. 加载 pending 决策、关联运行、当前计划、最新候选修订和上下文快照。
2. 校验决策仍然属于当前小说，且没有被资料更新或新计划替代。
3. 校验只能选择一个方案或一个自定义意图。
4. 调用 `generator.revise_draft()`。
5. 校验 `LocalRevisionOutput`、影响范围和 `expanded_scope`。
6. 创建新计划版本，并将旧计划标记为 `superseded`。
7. 创建 `DraftRevision(status="candidate")`，保存父版本、差异和决策来源。
8. 保存作者选择，决策改为 `resolved`。
9. 解除运行的 `planning_blocked`，但不直接把 candidate 当作已应用正文。
10. 一次性提交事务。

AI 调用或任意数据库操作失败时回滚 savepoint，保留 pending 决策、旧 active 计划、原始草稿和旧正典。

候选修订按以下状态转换：

```text
candidate → applied
```

新增 `PUT /novels/{novel_id}/draft-revisions/{revision_id}/apply`，只有未发布运行可以应用候选修订。应用时将同一运行的其他 candidate 标记为 `superseded`，把最新候选内容写回 `WritingRun.draft_content`，并保留锁定章节不变。

### 5.5 发布边界

发布前必须满足：

- 章节不是 `locked`。
- 章节关联运行不存在 `planning_blocked=True`。
- 小说没有与该写作流程相关的 pending 决策。
- 当前草稿已由作者接受。

发布成功后只把章节状态改为 `locked`。之后任何计划、决策、修订和写作接受路径都不能写入或删除该章节。

## 6. 前端工作台设计

### 6.1 状态模型

`usePlotPlanningStore()` 管理：

- `foundation`
- `plotUnits`
- `selectedPlotUnit`
- `planRevisions`
- `activePlan`
- `pendingDecisions`
- `currentDraftRevision`
- `loading`
- `error`

只有 API 成功后才更新 active 计划、决策和候选修订。API 失败时保留之前的本地候选内容。

### 6.2 写作流程接线

`WritingWorkspaceView.vue` 实际渲染 `PlotUnitPanel`，并按以下约束调用现有 API：

- 生成任务书时传递 `plot_plan_revision_id` 和 `author_input`。
- 生成上下文包时传递相同的 `plot_plan_revision_id` 和 `author_input`。
- 创建写作运行时使用相同的 active 计划版本。
- 若没有确认的 active 计划，不允许进入 Phase 3 写作。
- 写作运行进入 `decision_required` 或 `planning_blocked` 时，显示阻塞式决策状态。

### 6.3 决策卡与修订差异

`DecisionCard` 的事件必须携带实际决策 ID：

```ts
choose: [payload: { decisionId: number; optionIndex?: number; customIntent?: string }]
```

界面展示核心冲突、2–3 个方案、AI 推荐和自定义意图输入。默认不展开完整证据链。

`DraftRevisionDiff` 展示服务器返回的 `diff_json`。候选版本未被作者确认前，应用按钮不可用；应用成功后刷新当前运行和修订状态。移除当前没有后端语义的占位“替换”动作，统一使用“应用候选修订”。

### 6.4 锁定编辑器

`WritingEditor.vue` 和 `EditorView.vue` 对 `locked` 章节：

- 标题和正文只读。
- 隐藏保存、删除、发布控件。
- 不允许切换回可编辑状态。

## 7. 错误处理

错误处理遵循以下规则：

- JSON 解析或 Pydantic 校验失败：写作运行进入 `failed`，保存可读错误信息。
- 方案少于两个或无法安全规划：返回 `unsafe_planning`，不创建伪造方案。
- 资料更新后：active 计划标记 `stale`，pending 决策标记 `superseded`，锁定章节和未发布草稿保持不变。
- 过期决策再次选择：返回业务错误，不调用修订 AI。
- 局部修订扩大影响范围：必须保存扩大原因，并在前端展示。
- 跨用户或跨小说资源访问：继续使用现有 404 语义，不泄露资源存在性。
- AI 供应商失败：不回退到 Fake，不创建新的 active 计划，不修改章节正文。

## 8. 测试与验收

### 8.1 后端确定性测试

补充以下测试：

- 默认规划服务使用 DeepSeek 生成器，测试可注入 Fake。
- `PlotPlanOutput` 能正确转换并保存。
- 决策证据通过 `PlanningDecisionOut` 校验。
- 生成冲突和审查冲突都设置规划阻塞。
- 选择方案和自定义意图均会保存作者选择。
- AI 修订失败时旧计划、旧草稿和 pending 决策保持不变。
- candidate 应用后只有最新版本生效。
- 过期决策不能覆盖新计划。
- locked 章节在更新、删除、接受和发布路径均不可修改。

### 8.2 前端测试

补充以下测试：

- `PlotUnitPanel` 实际渲染并触发创建、生成和确认事件。
- 任务书、上下文和写作运行请求带有正确的计划版本 ID。
- 多张决策卡选择对应的实际 decision ID。
- candidate 未应用前不能更新当前草稿。
- locked 编辑器无保存、删除和发布控件。
- API 失败时 Store 保留之前的候选状态。

### 8.3 集成测试

确定性 E2E 场景使用 Fake 生成器验证完整状态流转：

```text
作者资料
→ 剧情单元
→ 计划生成与确认
→ 任务书与上下文
→ 正常草稿
→ 冲突草稿
→ 决策选择
→ candidate 修订
→ 应用修订
→ 接受为 draft
→ 发布为 locked
→ 下一章读取 locked canon
```

真实 DeepSeek 集成测试独立运行，验证：

- 真实生成器返回经过 Pydantic 校验的计划和草稿结构。
- 真实上下文包含作者资料、剧情计划和锁定章节。
- 生产路径不产生 Fake 预置结果。
- 没有 `DEEPSEEK_API_KEY` 时明确跳过，不伪装为通过。

### 8.4 最终命令

```bash
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -q
cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning_integration.py -q
cd backend && .venv/bin/python -m alembic heads
cd frontend && npm run test:unit
cd frontend && npm run type-check
cd frontend && npm run lint
cd frontend && npm run build
```

Phase 3 收尾完成的必要条件是：确定性后端测试、前端测试、类型检查、lint、构建和迁移验证全部通过；真实 AI 测试必须明确记录通过或因缺少密钥跳过。

