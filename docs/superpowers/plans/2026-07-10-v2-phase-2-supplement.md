# V2 Phase 2 补充实施计划

> 本文只补充和验证 Phase 2。Phase 3 不在本计划中实现，必须先重新讨论目标、AI 数据流、数据模型和验收标准，再单独形成设计文档与实施计划。

**目标：** 在保留现有单章自主写作闭环的基础上，补齐 Phase 2 的真实质量门禁、修复执行、正文确认后的记忆候选回写，并用端到端测试证明链路可用。

**当前边界：** 本计划不新增卷规划、计划版本、主线推进表、角色成长线、伏笔规划 API 或规划工作台。不得以 CRUD、页面展示或测试通过替代 AI 规划能力的完成证明。

## 全局约束

- 所有 AI 生成结果必须明确经过真实模型调用、结构化解析和持久化，测试可通过依赖注入使用 fake provider。
- 所有自动质量检查结果必须可追溯到 `WritingRun`；客观修复写入 `RepairLog`，需要作者意图的问题写入 `PendingRepair`。
- 正式章节正文和正式长期记忆仍需作者确认。
- 接受草稿后只生成 `PendingMemory` 候选，不直接写入正式记忆。
- 所有接口继续挂在 `/api/v1/novels/{novel_id}/` 下，并验证小说所有权。
- 不引入任何 Phase 3 的规划实体或 API。

---

## Task 1：确认真实质量门禁契约和默认调用链

**Files:**

- 检查/修改：`backend/app/ai/quality_gate.py`
- 检查/修改：`backend/app/ai/quality_agents.py`
- 检查/修改：`backend/app/services/quality_gate_service.py`
- 检查/修改：`backend/app/models/quality_gate.py`
- 检查/修改：`backend/app/repositories/quality_gate_repo.py`
- Test: `backend/tests/test_phase_2_quality_gate.py`

**必须证明：**

- 生产默认路径使用 `DeepSeekQualityGateAgent`，不是 `FakeQualityGateAgent`。
- 每个检查维度都经过模型调用、JSON 解析和 `CheckResult` 校验。
- 模型调用失败或结构化解析失败时，草稿可保留，但 `gated=False` 且有明确错误信息。
- `ReviewIssue` 归属于质量门禁，不依赖任何 Phase 3 模型。

- [ ] **Step 1：补充失败测试**

  测试默认 service 使用真实 Agent 类型；测试模型返回一个 `auto_fixable` 问题和一个 `needs_intent` 问题时，分别产生 `ReviewIssue`、`RepairLog` 和 `PendingRepair`。

- [ ] **Step 2：验证真实调用边界**

  为 DeepSeek Agent 注入最小 fake model，断言收到的 prompt 包含正文、章节任务书、上下文包和对应质量标准，并断言返回值经过 Pydantic 校验。

- [ ] **Step 3：补齐错误路径**

  对 provider 异常、空响应、非法 JSON、字段缺失分别返回稳定的失败结果；禁止静默变成“全部通过”。

- [ ] **Step 4：运行测试**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

## Task 2：完成待处理修复的真实执行

**Files:**

- 检查/修改：`backend/app/ai/writer.py`
- 检查/修改：`backend/app/services/repair_service.py`
- 检查/修改：`backend/app/api/writing.py`
- 检查/修改：`frontend/src/stores/writing.ts`
- 检查/修改：`frontend/src/components/editor/RepairItem.vue`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Test: `frontend/src/__tests__/WritingEditor.spec.ts`

**必须证明：**

- `apply` 会基于作者选择或作者意图调用 `rewrite_fragment`。
- 正文内容更新后会记录新的 `RepairLog`。
- `dismiss` 不修改正文。
- 跨小说、重复处理、非法选项和修复失败都不会污染原草稿。

- [ ] **Step 1：补充 API 失败测试**

  覆盖 choice、freeform、dismiss、重复 resolve、跨用户访问和模型修复失败。

- [ ] **Step 2：确认事务边界**

  修复成功时一次性保存正文、日志和状态；修复失败时回滚正文并保留 `PendingRepair.status = "pending"`。

- [ ] **Step 3：验证编辑器状态**

  前端处理后重新加载 WritingRun 和修复列表，不使用本地假状态冒充服务端结果。

- [ ] **Step 4：运行测试**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py -x -q`

  Run: `npm run test:unit -- src/__tests__/WritingEditor.spec.ts`

## Task 3：补齐正文确认后的记忆候选回写

**Files:**

- 检查/修改：`backend/app/services/writing_service.py`
- 检查/修改：`backend/app/ai/service.py`
- 检查/修改：`backend/app/api/writing.py`
- 检查/修改：`frontend/src/views/novels/WritingWorkspaceView.vue`
- 检查/修改：`frontend/src/stores/pendingMemory.ts`
- Test: `backend/tests/test_phase_2_quality_gate.py`
- Test: `backend/tests/test_phase_2_ai_extract.py`

**必须证明：**

- 接受新草稿并创建章节后，使用新章节 ID 调用真实提取服务。
- 覆盖已有章节时，使用已有章节 ID 调用提取服务。
- 提取结果进入 `PendingMemory`，不会直接写入正式角色、设定、剧情事实或伏笔。
- 提取失败不会回滚已经接受的正文，但必须向调用方返回可追踪错误。

- [ ] **Step 1：写接受到记忆的失败测试**

  使用注入的 extraction fake，断言调用次数、章节 ID、pending 数量和失败行为。

- [ ] **Step 2：验证提交顺序**

  先确保章节正文和 WritingRun 状态持久化，再执行记忆提取；不得因为提取服务失败导致已接受正文丢失。

- [ ] **Step 3：验证前端交接**

  接受成功后显示待确认记忆数量，并能进入 PendingMemory 页面继续确认或拒绝。

- [ ] **Step 4：运行测试**

  Run: `.venv/bin/python -m pytest tests/test_phase_2_quality_gate.py tests/test_phase_2_ai_extract.py -x -q`

## Task 4：端到端验收和真实调用审计

**Files:**

- Create: `backend/tests/test_phase_2_end_to_end.py`
- 检查/修改：`backend/tests/test_phase_2_quality_gate.py`
- 检查/修改：`backend/tests/test_phase_1_writing_integration.py`
- 检查/修改：`frontend/e2e/vue.spec.ts`
- 检查：`backend/app/ai/quality_agents.py`
- 检查：`backend/app/ai/writer.py`
- 检查：`backend/app/ai/service.py`

**验收链路：**

```text
作者输入构思
→ AI 生成蓝图
→ AI 生成章节计划和任务书
→ AI 生成正文草稿
→ 真实质量门禁
→ 自动修复或作者处理
→ 作者接受正文
→ AI 提取 PendingMemory
→ 作者确认记忆
```

- [ ] **Step 1：为每个 AI 边界添加调用断言**

  测试必须验证 provider 被调用、输入包含业务上下文、输出被保存；只验证数据库中出现一行固定字符串不算通过。

- [ ] **Step 2：运行后端完整测试**

  Run: `.venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 3：运行前端验证**

  Run: `npm run type-check`

  Run: `npm run test:unit`

  Run: `npm run build`

- [ ] **Step 4：更新需求基线**

  只有端到端链路和真实调用审计通过后，才更新项目文档中的 Phase 2 状态。Phase 3 状态保持“待讨论”，不得在本计划中标记完成。

## Phase 3 处理方式

Phase 3 暂不实现。下一步先单独进行需求讨论，明确：

- AI 规划的最小输入和输出是什么；
- 是生成全书规划、单卷规划，还是从单卷到章节逐层生成；
- 哪些规划必须作者确认；
- 规划如何影响后续章节任务书和上下文包；
- 如何证明 AI 实际使用了规划，而不是只保存人工填写的 CRUD 数据。

讨论达成一致后，另写 Phase 3 设计文档，经确认后再写实施计划。
