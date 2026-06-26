# Novel Agent 阶段 1 人工记忆闭环设计

> 日期：2026-06-26  
> 状态：待评审  
> 范围：补齐需求文档第一阶段的“章节编辑 + 基础记忆”能力，不引入 AI 自动提取、多 Agent、RAG 或一致性检查。

## 1. 背景

需求文档第一阶段的目标是让系统围绕章节编辑运转，并保存基础结构化信息。当前系统已经完成用户认证、小说 CRUD、章节 CRUD、基础章节编辑页、小说列表页和小说详情页，但还缺少阶段 1 的基础记忆数据结构和人工维护界面。

本设计选择“阶段 1 人工管理闭环”作为下一步：先补齐小说元信息、章节摘要、章节状态、角色卡片和世界观设定，让作者可以稳定维护长期创作资料。AI 自动摘要、待确认记忆区、伏笔管理、上下文自动检索和一致性检查都放到后续阶段。

## 2. 目标

- 小说项目支持 `genre` 和 `style_guide`，用于记录类型和写作风格指南。
- 章节支持 `summary` 和 `status`，用于保存手动摘要和章节状态。
- 支持手动维护角色卡片，包含叙事功能、世界内身份、性格、动机、说话方式、行为边界和当前状态。
- 支持手动维护世界观设定，包含标题、分类和正文内容。
- 前端提供围绕单本小说的“章节 / 角色 / 设定”工作区入口。
- 保持现有后端分层架构和前端 Vue + Pinia 结构，不引入额外复杂架构。

## 3. 非目标

- 不做 AI 自动摘要或自动记忆提取。
- 不做“待确认记忆区”。
- 不做伏笔生命周期管理。
- 不做上下文自动检索或上下文包生成。
- 不做一致性检查或自动修复。
- 不强制实现章节锁定后的禁止编辑。
- 不做复杂知识图谱、标签体系或全文向量检索。

## 4. 数据模型

### 4.1 Novel 扩展

现有 `Novel` 保持主表职责，新增两个字段：

```ts
{
  id: number
  user_id: number
  title: string
  description?: string | null
  genre?: string | null
  style_guide?: string | null
  created_at: string
  updated_at: string
}
```

`genre` 用于小说类型，例如“古风权谋”“都市悬疑”“仙侠成长”。`style_guide` 用于记录叙事视角、文风、节奏、禁用表达等长期写作偏好。

### 4.2 Chapter 扩展

现有 `Chapter` 新增摘要和状态：

```ts
{
  id: number
  novel_id: number
  title: string
  content: string
  summary: string
  status: "draft" | "reviewed" | "locked"
  created_at: string
  updated_at: string
}
```

`summary` 由用户手动填写，记录本章关键事实。`status` 与需求文档保持一致，后端默认值为 `draft`：

| 状态 | 含义 |
|---|---|
| `draft` | 草稿 |
| `reviewed` | 已确认 |
| `locked` | 锁定 |

第一阶段中 `locked` 只作为状态记录，不禁止编辑。

### 4.3 CharacterProfile

新增角色卡片表，绑定到小说：

```ts
{
  id: number
  novel_id: number
  name: string
  story_role: string
  identity: string
  personality: string
  motivation: string
  speech_style: string
  behavior_rules: string[]
  current_state: string
  created_at: string
  updated_at: string
}
```

字段语义：

| 字段 | 说明 |
|---|---|
| `name` | 角色名 |
| `story_role` | 角色在故事结构中的叙事功能，例如主角、反派、导师、盟友、误导角色 |
| `identity` | 角色在世界内的身份或职业，例如皇女、捕快、刺客、宗门弟子 |
| `personality` | 性格特征 |
| `motivation` | 当前动机和目标 |
| `speech_style` | 说话方式的约束规则，不只是口头禅 |
| `behavior_rules` | 行为边界，例如“不会主动背叛朋友” |
| `current_state` | 当前剧情阶段下的心理、关系、目标或处境 |

`speech_style` 的设计哲学是记录角色对话生成和检查时需要遵守的约束，例如句子长度、语气、用词、情绪表达方式、禁忌表达和典型句式。

`behavior_rules` 使用 JSON 字段保存字符串数组。后端 schema 接收数组，前端表单用多行文本编辑，提交前按行拆分。

### 4.4 WorldSetting

新增世界观设定表，绑定到小说：

```ts
{
  id: number
  novel_id: number
  title: string
  category: "geography" | "faction" | "rule" | "history" | "culture" | "other"
  content: string
  created_at: string
  updated_at: string
}
```

分类固定为第一阶段够用的基础分类：

| 分类 | 含义 |
|---|---|
| `geography` | 地理、地点、区域 |
| `faction` | 势力、组织、家族 |
| `rule` | 规则、力量体系、制度 |
| `history` | 历史、旧事、传说 |
| `culture` | 风俗、语言、礼法、生活方式 |
| `other` | 其他设定 |

后端使用字符串校验，不使用数据库 enum，避免后续扩展分类时必须迁移数据库枚举。

## 5. 后端 API

后端继续使用现有路径风格和统一响应格式。所有子资源访问都必须校验小说属于当前用户。

### 5.1 现有 API 扩展

```text
GET    /api/v1/novels
POST   /api/v1/novels
GET    /api/v1/novels/{novel_id}
PUT    /api/v1/novels/{novel_id}

POST   /api/v1/novels/{novel_id}/chapters
PUT    /api/v1/novels/{novel_id}/chapters/{chapter_id}
```

小说 create/update schema 增加 `genre` 和 `style_guide`。章节 create/update schema 增加 `summary` 和 `status`。

### 5.2 角色 API

```text
GET    /api/v1/novels/{novel_id}/characters
POST   /api/v1/novels/{novel_id}/characters
GET    /api/v1/novels/{novel_id}/characters/{character_id}
PUT    /api/v1/novels/{novel_id}/characters/{character_id}
DELETE /api/v1/novels/{novel_id}/characters/{character_id}
```

### 5.3 设定 API

```text
GET    /api/v1/novels/{novel_id}/settings
POST   /api/v1/novels/{novel_id}/settings
GET    /api/v1/novels/{novel_id}/settings/{setting_id}
PUT    /api/v1/novels/{novel_id}/settings/{setting_id}
DELETE /api/v1/novels/{novel_id}/settings/{setting_id}
```

### 5.4 后端分层

实现继续沿用现有结构：

```text
api -> service -> repository -> model
```

建议新增文件：

```text
backend/app/models/memory.py
backend/app/schemas/memory.py
backend/app/repositories/memory_repo.py
backend/app/services/memory_service.py
backend/app/api/memory.py
```

也可以将角色和设定拆成 `characters.py` 与 `settings.py`，但第一阶段二者都属于手动基础记忆，合并为 `memory` 模块更集中。

## 6. 前端页面与流程

### 6.1 路由

新增围绕单本小说的工作区路由：

```text
/novels/:id                     # 章节列表与预览
/novels/:id/edit/:chapterId     # 章节编辑
/novels/:id/characters          # 角色管理
/novels/:id/settings            # 世界观设定管理
```

### 6.2 小说工作区导航

不扩展全局侧边栏为复杂菜单。进入某本小说后，在小说详情、角色页、设定页顶部显示工作区导航：

```text
章节 | 角色 | 设定
```

这样阶段 1 的管理能力都围绕当前小说展开。

### 6.3 小说创建与编辑

小说创建表单增加：

- `genre`：单行输入。
- `style_guide`：多行输入。

当前系统尚无小说编辑页或编辑弹窗。阶段 1 可以在小说详情页提供“编辑小说信息”入口，用弹窗维护 `title`、`description`、`genre`、`style_guide`。

### 6.4 章节编辑

章节编辑器新增：

- `status`：顶部下拉选择。
- `summary`：正文下方的多行摘要输入框。

保存时与 `title`、`content` 一起调用现有章节 update API。第一阶段不做自动保存，仍由用户点击保存或使用现有快捷键保存。

### 6.5 角色管理页

角色页采用卡片列表加 `AppModal` 表单。新建和编辑共用同一个表单，删除使用现有 `AppConfirm`。字段输入方式：

| 字段 | 输入方式 |
|---|---|
| `name` | 单行输入 |
| `story_role` | 单行输入 |
| `identity` | 单行输入 |
| `personality` | 多行文本 |
| `motivation` | 多行文本 |
| `speech_style` | 多行文本 |
| `behavior_rules` | 多行文本，按行拆分为数组 |
| `current_state` | 多行文本 |

### 6.6 设定管理页

设定页采用列表、分类筛选和 `AppModal` 表单。新建和编辑共用同一个表单，删除使用现有 `AppConfirm`。字段输入方式：

| 字段 | 输入方式 |
|---|---|
| `title` | 单行输入 |
| `category` | 下拉选择 |
| `content` | 多行文本 |

## 7. 前端模块边界

### 7.1 类型

更新：

```text
frontend/src/types/novel.ts
```

新增：

```text
frontend/src/types/memory.ts
```

`memory.ts` 包含 `CharacterProfile`、`WorldSetting` 及对应 create/update 类型。

### 7.2 API

保留：

```text
frontend/src/api/novels.ts
```

新增：

```text
frontend/src/api/memory.ts
```

`memory.ts` 负责角色和设定 API，避免 `novels.ts` 继续膨胀。

### 7.3 Store

保留：

```text
frontend/src/stores/novels.ts
```

新增：

```text
frontend/src/stores/memory.ts
```

`novels.ts` 管理小说和章节。`memory.ts` 管理角色卡和世界观设定。

## 8. 数据流

阶段 1 的核心使用流程：

```text
创建小说，填写类型和风格指南
创建角色卡和世界观设定
创建章节
写正文
手动填写章节摘要
标记章节状态
进入下一章时人工查看角色、设定、上一章摘要
```

后续阶段可以在这个基础上加入自动摘要、待确认记忆、上下文检索和检查 Agent。

## 9. 错误处理与权限

- 后端继续使用 `AppException` 和统一响应格式。
- 获取角色或设定前必须先校验 `novel_id` 属于当前用户。
- 子资源不存在或不属于当前小说时返回 `NotFound`。
- 子资源属于其他用户小说时不暴露存在性，优先返回“小说不存在”或“资源不存在”。
- 前端沿用现有 axios 拦截器处理 401。

## 10. 数据迁移

新增 Alembic migration，不修改旧的 initial migration。

迁移内容：

- `novels` 表新增 `genre`、`style_guide`。
- `chapters` 表新增 `summary`、`status`，默认值分别为 `""` 和 `"draft"`。
- 新增 `character_profiles` 表。
- 新增 `world_settings` 表。

## 11. 测试与验证

### 11.1 后端

新增后端自动化测试，覆盖：

- 创建小说时保存 `genre`、`style_guide`。
- 创建和更新章节时保存 `summary`、`status`。
- 创建、读取、更新、删除角色卡。
- 创建、读取、更新、删除世界观设定。
- 跨用户访问小说、角色、设定失败。

### 11.2 前端

验证命令：

```bash
npm run type-check
npm run build
```

当前 `frontend/src/__tests__/App.spec.ts` 和 `frontend/e2e/vue.spec.ts` 仍包含 Vite 默认断言，应更新为当前应用可通过的基础断言，避免测试继续检查不存在的默认文案。

## 12. 实施顺序建议

1. 后端模型和 migration。
2. 后端 schema、repository、service、API。
3. 前端类型和 API client。
4. 前端 Pinia store。
5. 小说创建/编辑和章节编辑字段扩展。
6. 角色管理页。
7. 设定管理页。
8. 测试和构建验证。

这个顺序先稳定数据契约，再接页面，能减少前端返工。
