# Novel Agent 阶段 2：AI 骨架 + 章节提取闭环

> 日期：2026-06-27  
> 状态：待评审  
> 范围：搭建 LangChain 1.x AI 骨架（LLM 连接、ReAct Agent 引擎、工具系统），实现章节记忆提取闭环（章节摘要、角色变化、剧情事实、新设定、伏笔候选），包含 PendingMemory 待确认区及完整前后端。

## 1. 背景

系统已完成阶段 1（章节编辑 + 人工记忆管理），但完全没有 AI 能力。阶段 2 的目标是：

1. 搭建 AI 基础设施层（LLM 连接、Agent 引擎、工具系统）
2. 实现每章写完后自动提取关键信息的能力
3. 提取结果先进入待确认区（PendingMemory），用户确认后写入正式记忆

AI 骨架使用 LangChain 1.3 + `langchain-deepseek`，任务按复杂度分两条路径。

## 2. 技术选型

| 组件 | 选择 | 版本 |
|------|------|------|
| AI 框架 | LangChain (create_agent / create_deep_agent) | 1.3.11 |
| LLM 标准 | DeepSeek V4 Flash | `deepseek-v4-flash` |
| LLM 深度 | DeepSeek V4 Pro | `deepseek-v4-pro` |
| Provider 包 | langchain-deepseek | 1.1.0 |
| Agent 状态 | AgentState + InMemorySaver | langgraph |
| 深度 Agent | deepagents | — |

## 3. 架构设计

```
用户请求 → FastAPI Router
                ↓
         Agent Factory
         ├─ create_novel_agent("flash")    → 摘要、提取
         └─ create_novel_deep_agent("pro") → 伏笔推理、深度分析
                ↓
    ┌─────────────────────────────┐
    │    ReAct Loop               │
    │    Think → Plan → Act →    │
    │    Observe → ... → End      │
    └─────────────────────────────┘
           ↓              ↑
    ┌────────────┐  ┌──────────┐
    │   Tools    │  │Middleware│
    │ get_chapter│  │ 日志追踪  │
    │ save_*     │  │ pending  │
    └─────┬──────┘  └──────────┘
          ↓
    Repository Layer (existing)
```

### 3.1 目录结构

```
backend/app/ai/
├── __init__.py
├── models.py              # AgentState 定义 (NovelAgentState)
├── config.py              # 模型常量定义 (FLASH_MODEL / PRO_MODEL)
├── tools/
│   ├── __init__.py
│   ├── context.py         # get_chapter_context 读取工具
│   └── memory.py          # save_* 写入工具（输出到 pending）
├── middleware/
│   ├── __init__.py
│   └── logging.py         # 日志中间件
├── agent.py               # create_novel_agent / create_novel_deep_agent 工厂
├── service.py             # 编排层：组装 prompt → 选 agent → 调用 → 返回
└── router.py              # FastAPI routes

backend/app/repositories/
└── pending_memory_repo.py # PendingMemory 读写

backend/app/models/
└── pending_memory.py      # PendingMemory ORM 模型

backend/app/schemas/
└── pending_memory.py      # Pydantic schemas

frontend/src/
├── types/pendingMemory.ts  # TypeScript 类型
├── api/pendingMemory.ts    # API 客户端
├── stores/pendingMemory.ts # Pinia store
└── views/novels/
    └── PendingConfirmView.vue  # 待确认确认/拒绝页面
```

## 4. 配置设计

`.env.example` 只保留真正需要用户配置的项：

```
DEEPSEEK_API_KEY=
```

`backend/app/ai/config.py` 中模型名由代码决定，不做环境配置：

```python
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"
```

`Settings` 类新增：

```python
DEEPSEEK_API_KEY: str = ""
```

测试环境：`conftest.py` 通过 `load_dotenv()` 加载 `.env`，`settings.DEEPSEEK_API_KEY` 全局可用。

## 5. Agent 设计

### 5.1 Agent 工厂

```python
def create_novel_agent(
    model_type: Literal["flash", "pro"] = "flash",
    tools: list[Tool] = [],
    system_prompt: str = "",
    state_schema: type[AgentState] | None = None,
    checkpointer: BaseCheckpointerSaver | None = None,
) -> Agent:
    model_name = FLASH_MODEL if model_type == "flash" else PRO_MODEL
    model = init_chat_model(model_name, model_provider="deepseek")
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
    )

def create_novel_deep_agent(
    tools: list[Tool] = [],
    system_prompt: str = "",
    state_schema: type[DeepAgentState] | None = None,
    checkpointer: BaseCheckpointerSaver | None = None,
) -> Agent:
    model = init_chat_model(PRO_MODEL, model_provider="deepseek")
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        state_schema=state_schema,
        checkpointer=checkpointer,
    )
```

### 5.2 Agent State

```python
class NovelAgentState(AgentState):
    novel_id: int
    chapter_id: int
    user_id: int
    pending_confirmations: list[dict] = []
```

### 5.3 任务与 Agent 映射

| 任务 | Agent 类型 | 模型 |
|------|-----------|------|
| 生成章节摘要 | `create_novel_agent("flash")` | Flash |
| 提取角色变化 | `create_novel_agent("flash")` | Flash |
| 提取剧情事实 | `create_novel_agent("flash")` | Flash |
| 提取新世界设定 | `create_novel_agent("flash")` | Flash |
| 提取伏笔候选 | `create_novel_deep_agent()` | Pro |
| 深层一致性分析 | `create_novel_deep_agent()` | Pro |

## 6. Tool 设计

### 6.1 读取工具

```python
@tool
def get_chapter_context(
    novel_id: int,
    chapter_id: int,
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """获取章节全文、已有角色设定、世界设定、伏笔信息"""
```

拼接后的上下文格式：

```
[章节标题]
{chapter.title}

[章节正文]
{chapter.content}

[已有角色]
{character.name}: {character.personality}, {character.current_state}
...

[已有设定]
{setting.title} ({setting.category}): {setting.content}

[已有伏笔]
{foreshadowing.name}: {foreshadowing.status}

[已有剧情事实]
{fact.content} (涉及: {fact.related_characters})
```

### 6.2 写入工具（全部写入 pending）

```python
@tool
def save_character_changes(
    changes: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录角色变化到待确认区。
    changes 格式: [{name, field, change_description, reason}]
    示例: [{name: "主角", field: "current_state", change_description: "得知身世真相后情绪崩溃", reason: "第5章揭露身世"}]
    """

@tool
def save_plot_facts(
    facts: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录剧情事实。
    facts 格式: [{event, characters_involved, importance}]
    """

@tool
def save_world_settings(
    settings: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录新世界观设定。
    settings 格式: [{title, category, content}]
    """

@tool
def save_foreshadowing_candidates(
    candidates: list[dict],
    runtime: ToolRuntime[None, NovelAgentState],
) -> str:
    """记录伏笔候选。
    candidates 格式: [{name, description, hint, expected_reveal_after_chapter}]
    """
```

## 7. 数据模型

### 7.1 PendingMemory

```python
class PendingMemory(Base):
    __tablename__ = "pending_memories"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    novel_id: int = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: int = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    memory_type: str = Column(String(50), nullable=False)
    # "character_change" | "plot_fact" | "world_setting" | "foreshadowing"
    content: dict = Column(JSON, nullable=False)
    status: str = Column(String(20), nullable=False, default="pending")
    # "pending" | "confirmed" | "rejected"
    created_at: datetime = Column(DateTime, nullable=False, default=func.now())
```

确认后（`confirmed`）的内容由以下逻辑写入对应正式表：

| memory_type | confirm 行为 |
|-------------|------------|
| `character_change` | 更新 CharacterProfile 对应字段（current_state、personality 等） |
| `world_setting` | 创建新的 WorldSetting 记录 |
| `plot_fact` | 创建新的 PlotFact 记录 |
| `foreshadowing` | 创建新的 Foreshadowing 记录 |

### 7.2 PlotFact

```python
class PlotFact(Base):
    __tablename__ = "plot_facts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    novel_id: int = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    chapter_id: int = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    fact_type: str = Column(String(50), nullable=False)
    # "event" | "relationship" | "location" | "item" | "knowledge"
    content: str = Column(Text, nullable=False)
    related_characters: list = Column(JSON, nullable=False, default=list)
    # 角色名数组，如 ["主角", "反派"]
    importance: str = Column(String(20), nullable=False, default="minor")
    # "major" | "minor"
    created_at: datetime = Column(DateTime, nullable=False, default=func.now())
```

### 7.3 Foreshadowing

```python
class Foreshadowing(Base):
    __tablename__ = "foreshadowings"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    novel_id: int = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    name: str = Column(String(200), nullable=False)
    planted_chapter_id: int = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    description: str = Column(Text, nullable=False)
    hidden_truth: str = Column(Text, nullable=False, default="")
    status: str = Column(String(20), nullable=False, default="planted")
    # "planted" | "developing" | "resolved"
    expected_reveal_chapter_id: int = Column(Integer, ForeignKey("chapters.id"), nullable=True)
    related_characters: list = Column(JSON, nullable=False, default=list)
    risk_warning: str = Column(Text, nullable=False, default="")
    created_at: datetime = Column(DateTime, nullable=False, default=func.now())
    updated_at: datetime = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
```

### 7.4 Alembic 迁移

新建迁移脚本，创建三张表：`pending_memories`、`plot_facts`、`foreshadowings`。

## 8. API 设计

### 8.1 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/novels/{novel_id}/chapters/{chapter_id}/extract` | 对章节运行 AI 提取 |
| `GET` | `/api/v1/novels/{novel_id}/pending-memories` | 获取待确认列表 |
| `PUT` | `/api/v1/novels/{novel_id}/pending-memories/{id}/confirm` | 确认单条 → 按 memory_type 写入对应正式表 |
| `PUT` | `/api/v1/novels/{novel_id}/pending-memories/{id}/reject` | 拒绝（删除）单条 |
| `PUT` | `/api/v1/novels/{novel_id}/pending-memories/batch` | 批量确认/拒绝 |

**confirm 写入逻辑**：根据 `pending_memory.memory_type` 分发
- `character_change` → 更新 `CharacterProfile` 中对应角色的 `current_state` 等字段
- `world_setting` → 创建 `WorldSetting` 记录
- `plot_fact` → 创建 `PlotFact` 记录
- `foreshadowing` → 创建 `Foreshadowing` 记录

**`POST /extract` 请求/响应：**

```json
// 请求
{ "mode": "standard" | "deep" }

// 响应
{
  "code": 0,
  "message": "ok",
  "data": {
    "chapter_summary": "本章主要讲述了...",
    "pending_ids": [1, 2, 3],
    "pending_count": 3
  }
}
```

### 8.2 前端页面

新增路由：

| 路径 | 组件 | 说明 |
|------|------|------|
| `/novels/:id/pending` | `PendingConfirmView.vue` | 待确认记忆列表 |

页面功能：

- 按 `memory_type` 分类展示待确认条目（角色变化 / 剧情事实 / 设定 / 伏笔）
- 每条显示：提取类型、内容摘要、来源章节
- 操作：确认 / 拒绝 / 批量确认 / 批量拒绝
- 状态切换：已确认/已拒绝的条目变为只读

**入口**：在 NovelWorkspaceTabs 中新增"待确认"标签，有未确认条目时显示 badge。

### 8.3 前端新增类型

```typescript
// types/pendingMemory.ts
interface PendingMemory {
  id: number
  novel_id: number
  chapter_id: number
  memory_type: 'character_change' | 'plot_fact' | 'world_setting' | 'foreshadowing'
  content: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: string
}

// types/plotFact.ts
interface PlotFact {
  id: number
  novel_id: number
  chapter_id: number
  fact_type: 'event' | 'relationship' | 'location' | 'item' | 'knowledge'
  content: string
  related_characters: string[]
  importance: 'major' | 'minor'
  created_at: string
}

// types/foreshadowing.ts
interface Foreshadowing {
  id: number
  novel_id: number
  name: string
  planted_chapter_id: number
  description: string
  hidden_truth: string
  status: 'planted' | 'developing' | 'resolved'
  expected_reveal_chapter_id: number | null
  related_characters: string[]
  risk_warning: string
  created_at: string
  updated_at: string
}
```

## 9. 测试设计

### 9.1 测试配置

`conftest.py` 在设置测试环境时增加 `.env` 加载：

```python
from dotenv import load_dotenv
load_dotenv()  # 加载 DEEPSEEK_API_KEY
```

测试类直接使用 `from app.core.config import settings; settings.DEEPSEEK_API_KEY`。

### 9.2 测试策略

**AI 能力测试**（调用真实 API）：
- `test_extract_chapter_basic` — 对已知章节运行提取，验证返回结构
- `test_extract_character_changes` — 验证角色变化提取
- `test_extract_plot_facts` — 验证剧情事实提取

### 9.3 AI API 调用约定

所有测试调用真实 DeepSeek API（不 mock），使用 `.env` 中配置的 `DEEPSEEK_API_KEY`，与生产环境保持一致。

## 10. 系统提示词设计

### 10.1 标准 Agent System Prompt

```
你是一个小说创作辅助 Agent，负责分析章节内容并提取结构化信息。

## 工作流程
1. 使用 get_chapter_context 工具获取章节内容和相关记忆
2. 分析内容，提取以下信息：
   - 角色变化（性格、动机、状态、关系的变化）
   - 剧情事实（本章发生的重要事件）
   - 世界观设定（新出现的地点、组织、规则）
   - 伏笔候选（看似普通但可能重要的信息）
3. 使用对应的 save_* 工具写入提取结果

## 规则
- 只提取本章有明确依据的信息，不要臆测
- 角色变化要有原文支撑
- 伏笔候选标注潜在的回收方向
- 完成后回复"提取完成"并总结提取条目数
```

### 10.2 Deep Agent System Prompt

在标准提示词基础上增加：

```
## 深度分析要求
- 分析伏笔之间的隐含关联
- 评估章节内容与已有设定的冲突点
- 标记可能被忽略的细节（可能发展为后续情节）
- 对角色行为的合理性给出判断
```

## 11. 未包含在本次范围的内容

- 上下文检索 / RAG（阶段 3）
- 一致性检查（阶段 4）
- 前端编辑器内的 AI 辅助写作
- 多 Agent 协作
- 复杂知识图谱
