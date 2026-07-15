# Novel Agent Phase 6：作者三栏工作台与可追溯创作会话设计

> 日期：2026-07-15
> 状态：已与作者确认，等待规格审阅
> 范围：以作者创作为中心重构写作前端；为 Phase 6 的检索来源、草稿、审查和修订建立可恢复的 AI 创作会话。

## 1. 背景与目标

现有写作体验被拆成两个页面：`WritingWorkspaceView` 是 900px 宽的纵向步骤卡片，`EditorView` 是独立的章节编辑器。蓝图、计划、任务书、上下文包、生成草稿和版本修订都按表单顺序堆叠，作者无法在写作时保持对章节正文的持续关注。

Phase 6 将写作入口重构为独立全屏的作者工作台：左侧管理章节和未接受草稿，中间只显示文稿，右侧是可恢复的 AI 创作会话。AI 的计划、检索来源、生成、审查和修订都在会话中呈现为消息或操作卡；中央文稿不再承载流程卡片。

目标：

1. 作者在单一工作台内完成选章、创作、AI 协作、审查和接受草稿。
2. 每次 AI 创作都有持久化会话、消息记录、WritingRun 和上下文来源快照，可在刷新或再次打开后恢复。
3. 检索来源只显示在产生该结果的 AI 消息上下文中，不向小说正文插入引用标记。
4. 保持作者控制：AI 不能静默覆盖正文，接受、废弃和应用 AI 修订需要作者点击确认。
5. 复用现有 `WritingRun`、`ContextPackage`、`DraftVersion`、`DraftRevision` 和质量门禁业务逻辑，避免产生两套写作实现。

## 2. 已确认的产品决策

- 主界面采用独立全屏三栏工作台，而非把三栏嵌回当前后台内容区。
- 左侧为章节资源管理器；中央为唯一的文稿空间；右侧为 AI 创作协作区。
- 右侧是真实的、可恢复的章节创作会话，不是将既有按钮伪装成聊天气泡。
- 右侧采用“自然语言对话 + 结构化操作卡片”的混合交互。
- AI 草稿生成结束后，自动切换到中央文稿；生成过程中不覆盖作者当前正在编辑的内容。
- 来源绑定具体 `WritingRun` 的快照；作者可看到来源资料与入选原因，不默认看到向量分数和 Token 等检索诊断。
- 初版不实现逐 Token 流式文本；右栏展示生成中状态，完成后一次性载入草稿，之后可在不改变交互语义的前提下增量加入流式输出。

## 3. 路由与工作台布局

新增独立路由：

```text
/novels/:id/studio                         # 默认最近可继续的会话或章节
/novels/:id/studio?chapter_id=:chapterId   # 指定已接受章节
/novels/:id/studio?session_id=:sessionId   # 指定创作会话 / 未接受草稿
```

该路由位于 `AppLayout` 之外，与当前全屏 `EditorView` 一样不显示通用后台侧栏。现有入口兼容策略：

| 旧入口 | 迁移后行为 |
| --- | --- |
| `/novels/:id/writing` | 重定向到 `/novels/:id/studio` |
| `/novels/:id/edit/:chapterId` | 重定向到带 `chapter_id` 的 Studio 路由 |
| 小说详情页的章节“编辑” | 跳转到对应 Studio 章节 |
| 小说工作区 Tab 的“写作” | 跳转到 Studio |

工作台顶部只保留小说名、当前文稿状态、自动保存状态、字数、当前版本和必要的全局动作。正文不显示蓝图、上下文包或质量门禁的独立大卡片。

```text
┌──────────────────────── Studio 顶栏 ──────────────────────────┐
│ 小说名 · 第 18 章 / AI 草稿 v1 · 已保存 · 3,248 字 · 接受草稿 │
├────────────────┬──────────────────────────────┬───────────────┤
│ 章节资源管理器  │ 文稿编辑器                    │ AI 创作协作    │
│                │                              │               │
│ 已接受章节     │ 标题                          │ 会话消息流    │
│ 未接受草稿     │ 正文                          │ 操作卡        │
│ 新建草稿       │                              │ 来源详情      │
│                │                              │ 对话输入      │
└────────────────┴──────────────────────────────┴───────────────┘
```

### 3.1 左侧：章节资源管理器

- 按卷（当前无卷数据时按章节列表）列出已接受章节，显示标题、状态和字数。
- 单独列出 `running`、`completed`、`decision_required` 的未接受 `WritingRun`，使用“草稿”分组，不伪装成正式章节。
- 选中正式章节时，中央加载其正文；选中草稿时，中央加载该草稿的 `DraftWorkingCopy` 或当前 `DraftVersion`。
- “新建草稿”创建新的 `WritingSession`，不预先创建空章节；只有作者接受草稿后才创建或更新 `Chapter`。

### 3.2 中间：文稿编辑器

- 中间区域始终是正文和标题，不承载 AI 流程卡片。
- 已接受章节使用章节正文编辑状态；未接受草稿使用工作副本状态，并在顶部显示“AI 草稿 · 未接受”。
- 当 AI 为另一个会话生成时，当前文稿保持可编辑；生成完成后仅在用户当前会话或当前选中会话中自动切换到新草稿。
- 草稿的“接受为章节”“废弃”“创建版本”“查看历史”等操作位于顶部或右侧对应操作卡，不插入正文。

### 3.3 右侧：AI 创作协作

右栏为按时间排序、可刷新恢复的消息流。消息类型包括：

- 作者文字请求；
- AI 普通回复和澄清问题；
- 章节计划、任务书、上下文准备、草稿生成、审查和修订等结构化操作卡；
- 来源摘要卡与可展开的来源详情；
- 决策卡、候选修订、错误和重试卡。

来源卡只属于生成该草稿或建议的 AI 消息。展开后显示资料类型、章节/场景、原文摘要、作者可理解的入选原因及“查看原文”操作；诊断字段放在默认折叠的开发诊断区域。

### 3.4 响应式边界

- 宽度不低于 1280px 时同时显示三栏。
- 1024px 至 1279px 时左栏可折叠，正文和右栏保持可见。
- 宽度低于 1024px 时，左栏和右栏改为抽屉；移动设备不作为长文创作的优化目标，但基本浏览、对话和确认动作必须可用。

## 4. 创作会话与文稿生命周期

### 4.1 新增持久化模型

| 模型 | 关键字段 | 职责 |
| --- | --- | --- |
| `WritingSession` | `novel_id`、`target_chapter_id?`、`active_writing_run_id?`、`title`、`status`、时间戳 | 一次章节创作或章节修订的可恢复边界 |
| `WritingMessage` | `session_id`、`role`、`message_type`、`content_json`、`writing_run_id?`、`context_package_id?`、`draft_version_id?`、`action_status` | 作者输入、AI 回复和结构化操作卡的时间线 |
| `DraftWorkingCopy` | `writing_run_id`、`draft_version_id`、`content`、`title`、`base_revision_sequence`、`updated_at` | 中央编辑器的可自动保存正文，不为每次输入创建正式版本历史 |

`WritingRun` 增加可空的 `writing_session_id`。历史 WritingRun 保持可读；首次在 Studio 打开历史草稿时，系统按需创建迁移会话，避免数据回填阻塞部署。

`ContextPackage` 和 `WritingRun.context_snapshot_json` 继续是上下文事实来源。Phase 6 检索结果写入 `context_snapshot_json` 时，至少包含如下展示对象；`source_id` 必须能定位到 MySQL 中的原始资料，`locator` 不能只依赖易变的章节标题：

```json
{
  "source_items": [
    {
      "source_id": "chapter:18:scene:3",
      "source_type": "chapter_scene",
      "title": "第 18 章 · 第 3 场",
      "locator": { "chapter_id": 18, "scene_index": 3 },
      "preview": "沈砚在雨夜发现军饷账册的异常……",
      "inclusion_reason": "与当前角色认知和军饷案剧情线直接相关"
    }
  ],
  "diagnostics": { "retrieval": [] }
}
```

向量分数、稀疏分数、重排分和 Token 用量只进入 `diagnostics`，默认不向作者展示。

### 4.2 会话调度

新增 `WritingStudioService` 作为会话协调层，职责是：

1. 原子保存作者消息并创建待处理 AI 消息；
2. 使用现有 AI 基础设施识别写作意图或提出澄清问题；
3. 调用既有的计划、任务书、上下文包、WritingRun、审查和修订服务；
4. 将业务结果写回结构化 `WritingMessage`，并关联业务主键；
5. 在每次失败时将 AI 消息置为 `failed`，不改写现有章节或草稿正文。

自然语言解释由受限的 `StudioAgent` 处理。它只能返回以下动作提案：`clarify`、`generate_plan`、`generate_brief`、`generate_context`、`generate_draft`、`review_draft`、`propose_revision`、`explain_sources`。Agent 不拥有直接写入章节、版本或会话状态的工具；`WritingStudioService` 验证提案的会话状态和所有权后才调用领域服务。

明确、非破坏性的作者请求（例如“按这个目标生成下一章草稿”）可以直接启动生成。接受草稿、废弃草稿、应用候选修订、强制接受和恢复历史版本必须由结构化卡片上的明确按钮确认，不能因 AI 回复、消息重放或路由恢复而自动执行。

### 4.3 草稿与自动保存

`DraftVersion` 继续表示作者可见的版本/检查点，`DraftRevision` 继续表达已应用的手动修订、AI 修订和恢复历史。`DraftWorkingCopy` 解决作者编辑器的自动保存需求：

1. 草稿生成完成后，确保初始 `DraftVersion` 存在，并创建内容相同的 WorkingCopy。
2. 中央编辑器以短暂防抖更新 WorkingCopy，顶部显示“保存中 / 已保存”。
3. 创建版本、请求 AI 修订、应用候选修订或接受草稿前，服务先将 WorkingCopy 原子归并为一条 `manual_edit` DraftRevision；默认原因为“作者工作副本保存”，作者可在版本检查器中补充更具体的语义标题。
4. 归并后再执行原有的版本或修订逻辑，保留现有 `revision_sequence`、内容哈希和补丁冲突保护。

因此不会因自动保存产生大量正式历史，也不会丢失刷新前的作者文字。

### 4.4 生成、审查与接受流程

```text
作者消息
  → 写入会话消息
  → 计划 / 任务书 / 上下文包 / WritingRun
  → AI“草稿已完成”操作卡（关联 run 与来源快照）
  → 新草稿自动进入中央 WorkingCopy
  → 作者编辑、审查或请求修订
  → 作者点击接受
  → WorkingCopy 归并、accept_writing_run、创建/更新 Chapter
  → 草稿从左栏移入已接受章节
```

质量门禁、待处理修复、Phase 3 决策和 Phase 4 候选修订沿用既有领域状态。其表现位置从纵向写作页的独立卡片迁入会话中的操作卡；后端验证顺序不改变。

## 5. API 与服务边界

新增的工作台 API 全部嵌套在 `/api/v1/novels/{novel_id}/` 下：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/writing-sessions` | 创建章节创作或修订会话 |
| `GET` | `/writing-sessions` | 列出可继续会话与左栏草稿摘要 |
| `GET` | `/writing-sessions/{session_id}` | 获取会话、消息、活动草稿和工作副本 |
| `POST` | `/writing-sessions/{session_id}/messages` | 写入作者请求并同步执行可识别的 AI 任务 |
| `POST` | `/writing-sessions/{session_id}/actions/{message_id}` | 明确确认操作卡上的接受、废弃、应用或重试动作 |
| `PUT` | `/writing-sessions/{session_id}/working-copy` | 防抖保存标题、正文和基础修订序列 |
| `GET` | `/writing-runs/{run_id}/sources` | 返回该 run 的不可变来源展示模型 |

工作台 API 是对现有领域服务的协调封装，不复制 `WritingService`、`DraftVersionService`、`ModificationService` 或质量门禁的业务规则。旧 API 保留，用于兼容旧链接、自动化测试和逐步迁移。

初版使用普通请求/响应：消息在请求开始时创建 `running` 状态，在业务完成后更新为 `completed`、`needs_confirmation` 或 `failed`。每次触发昂贵 AI 操作使用与作者消息绑定的幂等键，避免双击、刷新重放或网络重试创建重复 WritingRun。

## 6. 交付切分

本设计作为一个创作工作台功能交付，但按以下顺序实施和验收，确保每一步都能独立运行：

1. **会话与工作台外壳**：新增会话、消息和 WorkingCopy 数据；建立 Studio 全屏路由、三栏布局、章节/草稿导航与刷新恢复，不改变既有 AI 生成算法。
2. **受限会话调度**：接入 StudioAgent 和 `WritingStudioService`，把现有计划、上下文、生成、审查和修订服务投射为右栏操作卡；实现幂等、确认和失败重试。
3. **检索来源与创作闭环**：接入 Phase 6 向量检索结果快照、来源面板、WorkingCopy 归并、版本冲突处理和旧路由重定向；完成完整测试和真实 AI 验证记录。

## 7. 前端架构

建议新增和调整的前端边界：

```text
views/studio/StudioView.vue
components/studio/StudioChapterExplorer.vue
components/studio/StudioDocumentPane.vue
components/studio/StudioConversationPane.vue
components/studio/StudioMessage.vue
components/studio/StudioActionCard.vue
components/studio/StudioSourcesPanel.vue
components/studio/StudioVersionInspector.vue
stores/writingStudio.ts
api/writingStudio.ts
types/writingStudio.ts
```

- `StudioView` 只处理路由参数、三栏布局和当前选中对象。
- `StudioChapterExplorer` 只负责章节、草稿和会话的选择，不直接请求 AI。
- `StudioDocumentPane` 只负责文本输入、自动保存状态、字数和当前文稿动作。
- `StudioConversationPane` 只负责消息流、输入、操作卡触发和来源面板。
- `writingStudio` store 聚合会话数据；现有 `writing`、`revisions`、`novels` store 继续负责其所属领域数据。
- 现有 `WritingEditor` 的排印和编辑能力抽离后复用，`WritingWorkspaceView` 退为兼容重定向，不保留纵向流程 UI。

## 8. 错误、并发与安全

- AI 服务、检索、质量门禁或数据库事务失败时，会话写入失败消息和重试动作；不覆盖中央 WorkingCopy，不新建或修改正式章节。
- WorkingCopy 保存带 `base_revision_sequence`。若版本在另一窗口或由已应用的 AI 候选发生变化，保存返回冲突，前端提供重新加载或保留为新草稿版本，不静默覆盖。
- 任何来源详情通过 WritingRun、会话和小说所有权三重校验，未授权访问返回与现有小说资源一致的 NotFound。
- 已锁定章节不可被 Studio 的编辑、修订、接受或自动保存路径修改。
- 会话消息重放不会重复执行操作：运行中的消息返回当前状态，已完成消息返回已关联的业务结果。

## 9. 测试与验收

### 9.1 后端

- 模型与迁移：会话、消息、WorkingCopy、WritingRun 外键和历史数据按需会话化。
- 所有权：不同用户、不同小说和锁定章节均无法读取或写入会话资源。
- 调度：作者消息被持久化，生成结果正确关联 WritingRun、上下文包和消息；重复请求不会创建重复 run。
- WorkingCopy：防抖保存、归并为单条手动修订、修订序列冲突和刷新恢复。
- 失败：真实 AI 调用失败、检索失败和事务失败不污染正文、版本、章节或会话的旧成功消息。
- 来源：`/sources` 始终读取 WritingRun 快照，后续上下文包变化不改变旧来源。

### 9.2 前端

- 章节与草稿分组、路由选择和从旧路由重定向。
- 会话刷新恢复，消息按类型渲染，来源卡只在关联消息中展示。
- 草稿完成时中央正确切换，生成中的其他会话不覆盖当前文稿。
- 自动保存状态、冲突提示、失败重试、接受/废弃/修订确认卡。
- 桌面三栏、窄屏栏位折叠和键盘保存行为。

### 9.3 完整验证

后端执行完整 pytest、Alembic 升级验证和确定性会话集成测试；前端执行 Vitest、`vue-tsc --build`、lint、生产构建和关键 Playwright 流程。真实 AI 集成验证单独记录，缺少密钥时只能明确跳过，不能在生产代码中回退为 Fake。

## 10. 非目标

- 不在小说正文插入类似对话产品的来源编号。
- 不向作者默认显示向量分数、重排分、Token 使用等检索诊断。
- 不引入多人实时协作、评论系统或 CRDT。
- 不在本期实现 Token 级流式输出；接口和消息状态为后续扩展保留空间。
- 不移除既有写作、审查、版本 API，直到 Studio 完成迁移验证。

## 11. 完成定义

作者能够从单一全屏工作台打开或新建创作会话，在左侧选择章节/草稿，在中间安全编辑且自动保存，在右侧与 AI 自然对话并执行可确认的创作操作。每个 AI 草稿、审查或修订都可以追溯至对应消息、WritingRun 和不可变来源快照；刷新、失败和并发冲突均不会丢失或静默覆盖作者正文。
