# Novel Agent Phase 5：高级上下文与可追溯检索设计

> 日期：2026-07-16
> 状态：已与作者确认，等待规格审阅
> 范围：为长篇写作加入云端向量检索、Qdrant 索引、重排、风险守卫和不可变来源快照；不重做已完成的 Phase 6 作者工作台。

## 1. 背景与目标

当前 `ContextPackageService` 会把所有已锁定章节、角色、设定、剧情事实和伏笔直接装入上下文包。小说变长后，这种全量注入会带来三类问题：上下文成本随章节数线性增长、真正相关的早期细节被淹没、伏笔和设定的冲突无法在生成前被有针对性地拦截。

Phase 6 已经完成作者工作台，并固定了来源展示的边界：作者从某条 AI 消息打开“查看来源”时，看到的必须是该次生成实际使用的资料，而不是此刻重新搜索出的结果。Phase 5 为该工作台提供真实的检索和来源快照，但不改变其三栏布局、会话模型或交互方式。

目标：

1. 在长篇后期，按当前任务检索相关章节、角色历史、剧情事实和世界设定，而不是全量塞入提示词。
2. 将可能提前泄露的伏笔和设定冲突作为独立的守卫上下文，在生成和质量检查前给出明确约束。
3. 每次生成把入选来源冻结到 `WritingRun.context_snapshot_json.source_items`，供 Studio 的既有来源面板稳定读取。
4. 索引失败、模型服务不可用或资料尚未入库时，不阻断写作；退回当前结构化上下文并留下可观测诊断。
5. 数据库仍是唯一事实来源；Qdrant 仅是可删除、可重建的派生索引。

## 2. 已确认的技术决策

| 决策 | 选择 | 原因 |
| --- | --- | --- |
| 向量数据库 | Qdrant，Docker 单节点部署 | 本地资源占用低、过滤与混合检索能力成熟，后续可无痛迁移到托管实例。 |
| 嵌入与重排 | 阿里云百炼 Model Studio：`text-embedding-v4`、`qwen3-rerank` | 采用云端模型，避免当前电脑承担本地模型推理。 |
| 向量形态 | 1024 维稠密向量 + 稀疏向量 | 语义召回与专有名词/人名/地名精确命中兼顾。 |
| 集合划分 | 每个嵌入版本一个共享集合 | 避免“小集合爆炸”；以小说租户键严格过滤。 |
| 隔离键 | `tenant_key = "{user_id}:{novel_id}"` | 每一条 Qdrant 查询都强制加该过滤条件，防止跨小说命中。 |
| 索引方式 | 事务提交后写入持久化索引任务，由独立 worker 异步执行 | 不让作者保存/发布章节等待嵌入；失败可重试，服务重启不丢任务。 |

不引入本地 embedding、Redis、Celery 或第二套业务数据存储。

## 3. 系统边界与整体数据流

```text
MySQL / SQLite（小说、章节、记忆、设定、伏笔）
  │  提交业务修改后标脏
  ▼
retrieval_index_jobs（持久化任务）
  │
  ▼
Retrieval Index Worker
  ├─ 读取并规范化业务资料
  ├─ Model Studio text-embedding-v4
  └─ upsert / delete → Qdrant novel-context-v1

作者请求生成草稿
  │
  ▼
ContextPackageService
  ├─ 构造任务查询
  ├─ Qdrant 稠密 + 稀疏召回（tenant_key 过滤）
  ├─ qwen3-rerank、去重与配额
  ├─ 写作上下文 + 风险守卫上下文
  └─ ContextPackage.package_json
         │
         └─ WritingRun.context_snapshot_json（冻结 source_items）
                    │
                    └─ Phase 6 “查看来源”
```

Qdrant 从不承担授权判断或业务真相：每次操作仍先验证小说归属；检索结果只作为候选，最终正文、角色、设定和伏笔均回到关系型数据库按 `source_id` 重新核验。删除小说或重建索引不影响业务资料。

## 4. Qdrant 集合和资料模型

### 4.1 集合

首个集合命名为 `novel-context-v1`。`v1` 表示嵌入模型、维度、分块规则和 payload 结构的组合版本，而非小说版本。升级嵌入模型或改变不可兼容的分块方式时，新建 `novel-context-v2`，完成全量回填并切换应用配置；旧集合只在验证后删除。

集合包含以下命名向量：

```text
dense   # 1024 维，Cosine 距离，来自 text-embedding-v4
sparse  # 稀疏向量，来自 text-embedding-v4
```

为 `tenant_key`、`source_type`、`source_record_id`、`chapter_id`、`visibility` 和 `index_version` 建立 payload 索引。所有查询必须把 `tenant_key` 放入 Qdrant filter；服务层不得接受客户端传入的 tenant key。

Docker 仅暴露本机回环地址并使用持久卷：

```text
127.0.0.1:6333 -> qdrant:6333
qdrant_storage -> /qdrant/storage
```

生产环境通过内网 URL 连接 Qdrant，不将 6333 暴露到公网。应用通过环境变量配置 URL、集合名、Model Studio 密钥和模型名；密钥不进入 Git、日志、快照或前端。

### 4.2 Point payload

每个 point 的 ID 是由 `tenant_key + source_id + content_hash + index_version` 得到的确定性 UUID。同一资料重新索引会幂等覆盖；资料删除或状态变为不可检索时，worker 删除它的全部 point。

```json
{
  "tenant_key": "42:18",
  "source_id": "chapter:331:scene:2",
  "source_type": "chapter_scene",
  "source_record_id": 331,
  "chapter_id": 331,
  "chunk_index": 2,
  "title": "第 331 章 · 第 2 场",
  "text": "供嵌入与提示词使用的规范化资料正文",
  "visibility": "writer",
  "content_hash": "sha256:...",
  "index_version": "v1",
  "updated_at": "2026-07-16T10:00:00+08:00"
}
```

`text` 是可再生副本，不能绕过关系型数据库成为编辑入口。所有 `source_id` 都必须能定位到稳定的业务主键和位置，不以易变标题作为定位依据。

### 4.3 可索引资料与分层

| 来源 | point 类型 | 规则 | 默认可见性 |
| --- | --- | --- | --- |
| 已锁定章节摘要 | `chapter_summary` | 每章一条，用于宽召回和时间线定位 | `writer` |
| 已锁定章节正文 | `chapter_scene` | 按自然段/场景切分，约 700 个中文字符，约 120 字符重叠 | `writer` |
| 角色档案及其状态 | `character_profile` | 一角色一条，含身份、动机、行为规则、当前状态 | `writer` |
| 已确认剧情事实 | `plot_fact` | 一条事实一条索引，保留关联角色和来源章节 | `writer` |
| 世界观设定 | `world_setting` | 一条设定一条索引，保留类别 | `writer` |
| 伏笔表层线索 | `foreshadowing_signal` | 名称、描述、状态，不含隐藏真相 | `writer` |
| 伏笔和禁区风险 | `foreshadowing_guard` | `hidden_truth`、风险提示、预计揭示章节，只供守卫使用 | `guard` |

只有 `locked` 章节进入 canonical 章节检索。草稿、WorkingCopy、未确认记忆和 AI 输出候选不进检索，避免把未定内容错误写成世界事实。章节发布、角色/设定 CRUD、PendingMemory 确认，以及剧情事实或伏笔的变化均会使对应小说进入待索引状态。

## 5. 异步索引与重建

### 5.1 持久化任务

新增 `retrieval_index_jobs`，关键字段为：

| 字段 | 用途 |
| --- | --- |
| `novel_id` | 需要同步的小说 |
| `operation` | `sync`、`rebuild` 或 `purge` |
| `status` | `pending`、`running`、`retry_wait`、`completed`、`failed` |
| `attempt_count`、`next_attempt_at` | 有界指数退避重试 |
| `lease_expires_at` | worker 中断后可回收的任务租约 |
| `last_error` | 脱敏的运维错误摘要 |
| `requested_at`、`completed_at` | 状态和可观测性 |

每次业务提交成功后只入队，不做同步 embedding。短时间内同一本小说的多个 `sync` 任务会被 worker 合并为一次“按当前数据库完整同步”的工作，因此重复入队安全且不会出现旧任务覆盖新资料的问题。任务取得使用租约；异常后按退避重试，超过上限保留 `failed` 供手工重试。

独立命令 `python -m app.retrieval.worker` 轮询并执行任务；部署时作为与 API 进程分离的 worker 服务运行。开发环境可手动运行该命令。应用 API 进程不依赖内存 BackgroundTask 来保证投递，因此重启不会吞掉任务。

### 5.2 重建、删除与健康检查

- `rebuild`：从业务数据库枚举某本小说的 canonical 来源，生成新 point 后清理不再存在的该 `tenant_key` point。
- `purge`：删除小说时先入队；若数据库已级联删除，任务仍可按已保存 tenant key 清理。数据库删除失败时不执行 purge。
- 提供受所有权保护的索引状态和重建 API，便于作者确认“待同步 / 同步中 / 已同步 / 需重试”；Studio 正文区不展示技术指标。
- worker 启动与健康检查验证 Qdrant collection、Model Studio 配置和写入权限；这些故障进入日志和任务错误，不能包含 API key 或正文。

## 6. 检索、重排与上下文组装

### 6.1 查询输入

`ContextPackageService` 根据作者输入、章节任务书、章节计划、当前剧情单元、目标字数和最近章节摘要构造确定性的检索查询。模型不会直接决定 Qdrant 的过滤条件、租户键或风险可见性。

保留当前结构化锚点：作者基础设定、当前章节任务书、当前计划/剧情单元、最近章节摘要和文风指南。Phase 5 仅将原来“全量历史资料”替换为按任务检索出的资料。

### 6.2 混合检索管线

```text
任务查询
  → text-embedding-v4 生成 dense + sparse 查询向量
  → Qdrant dense / sparse 各召回候选（tenant_key + visibility 过滤）
  → RRF 融合
  → qwen3-rerank 重排前 N 条
  → 去重、每种来源配额、Token 预算裁剪
  → writer_context / guard_context / source_items
```

初版候选数和上下文预算由配置控制，默认：稠密/稀疏各取 24 条、融合后取 20 条重排、写作上下文最多 10 条、守卫上下文最多 6 条。为避免一章正文淹没全部结果，最终选择每个章节至多 2 个场景、每种原子记忆至少保留 1 个机会，并优先保留高重要度剧情事实和世界规则。

### 6.3 两类上下文

**写作上下文**供起草和修订模型直接使用，包含相关章节片段、角色、剧情事实、世界设定和伏笔表层线索。它不会包含 `hidden_truth` 或原始风险提示，避免模型因“知道秘密”而过早写出谜底。

**风险守卫上下文**只供生成前约束和质量门禁使用，包含伏笔真相、禁区和可能冲突的规则。它输出面向写作模型的最小化约束，例如“本章不可确认某角色已知账册去向”，不把不必要的剧透原文注入正文生成提示词。

若当前计划明确进入预计揭示章节，守卫可按照计划状态将必要信息提升为写作上下文；该提升必须记录在诊断和来源原因中。

### 6.4 失败与降级

| 失败点 | 行为 |
| --- | --- |
| Qdrant 不可用、集合不存在、无索引或索引仍待处理 | 使用已有结构化锚点与最近章节摘要生成；快照记录 `retrieval_status: fallback`。 |
| Model Studio embedding 或 rerank 超时 | 不等待无限重试；同样退化为结构化上下文，并让索引/运行诊断可见。 |
| 单条 point 损坏或原始资料不存在 | 丢弃该候选、记录诊断，继续使用其余候选。 |
| 风险守卫无结果 | 不阻断写作，但质量门禁按现有规则继续执行。 |

降级不会假装“已经检索到来源”；Studio 显示的来源只包含本次实际进入上下文的结构化锚点或检索项，并标注作者可理解的原因。

## 7. 不可变来源快照与 Phase 6 契约

每个 ContextPackage 记录当次检索资料；创建 WritingRun 时，不论是否经过 Phase 3 的计划路径，都将最终来源快照复制进 `WritingRun.context_snapshot_json`。完成的 run 永不从 Qdrant 或最新 ContextPackage 回查来源。

快照的作者展示部分严格保持 Phase 6 已有服务的模型：

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
  "diagnostics": {
    "retrieval_status": "retrieved",
    "index_version": "v1",
    "candidates": []
  }
}
```

`source_items` 只放作者需要理解和追溯的内容；稠密分、稀疏分、RRF 分、重排分、Token 估算和降级原因仅放入 `diagnostics`。默认来源面板不展示这些技术分数，开发诊断可按现有折叠区域读取。Phase 5 会同时校正 Studio 前端类型，使其与后端既有的 `StudioSourceOut`（`source_id`、`locator` 等）一致，不能另造一套来源字段。

来源必须可以定位到原始资料。后续“查看原文”动作按 `source_type + locator` 读取业务 API，重新执行小说所有权验证；绝不把 Qdrant point ID 或未授权正文直接暴露给浏览器。

## 8. 服务、配置与 API 边界

建议新增边界：

```text
app/retrieval/model_studio.py        # embedding / rerank provider 协议与生产客户端
app/retrieval/qdrant_store.py        # collection 初始化、upsert、delete、hybrid search
app/retrieval/source_builder.py      # 关系型资料 → 可索引 RetrievalSource
app/retrieval/indexer.py             # 单小说同步、哈希、清理与任务执行
app/retrieval/service.py             # 上下文检索、重排、配额和快照投影
app/retrieval/worker.py              # 持久化任务 worker 入口
app/models/retrieval.py              # RetrievalIndexJob
app/services/retrieval_index_service.py # 入队、状态、重建与所有权校验
```

`ContextPackageService` 只调用检索服务并接收已裁剪的领域对象，不直接了解 Qdrant SDK 或 Model Studio HTTP 细节。`WritingService` 负责将所有路径的来源快照写入 WritingRun。业务写服务在成功提交后调用 `RetrievalIndexService.enqueue_sync()`；不会让 repository 直接依赖向量数据库。

配置新增但不赋予默认密钥：

```text
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=novel-context-v1
MODEL_STUDIO_API_KEY=
MODEL_STUDIO_EMBEDDING_MODEL=text-embedding-v4
MODEL_STUDIO_RERANK_MODEL=qwen3-rerank
RETRIEVAL_ENABLED=true
```

新增嵌套 API：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/novels/{novel_id}/retrieval-index` | 返回该小说最近索引状态（不含密钥与正文）。 |
| `POST` | `/api/v1/novels/{novel_id}/retrieval-index/rebuild` | 入队全量重建；重复请求幂等合并。 |

既有 `POST /context-packages/generate`、写作运行和 Studio 来源 API 不改变路径。它们通过增强后的 ContextPackage 自动获得检索能力。

## 9. 安全、成本与并发

- 每个 Qdrant 查询均同时经过业务所有权验证和 `tenant_key` 过滤；单独任一层都不视为充分隔离。
- 快照只记录实际送入生成/守卫的最小资料片段，避免把整章正文复制到长期运行记录中。
- 指数退避、批量 embedding、内容哈希跳过未变化 point、任务合并和候选预算控制云端调用成本。
- worker 采用任务租约，保证多 worker 部署时同一任务不会被长期重复执行；point 以稳定 ID upsert，重复执行仍然安全。
- 新索引绝不改写已完成 WritingRun 的快照；资料发生变更只影响未来的上下文包。
- 测试通过 fake embedding、fake rerank 和内存 Qdrant adapter 覆盖确定性行为；真实 Model Studio/Qdrant 冒烟测试单独显式执行，不在单元测试中消耗云端额度。

## 10. 测试与验收

### 后端

- 模型与迁移：索引任务可创建、租约回收、失败退避、任务合并和重建。
- source builder：章节分场景稳定、角色/设定/事实/伏笔映射正确，未锁定章节和未确认记忆不入索引。
- 安全：不同用户或小说的 `tenant_key` 永不可交叉召回；删改资料后旧 point 被清理。
- 检索：稠密+稀疏融合、重排、去重、来源配额、Token 预算和 writer/guard 分流均由 fake provider 验证。
- 降级：Qdrant、embedding 或 rerank 失败时 ContextPackage 和 WritingRun 仍可创建，并明确记录 fallback。
- 快照：所有创建 WritingRun 的路径冻结相同来源合同；之后重建索引或修改资料不改变历史 `/sources` 返回值。
- API：索引状态/重建需所有权；Studio 前后端来源模型字段一致。

### 运维与端到端

- `docker compose up -d qdrant` 后 collection 自动初始化，重启后持久卷中的数据仍存在。
- 新建一部含早期线索的长篇，发布章节并等待 worker；后续任务能召回早期场景、角色关系和设定规则。
- 生成草稿后在 Studio 打开“查看来源”，资料、定位和入选原因稳定可读；默认没有分数或 Token 噪声。
- 模拟 Qdrant 停机后，作者仍可生成草稿，且恢复服务、重建索引后不需要修改旧 WritingRun。

## 11. 非目标

- 不改造 Phase 6 的三栏工作台、会话协议或把来源编号插入小说正文。
- 不做多租户共享检索、互联网知识库、全文搜索替代或跨小说推荐。
- 不将 Qdrant 作为主数据库，不在 Qdrant 中维护作者可编辑的正文。
- 不为每一部小说单独创建 collection，不部署本地 embedding/rerank 模型。
- 不把技术诊断默认展示给作者，也不以“检索分数高”替代质量门禁和作者决定。

## 12. 完成定义

当一部小说进入长篇阶段后，作者触发上下文包或生成草稿，系统能从已锁定的历史章节、角色、剧情事实、世界设定和伏笔中找出与当前任务相关的最小资料集，分别提供给写作与风险守卫。索引在后台可靠更新、可重建、失败可降级；每次写作运行留下不可变且可定位的来源快照，Phase 6 的作者工作台能在对应 AI 消息下稳定展示这些来源，而不会干扰中央文稿。
