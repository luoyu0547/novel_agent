# Novel Agent v2 Phase 4：辅助修改与版本管理设计

> 日期：2026-07-13
> 状态：已确认
> 范围：让作者围绕一章完成“生成 → 检查 → 局部修改 → 确认”的可控修改闭环，并建立符合作者认知的草稿版本管理。
> 前置条件：Phase 1 自主写作、Phase 2 质量门禁和 Phase 3 动态剧情规划继续可用。

## 1. 设计结论

Phase 4 引入修改 Agent、修改候选、差异确认和草稿版本管理，但必须区分两个不同层级：

- `DraftVersion` 表示作者主动发起的一轮完整创作。
- `DraftRevision` 表示该轮创作内部的一次生成、修复、选择、手动编辑或恢复操作。

版本号只在作者显式执行“创建新版本”时递增。初稿生成、篇幅补足、质量门禁重写、ReviewIssue 局部修复、作者选择修复方向和当前轮次内的历史内容恢复都不能自动增加版本号。

例如首次写作过程为：

```text
DraftVersion v1：首次生成轮次
├── 初稿生成
├── 字数补足
├── 质量门禁重写
├── DraftRevision R1：补充角色动机
├── DraftRevision R2：按作者选择调整表达
└── 作者确认 v1
```

只有作者之后选择“基于 v1 创建新版本”时，才创建 `DraftVersion v2`。

## 2. 需求依据

第二版阶段路线图对 Phase 4 的明确要求是：

- 根据 `ReviewIssue` 局部改写指定片段。
- 为作者生成多个修复方向。
- 使用 `DraftVersion` 保存章节草稿版本。
- 展示修改前后的差异。
- 记录修改理由。
- 完成“生成 → 检查 → 局部修改 → 接受”的单章闭环。

修改 Agent 的需求边界是：

- 默认只修改存在问题的片段，不默认重写整章。
- 可以补充铺垫、删除冲突内容、统一风格。
- 每次修改必须可追踪。
- 不得擅自替换正式章节。

本阶段继续遵守以下产品原则：

- 检查优先于自动修改。
- AI 生成的修改不能绕过作者确认。
- 草稿不能直接覆盖正式章节。
- 正式长期记忆继续通过 `PendingMemory` 由作者确认。
- `locked` 章节是不可修改的已发布事实。

## 3. 当前实现基线与缺口

当前项目已经具备：

- 7 类质量检查和 `ReviewIssue`。
- 自动修复日志 `RepairLog`。
- 需要作者意图的 `PendingRepair`。
- Phase 3 规划冲突产生的 `DraftRevision` 候选。
- 候选差异展示和 `candidate → applied` 应用流程。
- WritingRun 接受、章节发布和 `locked` 保护。

当前缺口是：

1. `PendingRepair` 应用后直接改写 `WritingRun.draft_content`，没有统一候选预览。
2. `DraftRevision` 主要服务规划冲突，不能表达普通 ReviewIssue、作者手动编辑和当前版本内恢复。
3. 没有 `DraftVersion`，也没有作者主动创建新版本的入口。
4. 当前实现把 ReviewIssue 的严重程度和修复方式混在 `severity` 字段中。
5. 没有版本历史、版本内修订历史和过期候选保护。
6. 前端只展示当前 Phase 3 候选，不能围绕一章连续检查和修改。
7. 默认后端测试仍可能因本地密钥存在而访问真实 DeepSeek，离线测试边界不稳定。
8. 当前后端虚拟环境是 Python 3.11，与项目声明的 Python 3.12 基线不一致。

## 4. 核心概念与边界

### 4.1 WritingRun

`WritingRun` 是一个章节草稿的工作空间，保存当前正在编辑的正文和上下文快照。

同一个 WritingRun 可以包含多个作者主动创建的 `DraftVersion`，但同时只能有一个状态为 `draft` 的当前版本。`WritingRun.draft_content` 是当前版本正文的工作副本，保留该字段以兼容现有写作、审查和接受链路。

### 4.2 DraftVersion

`DraftVersion` 是作者可见的创作轮次，不是每次 AI 调用的快照。

状态语义：

- `draft`：当前创作轮次，可以在该版本内部继续产生和应用 DraftRevision。
- `accepted`：作者已接受到章节，正文冻结。
- `rejected`：作者废弃当前 WritingRun 时的当前版本。
- `archived`：作者显式创建新版本后，原版本成为只读历史。

只有以下动作可以创建 DraftVersion：

1. WritingRun 首次得到可供作者处理的草稿时，创建 v1。
2. 作者显式选择“创建新版本”时，基于指定历史版本创建 vN+1。

以下动作不能创建 DraftVersion：

- 初稿生成中的字数补足。
- 质量门禁的自动重写循环。
- 自动局部替换。
- ReviewIssue 修复候选的生成或应用。
- Phase 3 规划冲突候选的生成或应用。
- 作者在当前版本中的手动局部编辑。
- 把历史版本内容恢复到当前 draft 版本。

### 4.3 DraftRevision

`DraftRevision` 是当前版本内部的一次可追踪修改。它可以是待确认候选，也可以是已经应用的操作记录。

来源包括：

- `planning_decision`
- `review_issue`
- `author_request`
- `manual_edit`
- `restore`

状态为：

```text
candidate → applied
          → rejected
          → superseded
```

同一个基础正文可以产生多个候选。作者应用其中一个后，其他基于同一正文的候选自动变为 `superseded`。

### 4.4 ReviewIssue

`ReviewIssue` 只描述问题本身。严重程度和修复方式必须拆开：

- `severity`: `blocking | major | minor`
- `resolution_mode`: `auto_fixable | needs_intent`
- `status`: `open | resolved | ignored`

生成候选时问题仍为 `open`。只有应用候选后才变为 `resolved`；拒绝候选后问题保持 `open`；作者明确忽略后变为 `ignored`。

## 5. 数据模型

### 5.1 DraftVersion

新增 `draft_versions`：

```text
id: int
novel_id: int
chapter_id: int | null
writing_run_id: int
based_on_version_id: int | null
version: int
title: str
content: text
word_count: int
change_reason: text
status: draft | accepted | rejected | archived
revision_sequence: int
created_at: datetime
updated_at: datetime
```

约束：

- `(writing_run_id, version)` 唯一。
- 一个 WritingRun 最多有一个 `draft` 版本。
- `chapter_id` 在首次接受前允许为空，接受后回填。
- `accepted`、`rejected` 和 `archived` 版本的正文不可再修改。
- `revision_sequence` 每应用一次内部修订递增，用于并发和过期候选校验，不对作者显示为版本号。

### 5.2 DraftRevision

扩展现有 `draft_revisions`：

```text
draft_version_id: int
sequence: int
source_type: planning_decision | review_issue | author_request | manual_edit | restore
source_id: int | null
base_revision_sequence: int
base_content_hash: str
base_content: text
candidate_content: text
patches_json: list
diff_json: dict
scope_json: dict
reason: text
expanded_scope: bool
expanded_scope_reason: text | null
status: candidate | applied | rejected | superseded
created_at: datetime
updated_at: datetime
```

保留现有 `decision_id` 以兼容 Phase 3 数据，同时通过 `source_type/source_id` 建立统一来源协议。迁移不删除现有字段或记录。

### 5.3 ReviewIssue

扩展 `review_issues`：

```text
chapter_id: int | null
severity: blocking | major | minor
resolution_mode: auto_fixable | needs_intent
repair_options_json: list | null
resolved_by_revision_id: int | null
ignored_reason: text | null
status: open | resolved | ignored
```

现有 `auto_fixable/needs_intent` 值在服务边界归一化为 `resolution_mode`，不能继续作为业务严重程度。

## 6. 修改 Agent 协议

修改 Agent 分为两步。

### 6.1 生成修改方向

`generate_options()` 输入：

- 当前 DraftVersion 正文。
- ReviewIssue。
- 章节任务书和上下文快照。
- 作者资料、当前剧情计划和已发布事实。

输出 2–3 个真实可执行方向：

```text
label
summary
action
expected_effect
estimated_scope
recommended
recommendation_reason
```

只有一个合理方向时可以只返回一个，但必须解释为什么其他方向不可行。不能为了凑数量制造伪选项。

### 6.2 生成修改候选

`create_revision()` 输入作者选择的方向或自定义意图，输出：

```text
candidate_content
patches
diff
change_reason
scope
expanded_scope
expanded_scope_reason
```

每个 patch 包含：

```text
start_offset
end_offset
original_text
replacement_text
reason
```

服务端使用 patches 从基础正文重建候选，并验证结果与 `candidate_content` 完全一致。验证失败时不能保存候选。

如果无法局部修复，Agent 必须返回扩大范围说明或明确失败，不能静默改写整章。

## 7. 核心流程

### 7.1 首次生成版本

```text
创建 WritingRun
→ 生成初稿
→ 篇幅检查和补足
→ 质量门禁与最多三轮检查
→ 自动修复和重写在 WritingRun 内收敛
→ 得到可供作者处理的草稿
→ 创建 DraftVersion v1(status=draft)
```

质量门禁内部迭代继续使用 RepairLog 追踪，但不能创建 v2、v3。

如果 Phase 3 在生成期间产生规划决策，系统可以先为部分草稿创建 v1。决策候选应用后只更新 v1 当前内容，直到该 WritingRun 完成。

### 7.2 ReviewIssue 局部修改

```text
选择一条 open ReviewIssue
→ 生成 2–3 个修改方向
→ 作者选择或填写自定义意图
→ 生成 DraftRevision(candidate)
→ 作者查看差异
→ 应用或拒绝
```

首版一次只处理一条 ReviewIssue，避免多个问题的修改范围重叠。

应用候选时一次事务完成：

1. 校验版本仍为当前 `draft`。
2. 校验目标章节不是 `locked`。
3. 校验 `base_revision_sequence` 和正文哈希仍然有效。
4. 校验 patches 能重建候选正文。
5. 更新当前 DraftVersion 内容、字数和 `revision_sequence`。
6. 同步更新 `WritingRun.draft_content` 和 `word_count`。
7. 将候选标记为 `applied`。
8. 将同基础正文的其他候选标记为 `superseded`。
9. 将来源 ReviewIssue 标记为 `resolved`。
10. 一次性提交。

任何一步失败都回滚，原正文和问题状态保持不变。

### 7.3 作者手动编辑

作者明确点击保存时，创建一条 `source_type=manual_edit`、状态为 `applied` 的 DraftRevision，并更新当前 DraftVersion。系统不记录每次键盘输入，也不增加版本号。

### 7.4 创建新版本

只有作者显式执行“创建新版本”时才递增版本号：

```text
选择作为基础的历史版本
→ 填写新版本目标或原因
→ 将当前 draft 版本归档
→ 创建 vN+1(status=draft)
→ 复制基础版本正文到新版本
→ 同步 WritingRun 工作副本
```

创建新版本本身不是 AI 修改。后续 AI 优化继续记录为新版本内部的 DraftRevision。

创建新版本只允许发生在 WritingRun 尚未接受、当前仍存在 `draft` 版本时。服务先归档当前 draft，再创建新 draft。`accepted` 版本已经写入章节并触发记忆提取，不能再从该 WritingRun 开启 Phase 4 新版本，避免正文与 PendingMemory 来源失配。

### 7.5 当前轮次内恢复

把历史版本正文加载到当前 draft 版本时，不创建新版本。系统创建一条 `source_type=restore`、状态为 `applied` 的 DraftRevision，记录完整差异和来源版本。

恢复操作必须同时存在一个可写的当前 `draft` 版本。来源可以是同一 WritingRun 中的任意历史版本，但目标只能是当前 draft。如果 WritingRun 已经接受或废弃，没有当前 draft，Phase 4 拒绝恢复。

### 7.6 接受与发布

- 接受草稿时使用当前 DraftVersion 的正文。
- 存在未处理候选时，作者必须先应用或拒绝。
- 存在 `blocking` 且 `open` 的 ReviewIssue 时默认阻止接受。
- 作者可以显式强制接受，但必须填写原因并保存审计记录。
- 接受成功后，当前版本变为 `accepted`，回填 `chapter_id`，并触发现有 PendingMemory 提取。
- 接受后的版本不再进入 Phase 4 修改，也不能从同一 WritingRun 创建新版本；接受后修改与记忆失效策略不在本阶段处理。
- 发布后章节变为 `locked`，任何版本创建、恢复、候选应用或正文修改都必须被拒绝。

## 8. API 设计

所有端点继续嵌套在 `/api/v1/novels/{novel_id}/` 下。

### 8.1 版本

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/writing-runs/{run_id}/draft-versions` | 获取作者可见版本历史 |
| GET | `/draft-versions/{version_id}` | 获取一个版本正文和元数据 |
| POST | `/writing-runs/{run_id}/draft-versions` | 作者显式创建新版本 |
| POST | `/draft-versions/{version_id}/restore-into-current` | 把历史内容作为当前版本内部修订应用 |
| POST | `/writing-runs/{run_id}/manual-revisions` | 保存作者手动编辑，不增加版本号 |

创建新版本请求必须包含：

```text
based_on_version_id
change_reason
```

手动编辑和恢复请求必须包含当前 `revision_sequence`，用于拒绝过期写入。

### 8.2 ReviewIssue 与候选

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/writing-runs/{run_id}/review-issues` | 获取当前写作运行的问题 |
| POST | `/review-issues/{issue_id}/repair-options` | 生成并保存修改方向 |
| POST | `/review-issues/{issue_id}/draft-revisions` | 按选择或意图生成候选 |
| PUT | `/review-issues/{issue_id}/ignore` | 作者忽略问题并记录原因 |
| GET | `/draft-versions/{version_id}/draft-revisions` | 获取版本内部修订历史 |
| PUT | `/draft-revisions/{revision_id}/apply` | 应用候选，不增加版本号 |
| PUT | `/draft-revisions/{revision_id}/reject` | 拒绝候选 |

现有 Phase 3 `draft-revisions/{revision_id}/apply` 路径保持兼容，内部委托统一的版本内修订服务。

## 9. 服务与代码边界

### 9.1 DraftVersionService

负责：

- 创建或获取 v1。
- 作者显式创建新版本。
- 在当前版本内应用、拒绝和恢复修订。
- 同步 WritingRun 工作副本。
- 接受、废弃和锁定边界。
- 版本号、修订序号和过期校验。

### 9.2 ModificationService

负责：

- 校验 ReviewIssue 所有权和状态。
- 调用修改 Agent 生成方向和候选。
- 校验结构化输出、patches 和修改范围。
- 创建 DraftRevision，但不直接替换正文。

### 9.3 现有服务的调整

- `WritingService` 负责在首次草稿可供作者处理时创建 v1，并在接受时读取当前版本。
- `RepairService` 不再直接覆盖 WritingRun，改为生成或应用统一 DraftRevision。
- `PlotPlanningService` 继续负责规划和决策，但候选应用委托 `DraftVersionService`。
- `QualityGateService` 继续负责检查和内部自动修复，并把严重程度与修复方式分开保存。

`WritingService` 和 `PlotPlanningService` 已经较大，Phase 4 只抽取与版本和修改直接相关的职责，不进行无关的全局重构。

## 10. 前端工作台

草稿区域提供三个协作面板：

1. 正文面板：显示当前版本正文并高亮 ReviewIssue 位置。
2. 问题与修改面板：显示问题、严重程度、修改方向和自定义意图。
3. 候选与历史面板：在“内部修改”和“版本历史”之间切换。

内部修改显示：

```text
当前版本：v1 首次生成
生成过程（归入 v1）：初稿 → 自动扩写 → 质量门禁重写
内部修改：
- R2 作者选择：保留谨慎人设
- R1 局部修改：补充角色动机
```

只有作者创建新版本后，版本历史才显示：

```text
v2 节奏调整（当前）
v1 首次生成（已归档）
```

交互规则：

- 生成候选后正文保持不变。
- 差异视图只突出 patches，并显示必要上下文。
- 应用扩大范围的候选必须二次确认。
- 拒绝候选后问题保持 open，作者可以选择其他方向。
- 历史版本只读；“恢复”作用于当前 draft 版本，不自动生成新版本。
- “创建新版本”是独立、明确的作者动作。
- API 失败时保留当前正文、候选和表单输入。

## 11. 错误处理与并发安全

- DeepSeek 失败：不创建候选，不改变版本正文或问题状态。
- Pydantic 或 patches 校验失败：返回明确业务错误，不保存半成品。
- ReviewIssue 原文位置已变化：拒绝候选并提示重新检查。
- 候选基础修订序号或正文哈希过期：拒绝应用并提示重新生成。
- 扩大范围但作者未确认：拒绝应用。
- 当前版本不是 `draft`：拒绝任何内部修改。
- 存在另一个当前 draft 版本：拒绝创建新版本。
- WritingRun 已接受或废弃：拒绝创建新版本或恢复历史内容。
- 数据库事务失败：版本、WritingRun、候选和 ReviewIssue 一起回滚。
- 跨用户或跨小说资源：继续使用 404，不泄露存在性。
- `locked` 章节：所有版本创建、恢复、应用和手动编辑路径拒绝执行。

## 12. 测试与验收

### 12.1 后端确定性测试

覆盖：

- 首次生成完成后只创建 v1。
- 初稿、字数补足和最多两次自动重写仍然只有 v1。
- 多次内部修复只递增 `revision_sequence`，不增加版本号。
- 只有显式创建新版本才产生 v2。
- ReviewIssue 生成 2–3 个真实方向。
- 生成候选不改变当前正文。
- 应用候选更新当前版本和 WritingRun，但版本号不变。
- 拒绝候选不修改正文。
- 应用一个候选后，同基础正文的其他候选被 superseded。
- 过期候选不能覆盖新修订。
- 扩大范围必须二次确认。
- 手动保存创建 applied DraftRevision，但不创建新版本。
- 恢复历史内容创建 restore DraftRevision，但不创建新版本。
- 显式基于历史版本创建新版本时版本号递增。
- 接受使用当前版本正文并冻结版本。
- blocking 问题默认阻止接受，强制接受需要原因。
- AI、结构校验和数据库失败均不改变旧状态。
- locked、跨用户和跨小说写入被拒绝。

### 12.2 前端测试

覆盖：

- 当前版本和内部修订使用不同视觉层级。
- 一次内部修复不会在版本历史中出现 v2。
- 只有“创建新版本”后才显示新版本号。
- 问题选择、方向生成、自定义意图和候选差异展示。
- 应用、拒绝、过期和扩大范围确认。
- 手动编辑保存和当前轮次内恢复。
- blocking 问题接受确认。
- API 失败时保留当前状态。
- locked 状态下所有修改控件不可用。

### 12.3 端到端验收

```text
生成初稿
→ 内部篇幅补足和质量门禁重写
→ 得到唯一 DraftVersion v1
→ 检查产生 ReviewIssue
→ 生成多个修复方向
→ 生成候选但 v1 正文不变
→ 拒绝第一个候选
→ 应用第二个候选，产生 R1，版本仍为 v1
→ 作者手动修改，产生 R2，版本仍为 v1
→ 作者显式基于 v1 创建新版本，产生 v2
→ 在 v2 内恢复 v1 内容，产生 R1，版本仍为 v2
→ 再次检查并接受 v2
→ 提取 PendingMemory
→ 发布 locked
→ 验证任何修改、恢复和创建版本均被拒绝
```

### 12.4 工程基线

Phase 4 实施开始时先完成：

- 后端确定性测试统一注入 Fake 生成器和 Fake 门禁 Agent。
- 真实 DeepSeek 测试使用独立 integration 标记和命令。
- 默认 `.venv/bin/python -m pytest tests/ -x -q` 不访问外部网络。
- 后端开发和测试环境固定为 Python 3.12。
- Phase 1–3 的确定性测试、前端单测、类型检查、lint 和构建继续通过。

## 13. 非目标

Phase 4 不包含：

- 每次 AI 调用或每次应用候选都创建新版本。
- 多个 ReviewIssue 的批量合并修复。
- 草稿版本分支与合并。
- 实时多人协作。
- 已发布 `locked` 章节回滚或重写。
- 接受章节后的版本续写和 PendingMemory 失效重算。
- 默认整章重写。
- AI 自动应用修改。
- 每次键盘输入自动保存版本。
- Phase 5 向量检索和高级 RAG。
- 多 Agent 并发修改同一草稿。

## 14. Phase 4 完成标准

Phase 4 完成必须同时满足：

1. 作者能从 ReviewIssue 获取真实修改方向，并生成不直接生效的候选。
2. 作者能查看差异和修改理由，再决定应用或拒绝。
3. AI 自动优化和局部修复只记录为当前版本内部修订，不污染作者可见版本号。
4. 只有作者显式创建新版本时版本号才递增。
5. 当前版本内的手动编辑和历史恢复都有可追踪记录。
6. 过期候选、扩大范围、事务失败和 locked 章节不会导致错误覆盖。
7. 作者能完成“生成 → 检查 → 局部修改 → 确认 → 记忆提取”的完整闭环。
8. 默认确定性测试可离线运行，真实 AI 验证独立记录。
