# v2 Phase 2: Chapter Quality Gate Design

## 1. 设计目标

在 Phase 1 的写作闭环基础上，引入质量门禁系统，使 AI 草稿在进入编辑器前经过自动检查与修复，减少低质量草稿对作者的干扰。

## 2. 设计原则

- **能自动修的不问用户** — 有客观对错标准的问题，由系统自动修复并记录日志
- **需要意图才升级** — 只有涉及创作选择、风格偏好、角色发展方向等无客观对错的问题，才升级给用户辅助修复
- **辅助修复不阻塞** — 草稿直接进入编辑器，待处理项在右侧栏展示，用户写作时顺手处理
- **区域锁定防冲突** — 有待处理修复的正文区域设为只读，防止用户编辑与系统修复冲突

## 3. 流程总览

```
写作 Agent 完成 → 草稿写入 WritingRun
       ↓
   质量门禁入口 quality_gate(writing_run_id)
       ↓
   并行执行 6 个检查 Agent
   ┌────┬────┬────┬────┬────┬────┐
   │任务│风格│人设│世界观│伏笔│篇幅│
   │完成│可读│剧情│一致 │控制│内容│
   │度  │性  │连续│     │    │密度│
   └────┴────┴────┴────┴────┴────┘
       ↓
   汇总结果 → 分类处理
   ┌─────────────────────┐
   │ 自动修复              │
   │ → RepairLog 记录     │
   │ → 整章重写或局部替换   │
   ├─────────────────────┤
   │ 辅助修复（需要意图）    │
   │ → PendingRepair 创建 │
   └─────────────────────┘
       ↓
   WritingRun.status = "gated"
   草稿进入编辑器
   右侧栏加载 RepairLog + PendingRepair
```

## 4. 检查 Agent 设计

### 4.1 Agent 划分

| Agent | 检查范围 | 自愈方式 |
|-------|---------|---------|
| TaskAgent | 是否完成章节任务书的剧情/角色/情绪目标 | 整章重写 |
| StyleAgent | 是否偏离风格指南，是否有空泛/拖沓 | 整章重写 |
| CharContinuityAgent | 角色行为/知识越界、时间地点冲突 | 局部替换 |
| WorldAgent | 是否违反已确认世界观设定 | 局部替换 |
| ForeshadowAgent | 遗漏、提前揭露、重复解释、误导过度 | 局部替换 |
| LengthAgent | 是否达标、是否有效推进场景 | 整章重写（当前字数检查扩展） |

### 4.2 Agent 输出结构

每个 Agent 输出统一的 `CheckResult`：

```python
class CheckResult(BaseModel):
    passed: bool
    issue_type: str  # task_completion | style | character | continuity | world | foreshadowing | length
    severity: str    # "auto_fixable" | "needs_intent"

    # auto_fixable 时
    fix_strategy: str | None  # "full_rewrite" | "local_replace"
    fixed_text: str | None
    fix_description: str

    # needs_intent 时
    options: list[str] | None
    intent_type: str | None   # "choice" | "freeform"
    description: str
    location: str
    context: str
```

### 4.3 自动修复策略

- **整章重写 (full_rewrite)** — 将问题描述作为反馈，重新调用写作 Agent 生成整章，替换 `WritingRun.draft_content`
- **局部替换 (local_replace)** — 只替换出问题的段落/句子，其余内容不动
- 每种修复均创建 `RepairLog` 记录

## 5. 数据模型

### 5.1 RepairLog（自动修复记录）

```python
class RepairLog(Base):
    novel_id: int           # FK to novel
    writing_run_id: int     # FK to writing_run
    issue_type: str
    description: str        # "人设修正：角色XXX的对话超出知识范围"
    location: str            # 正文中的位置描述
    old_text: str            # 原文摘要（截取前200字）
    new_text: str            # 修改后摘要
    created_at: datetime
```

用户不需要操作 RepairLog，只在侧栏折叠展示，可展开查看详情。

### 5.2 PendingRepair（待处理修复项）

```python
class PendingRepair(Base):
    novel_id: int
    chapter_id: int
    writing_run_id: int
    issue_type: str  # character_choice | expression | direction
    description: str
    location: str     # 正文中的位置（用于前端定位和区域锁定）
    context: str      # 问题所在的正文片段
    options: list[RepairOption] | None
    intent_type: str  # "choice" | "freeform"
    status: str       # "pending" | "applied" | "dismissed"
    created_at: datetime
```

```python
class RepairOption(BaseModel):
    label: str    # "方案A：保留当前写法"
    summary: str  # "角色表现果断，强化其领导者形象"
```

### 5.3 WritingRun 扩展

在 `WritingRun` 中增加字段：

```python
class WritingRun(Base):
    # ... 现有字段
    gated: bool = False                 # 是否已通过质量门禁
    has_pending_repairs: bool = False   # 是否有待处理修复项
```

## 6. 编辑器布局与交互

### 6.1 布局变更

EditorView 从单列居中改为两栏布局：

```
┌──────────────────────────────────────────────┐
│  header（保持不变）                           │
├──────────────────────────┬───────────────────┤
│                          │  修复侧栏           │
│   编辑器正文              │  ┌──────────────┐ │
│   max-width: 660px       │  │ 自动修复日志   │ │
│   居左                    │  │ (折叠区域)     │ │
│                          │  ├──────────────┤ │
│   有待处理修复的区域       │  │ 待处理修复     │ │
│   灰底只读                │  │ ┌──────────┐ │ │
│                          │  │ │ 角色抉择  │ │ │
│                          │  │ │ ○ 方案A   │ │ │
│                          │  │ │ ○ 方案B   │ │ │
│                          │  │ │ [应用]    │ │ │
│                          │  │ └──────────┘ │ │
│                          │  │ ┌──────────┐ │ │
│                          │  │ │ 表达方式  │ │ │
│                          │  │ │ [输入意图]│ │ │
│                          │  │ │ [按意图修]│ │ │
│                          │  │ └──────────┘ │ │
│                          │  └──────────────┘ │
└──────────────────────────┴───────────────────┘
```

### 6.2 区域锁定机制

- `PendingRepair.location` 记录正文中问题的起止位置（行号/字符偏移）
- 前端据此将对应区域渲染为灰底只读块，显示标记
- 处理完成（`applied` / `dismissed`）后锁定解除，恢复正常编辑
- 未锁定区域正常可编辑

### 6.3 修复交互

- `intent_type = "choice"` → 显示选项（el-radio-group），用户选择后点击"应用"
- `intent_type = "freeform"` → 显示输入框（el-input），用户填写意图后点击"按意图修复"
- 提交后调 API：`PUT /api/v1/writing/repairs/{id}/resolve`
  - body: `{"action": "apply", "choice_index": 0}` 或 `{"action": "apply", "intent_text": "...",}`
- 后端执行修复并更新 `PendingRepair.status = "applied"`

## 7. API 设计

### 7.1 新增路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/writing/runs/{run_id}/repairs` | 获取 WritingRun 的所有修复项（含 RepairLog + PendingRepair） |
| GET | `/api/v1/writing/runs/{run_id}/repairs/pending` | 仅获取待处理修复项 |
| PUT | `/api/v1/writing/repairs/{id}/resolve` | 处理一条待处理修复项 |

### 7.2 质量门禁自动触发

质量门禁在写作流程中自动触发，无独立 API：

```
POST /api/v1/writing/runs → 创建 WritingRun → 调用 writing_agent → quality_gate
```

`quality_gate` 函数在 `WritingService` 中作为 `create_run` 的内部步骤调用。

## 8. 前端变更

### 8.1 新增文件

- `frontend/src/api/writing.ts` — 扩展 writing API client，增加 `getRepairs` / `resolveRepair`
- `frontend/src/stores/writing.ts` — 扩展 writing store，增加 `repairs` / `pendingRepairs`
- `frontend/src/components/writing/RepairSidebar.vue` — 修复侧栏组件
- `frontend/src/components/writing/RepairItem.vue` — 单条修复项组件（自动修复/待处理两种模式）
- `frontend/src/types/writing.ts` — 扩展类型定义

### 8.2 组件结构

```
WritingEditor.vue
  ├── .writing-editor__header（不变）
  ├── .writing-editor__body（改为 flex row）
  │   ├── .writing-editor__content（编辑器正文，居左）
  │   └── RepairSidebar.vue
  │       ├── RepairLogSection（自动修复日志，折叠）
  │       └── PendingRepairSection
  │           └── RepairItem.vue × N
  │               ├── 待处理类型："choice" → el-radio-group
  │               └── 待处理类型："freeform" → el-input
```

### 8.3 设计风格

- 使用现有 SCSS 变量 (`@use '@/styles/variables' as *`)
- 侧栏宽 320px，背景 `$color-bg-card`，左边框 `$color-border`
- 自动修复日志标题行使用 `$color-text-secondary`
- 待处理修复项卡片使用 `el-card shadow="never"` + 自定义 padding
- 锁定的正文区域使用 `$color-bg-secondary` 背景 + 虚线边框
- 按钮风格保持现有 `size="small" type="primary"` 模式

## 9. 错误处理与边界情况

- 质量门禁失败（某个 Agent 超时/报错）→ 不影响写作流程，草稿直接进入编辑器，`WritingRun.gated = False`
- 自动修复后字数不达标 → 再触发一次字数检查迭代
- PendingRepair 提交后修复失败 → 显示错误提示，保留原待处理项
- 用户手动编辑了锁定区域周边 → 不影响锁定区域内容
- 用户废弃草稿 → 自动清理关联的 RepairLog 和 PendingRepair

## 10. 不做的事（明确排除）

- 不做自动修复的版本管理与回退（后续阶段处理）
- 不做自动修复的用户确认流程（自动修复默认生效）
- 不做修复项批量处理（每条手动处理）
- 不做写作运行之间的修复传递（每次运行独立检查）
