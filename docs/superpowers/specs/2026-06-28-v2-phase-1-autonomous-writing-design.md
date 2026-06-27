# Novel Agent v2 阶段 1：最小自主写作闭环设计

> 日期：2026-06-28  
> 状态：已评审  
> 范围：完成第二版需求文档的阶段 1：从小说蓝图到下一章可编辑草稿的最小自主写作闭环。  
> 基线：当前项目已具备小说/章节管理、人工记忆管理、待确认记忆和章节记忆提取能力，这些能力作为阶段 0 底座复用。

## 1. 背景

第二版需求文档将产品定位调整为“作者可控的 AI 自主写作工作台”。当前项目已经完成长期创作资料底座：小说、章节、角色、世界设定、剧情事实、伏笔、待确认记忆，以及从已写章节提取结构化记忆的 AI 流程。

当前缺口不是继续补资料管理页面，而是建立写作前的最短闭环：AI 能根据作者构思和已确认资料生成蓝图、下一章计划、章节任务书、上下文包和章节草稿；草稿先进入可追踪的写作运行记录，只有作者接受后才写入正式章节正文。

## 2. 阶段目标

阶段 1 只完成“下一章最小自主写作闭环”：

```text
小说构思 / 现有小说资料
↓
生成或编辑激活蓝图
↓
生成下一章章节大纲
↓
生成章节任务书 + 篇幅契约
↓
生成上下文包快照
↓
WritingRun 生成草稿
↓
基础硬门槛检查
↓
作者接受草稿，写入章节正文
```

阶段成功标准：作者能从一个小说构思生成下一章章节任务书，并让 AI 按目标字数写出一章可编辑草稿，而不是只生成剧情梗概式短章。

## 3. 非目标

- 不做自动连续生成多章。
- 不做卷/篇章规划和长期结构版本管理。
- 不做完整质量门禁和 `ReviewIssue` 列表。
- 不做人设、设定、伏笔、风格等完整检查 Agent。
- 不做 `DraftVersion` 差异管理。
- 不做复杂向量检索或 RAG。
- 不让 AI 自动写入正式记忆。
- 不让 AI 草稿直接覆盖正式章节正文。
- 不做多 Agent 并发执行；第一阶段按顺序串联，保证可调试。

## 4. 关键设计原则

### 4.1 AI 能力共享，业务流程分离

现有 `backend/app/ai/` 是共享 AI 能力层和记忆提取流程的承载位置。它已经负责模型配置、Agent factory、工具、日志中间件，以及章节内容提取为 `PendingMemory` 的流程。

阶段 1 新增的写作流程不另起一套 AI 基础设施，而是新增 `writing` 业务模块调用 `ai` 能力：

```text
backend/app/ai/
  模型配置、Agent 创建、工具、日志、通用调用能力

backend/app/writing/
  蓝图、章节大纲、章节任务书、上下文包、WritingRun、接受/废弃草稿

现有记忆提取流程
  已确认章节正文 → PendingMemory → 作者确认 → 正式长期记忆
```

这样后续可以统一成完整流水线，但不会混淆“写作前计划/草稿”和“写作后记忆沉淀”。

### 4.2 草稿必须先进入 WritingRun

AI 生成的正文草稿不直接覆盖章节正文。草稿先保存到 `writing_runs`，作者可以接受或废弃。只有接受后，系统才写入目标章节正文或创建新章节。

### 4.3 ContextPackage 是快照，不是事实来源

`context_packages` 保存本次写作时 AI 看到的上下文快照，便于追踪生成依据。正式事实来源仍然是角色卡、世界设定、剧情事实、伏笔和章节摘要。

### 4.4 第一阶段只做基础硬门槛

基础硬门槛用于防止明显不合格输出：

- 蓝图、章节大纲、任务书、篇幅契约的必需字段完整。
- 草稿字数达到最低字数。
- 草稿不像纯大纲、列表或摘要。

完整质量门禁放到第二阶段。

## 5. 后端数据模型

新增后端模块：

```text
backend/app/models/writing.py
backend/app/schemas/writing.py
backend/app/repositories/writing_repo.py
backend/app/services/writing_service.py
backend/app/api/writing.py
```

### 5.1 NovelBlueprint

保存小说蓝图。一个小说可以有多份蓝图，第一阶段只允许一份 `active` 蓝图。

核心字段：

```ts
{
  id: number
  novel_id: number
  version: number
  status: "draft" | "active" | "archived"
  content_json: {
    core_promise: string
    theme: string
    main_conflict: string
    character_arcs: string
    world_rules: string
    narrative_perspective: string
    style_constraints: string
    ending_direction: string
  }
  created_at: string
  updated_at: string
}
```

### 5.2 ChapterPlan

保存下一章章节大纲。第一阶段只生成下一章，不批量生成多章。

核心字段：

```ts
{
  id: number
  novel_id: number
  chapter_id?: number | null
  position: number
  status: "draft" | "ready" | "used"
  content_json: {
    chapter_title: string
    plot_task: string
    character_task: string
    information_task: string
    emotional_effect: string
    pacing: string
    foreshadowing_task: string
  }
  created_at: string
  updated_at: string
}
```

`chapter_id` 可为空，因为计划可以先于章节创建。

### 5.3 ChapterBrief

保存章节任务书和篇幅契约。

核心字段：

```ts
{
  id: number
  novel_id: number
  chapter_plan_id: number
  chapter_id?: number | null
  status: "draft" | "ready" | "used"
  brief_json: {
    writing_goal: string
    scenes: Array<{
      name: string
      purpose: string
      conflict: string
      expected_words: number
    }>
    participating_characters: string
    conflict_design: string
    information_control: string
    foreshadowing_handling: string
    writing_constraints: string
    acceptance_criteria: string
  }
  length_contract_json: {
    target_words: number
    min_words: number
    max_words: number
    scene_word_allocation: Array<{
      scene: string
      words: number
    }>
    density_requirements: string
    expansion_strategy: string
    compression_strategy: string
  }
  created_at: string
  updated_at: string
}
```

默认篇幅契约：

```text
target_words = 3000
min_words = 2000
max_words = 5000
```

作者可以在前端修改篇幅契约后再生成草稿。

### 5.4 ContextPackage

保存本次写作使用的上下文快照。

核心字段：

```ts
{
  id: number
  novel_id: number
  chapter_brief_id: number
  package_json: {
    blueprint_summary: string
    chapter_brief: object
    previous_chapter_summary?: string
    characters: object[]
    world_settings: object[]
    plot_facts: object[]
    foreshadowings: object[]
    style_guide?: string
    length_contract: object
    acceptance_criteria: string
  }
  created_at: string
}
```

第一阶段上下文包使用结构化查询拼装，不引入向量检索。

### 5.5 WritingRun

保存 AI 写作运行和草稿池。

核心字段：

```ts
{
  id: number
  novel_id: number
  chapter_brief_id: number
  context_package_id: number
  target_chapter_id?: number | null
  status: "running" | "completed" | "failed" | "accepted" | "discarded"
  draft_content: string
  word_count: number
  gate_result_json: {
    passed: boolean
    reasons: string[]
    min_words: number
    target_words: number
    max_words: number
    outline_like: boolean
  }
  error_message?: string | null
  accepted_at?: string | null
  created_at: string
  updated_at: string
}
```

## 6. 后端 API

所有接口挂在现有小说路径下，继续使用统一响应格式：

```text
{"code": 0, "message": "ok", "data": ...}
```

### 6.1 蓝图

```text
POST /api/v1/novels/{novel_id}/blueprints/generate
GET  /api/v1/novels/{novel_id}/blueprints
PUT  /api/v1/novels/{novel_id}/blueprints/{blueprint_id}
PUT  /api/v1/novels/{novel_id}/blueprints/{blueprint_id}/activate
```

`generate` 使用小说 `title`、`description`、`genre`、`style_guide` 和作者输入的构思生成第一版蓝图。`activate` 会把同小说其他 active 蓝图改为 `archived`，保证同一小说只有一个 active 蓝图。

### 6.2 下一章计划

```text
POST /api/v1/novels/{novel_id}/chapter-plans/next/generate
PUT  /api/v1/novels/{novel_id}/chapter-plans/{plan_id}
```

生成前必须存在 active 蓝图。计划可绑定已有章节，也可以不绑定章节。

### 6.3 章节任务书

```text
POST /api/v1/novels/{novel_id}/chapter-briefs/generate
PUT  /api/v1/novels/{novel_id}/chapter-briefs/{brief_id}
```

根据 `chapter_plan_id` 生成任务书和篇幅契约。默认篇幅契约为 `3000 / 2000 / 5000`。

### 6.4 上下文包

```text
POST /api/v1/novels/{novel_id}/context-packages/generate
```

根据 `chapter_brief_id` 生成上下文快照，包含蓝图摘要、任务书、上一章摘要、角色、设定、剧情事实、伏笔、风格指南和篇幅契约。

### 6.5 写作运行

```text
POST /api/v1/novels/{novel_id}/writing-runs
GET  /api/v1/novels/{novel_id}/writing-runs
GET  /api/v1/novels/{novel_id}/writing-runs/{run_id}
PUT  /api/v1/novels/{novel_id}/writing-runs/{run_id}/accept
PUT  /api/v1/novels/{novel_id}/writing-runs/{run_id}/discard
```

创建 `writing-runs` 时必须提供 `chapter_brief_id` 和 `context_package_id`。系统调用 AI 生成草稿，保存草稿和硬门槛结果。

接受逻辑：

- 如果 `target_chapter_id` 存在，覆盖该章节正文。
- 如果 `target_chapter_id` 为空，创建新章节并写入草稿正文。
- 接受后设置 `writing_run.status = accepted` 和 `accepted_at`。
- 不自动触发记忆提取，只提示作者可运行现有章节提取流程。

废弃逻辑：

- 设置 `writing_run.status = discarded`。
- 不修改章节正文。

## 7. AI 调用与基础硬门槛

### 7.1 结构化生成

蓝图、章节大纲、任务书和篇幅契约应尽量要求 AI 返回结构化 JSON。后端 schema 负责校验必需字段。校验失败时返回明确错误，并保存失败信息用于排查。

### 7.2 正文生成

写作提示词必须强调：

- 按章节任务书写正文，不要自由发挥成另一章。
- 按篇幅契约展开场景、冲突、反应、动作、对话和氛围。
- 不输出大纲、列表、总结或解释，只输出章节正文。
- 如果篇幅不足，优先扩写任务书指定的场景过程、角色反应、冲突升级和信息控制。

### 7.3 字数统计

第一阶段使用后端本地字数统计。中文文本按非空白字符计数，英文按词计数的精度不是阶段重点；测试只要求统计逻辑稳定且能触发最低字数门槛。

### 7.4 纲要体检测

第一阶段只做启发式检测，判断草稿是否明显像纲要或列表：

- 正文中项目符号、编号行占比过高。
- 出现大量“场景一”“目标”“任务”“摘要”等结构化规划词。
- 平均段落过短且缺少对话、动作或描写。

该检测用于硬门槛，但不是完整质量评价。

### 7.5 扩写策略

如果初稿低于 `min_words` 或被判定为明显纲要体，系统在第一阶段固定进行一次扩写调用。扩写仍不达标时，`WritingRun.status = failed`，`gate_result_json.reasons` 记录失败原因。

## 8. 前端设计

新增工作区导航项：

```text
章节 | 角色 | 设定 | 待确认 | 写作
```

新增路由：

```text
/novels/:id/writing
```

新增文件：

```text
frontend/src/types/writing.ts
frontend/src/api/writing.ts
frontend/src/stores/writing.ts
frontend/src/views/novels/WritingWorkspaceView.vue
```

页面采用线性工作台，不拆成复杂多页：

1. 小说蓝图
   显示当前 active 蓝图。没有蓝图时提供“生成蓝图”。支持编辑和激活。

2. 下一章计划
   生成下一章章节大纲，展示剧情任务、角色任务、信息任务、情绪效果、节奏目标和伏笔任务。

3. 章节任务书
   生成任务书和篇幅契约。可编辑目标字数、最低字数、最高字数，默认 `3000 / 2000 / 5000`。

4. 上下文包
   展示本次写作会使用的上下文摘要，包括角色、设定、剧情事实、伏笔、上一章摘要和风格指南。

5. 生成草稿
   创建 `WritingRun`，展示草稿、字数统计和基础门槛结果。作者可以接受到章节或废弃。

## 9. 错误处理与权限

- 所有接口必须校验小说属于当前用户。
- 子资源必须同时校验 `novel_id`，不能只按子资源 id 查询后返回。
- 不存在或不属于当前小说的资源返回 `NotFound`，避免泄露其他用户数据。
- 没有 active 蓝图时生成下一章计划返回业务错误。
- 任务书或上下文包缺失时不能创建 `WritingRun`。
- AI 调用失败时保存失败状态和错误信息，不创建或修改章节正文。
- `accepted` 或 `discarded` 的 `WritingRun` 不允许再次接受或废弃。

## 10. 测试与验证

### 10.1 后端自动化测试

默认后端测试使用 fake LLM，不依赖真实 DeepSeek。

覆盖：

- 蓝图生成、编辑、激活。
- 同一小说只有一份 active 蓝图。
- 无 active 蓝图时不能生成下一章计划。
- 生成下一章计划。
- 生成章节任务书和默认篇幅契约。
- 生成上下文包，包含现有角色、设定和上一章摘要。
- 创建 `WritingRun` 并保存草稿。
- 草稿低于最低字数时固定触发一次扩写；扩写仍不达标时进入失败状态。
- 明显纲要体草稿被硬门槛拦截。
- 接受 `WritingRun` 后写入章节正文。
- 废弃 `WritingRun` 不修改章节正文。
- 跨用户访问蓝图、计划、任务书、上下文包、WritingRun 返回 404。

命令：

```bash
.venv/bin/python -m pytest tests/ -x -q
```

### 10.2 真实 AI 冒烟测试

单独保留可选 integration test：

- 没有 `DEEPSEEK_API_KEY` 时跳过。
- 只验证状态、字段结构和非空正文，不严格断言具体文案。

### 10.3 前端验证

覆盖：

- 写作工作台可以展示蓝图、计划、任务书、上下文包和 WritingRun 区块。
- 篇幅契约默认值为 `3000 / 2000 / 5000`。
- 接受草稿调用正确 API。
- 废弃草稿不会进入章节编辑器。
- loading、失败和空状态有基础展示。

命令：

```bash
npm run type-check
npm run test:unit
npm run build
```

## 11. 实施顺序建议

1. 后端写作模型和 migration。
2. 后端 schema、repository、service、API。
3. 抽象可测试的 AI 调用接口，默认测试注入 fake LLM。
4. 实现基础硬门槛和扩写流程。
5. 后端 API 测试。
6. 前端 writing 类型、API client、store。
7. 写作工作台页面和工作区导航入口。
8. 前端测试与构建验证。
9. 可选真实 AI 冒烟测试。

## 12. 后续阶段衔接

阶段 1 完成后，系统可以把写作流程和现有记忆提取流程串联起来：

```text
WritingRun 生成草稿
↓
作者接受，写入章节正文
↓
作者运行现有 extract 接口
↓
PendingMemory
↓
作者确认
↓
正式长期记忆
↓
下一章 ContextPackage 使用这些记忆
```

后续阶段可以在不破坏当前边界的前提下继续加入完整质量门禁、规划版本、局部改写、草稿版本管理和高级上下文检索。
