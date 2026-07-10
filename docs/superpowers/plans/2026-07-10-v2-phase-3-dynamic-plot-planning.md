# Novel Agent v2 Phase 3：动态剧情规划与写作协作实施计划

> **面向智能代理的执行要求：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐任务执行本计划。步骤使用复选框（`- [ ]`）跟踪进度。

**Goal:** 在作者已有大纲、角色、世界观和剧情资料的基础上，实现“剧情单元规划 → 章节写作 → 矛盾决策 → 未发布草稿局部修订 → 作者确认发布”的完整闭环。

**架构：** 在现有 Phase 1/2 写作链路旁增加独立的作者资料、剧情单元、计划修订、决策卡和草稿修订边界；通过一个上下文构建器把当前有效作者资料、已发布章节事实、有效计划、章节任务书和相关记忆组装成快照。写作生成与草稿审查共享结构化冲突协议，所有冲突都归一到同一个 `PlanningDecision` 流程；质量问题仍走 Phase 2 的 `ReviewIssue`/`PendingRepair` 流程。发布动作与接受草稿动作分离，`Chapter.status == "locked"` 后只读。

**技术栈：** Python 3.12、FastAPI、异步 SQLAlchemy、Pydantic v2、Alembic、DeepSeek/LangChain 1.x、SQLite 测试环境/MySQL 生产环境、Vue 3、TypeScript、Pinia、Element Plus、Vitest。

## 全局约束

- `Chapter.status == "locked"` 是已发布正文事实；`draft` 和 `reviewed` 都是可调整的未发布内容。
- 任何规划、写作、审查或局部修订流程都不能覆盖、删除或改写 `locked` 章节。
- 作者资料修改产生新的 `AuthorFoundationRevision`，但不会直接产生决策卡；只有后续写作/审查确认真实矛盾时才产生决策卡。
- 当前剧情计划只约束未发布未来，必须保存本次 AI 实际使用的资料版本、锁定章节范围和计划版本。
- 写作生成和草稿审查发现的 narrative conflict 必须使用同一个决策卡格式和处理服务；普通文风、字数、表达问题继续使用 Phase 2 质量门禁。
- 决策卡通常包含 2–3 个真实可执行方案、一个推荐方案、核心后果和最小影响范围；AI 无法提供真实方案时返回 `unsafe_planning`，禁止伪造选项。
- 局部修订默认只修改段落、场景或必要的连续场景；不得因读取全文而自动全量重写。
- 所有 AI 结构化输出必须经过 Pydantic 校验；供应商失败、超时或无效 JSON 时不修改作者资料、计划版本或正式章节。
- 生产流程使用真实 `DeepSeekWritingGenerator` 或同等真实模型；`FakeWritingGenerator` 只能用于确定性测试。
- 所有后端路由继续挂在 `/api/v1/novels/{novel_id}/` 下，并通过现有小说归属守卫返回统一 `ApiResponse`。
- 当前 Alembic head 是 `c3d4e5f6a7b8` 的回滚迁移；Phase 3 新迁移必须从该 head 继续，不能重新启用已回滚的 `volume_arcs`/`plan_versions` CRUD 方案。
- 开发启动仍可依赖 `Base.metadata.create_all`，但新增模型必须同时提供 Alembic migration。
- 首要验收场景必须从“已有资料、正文尚未发布”的小说开始，而不是空白小说自动生成完整世界观。

## 实施决策

### 领域模型与状态

本计划使用以下模型边界，避免把旧 `NovelBlueprint` 或单章 `ChapterPlan` 解释成作者完整大纲：

| 模型 | 必需字段 | 状态值 |
| --- | --- | --- |
| `AuthorFoundation` | `novel_id`, `outline`, `current_intent`, `stage_goal`, `constraints_json`, `version` | 每部小说一条当前记录 |
| `AuthorFoundationRevision` | `foundation_id`, `novel_id`, `version`, `snapshot_json`, `change_reason` | 不可变快照 |
| `PlotUnit` | `novel_id`, `title`, `scope_type`, `start_position`, `end_position`, `author_goal`, `start_state`, `end_state`, `foundation_revision_id` | `draft`, `active`, `completed`, `archived` |
| `PlotPlanRevision` | `plot_unit_id`, `novel_id`, `version`, `foundation_revision_id`, `based_on_published_chapter_id`, `plan_json`, `change_reason` | `draft`, `active`, `stale`, `blocked`, `superseded`, `completed` |
| `PlanningDecision` | `novel_id`, `source`, `conflict_summary`, `evidence_json`, `options_json`, `recommended_index`, `recommendation_reason`, `impact_scope_json` | `pending`, `resolved`, `superseded` |
| `DraftRevision` | `novel_id`, `writing_run_id`, `parent_revision_id`, `decision_id`, `base_content`, `candidate_content`, `scope_json`, `diff_json`, `reason` | `candidate`, `applied`, `superseded` |

`source` 只有 `during_generation` 和 `during_review`。`PlanningDecision` 通过可空的 `plot_unit_id`、`plot_plan_revision_id`、`chapter_brief_id` 和 `writing_run_id` 关联上下文；`DraftRevision` 持有 `decision_id`，避免和决策卡形成循环外键。

### JSON 协议

`PlotPlanRevision.plan_json` 至少包含：

```json
{
  "starting_state": "当前已发布事实和人物状态",
  "stage_goal": "本剧情单元结束时必须达到的状态",
  "core_conflict": "核心冲突",
  "key_turns": [{"order": 1, "event": "关键转折", "required": true}],
  "progression": [{"order": 1, "chapter_position": 1, "purpose": "推进目的", "scenes": ["场景目标"]}],
  "character_changes": [{"character": "角色名", "from": "起点", "to": "阶段变化"}],
  "foreshadowing": [{"action": "plant", "item": "伏笔", "chapter_position": 1}],
  "must_complete": ["必须完成事项"],
  "optional": ["可选事项"],
  "completion_criteria": ["完成判断标准"]
}
```

`ContextPackage.package_json` 必须包含 `author_foundation`, `published_canon`, `plot_unit`, `plot_plan`, `chapter_brief`, `chapter_plan`, `characters`, `world_settings`, `plot_facts`, `foreshadowings`, `style_guide`, `author_input` 和 `snapshot`。`snapshot` 至少记录 `foundation_revision_id`, `plot_plan_revision_id`, `published_chapter_ids`, `chapter_brief_id` 和 `generated_at`。

### API 契约

新增端点如下，所有响应都使用现有 `ApiResponse.success()`：

```text
GET  /author-foundation
PUT  /author-foundation
GET  /author-foundation/revisions

POST /plot-units
GET  /plot-units
GET  /plot-units/{plot_unit_id}
POST /plot-units/{plot_unit_id}/plans/generate
GET  /plot-units/{plot_unit_id}/plans
PUT  /plot-units/{plot_unit_id}/plans/{revision_id}/confirm

GET  /planning-decisions
GET  /planning-decisions/{decision_id}
POST /planning-decisions/{decision_id}/choose
POST /writing-runs/{run_id}/review

PUT  /chapters/{chapter_id}/publish
```

`POST /planning-decisions/{decision_id}/choose` 的请求体是：

```json
{"option_index": 0, "custom_intent": null}
```

二者必须恰好提供一个；选择后返回 `{decision, plan_revision, draft_revision, writing_run}`。`custom_intent` 由 AI 作为作者新方向处理，仍需先成功生成局部修订，失败时不能写入有效计划。

### 现有流程兼容性

保留现有 Phase 1/2 的蓝图、单章计划、任务书和质量门禁接口，避免回归已有测试；Phase 3 新流程要求任务书关联一个已确认的 `PlotPlanRevision`，旧接口在未提供剧情单元时继续使用旧上下文构建器。Phase 3 验收只使用新流程，并断言 `plot_plan_revision_id` 出现在写作上下文快照和 AI 输入中。

---

### 任务 1：Phase 3 领域模型、Schema 与迁移

**文件：**
- 创建：`backend/app/models/plot_planning.py`
- 创建：`backend/app/schemas/plot_planning.py`
- 修改：`backend/app/models/__init__.py`
- 修改：`backend/app/models/novel.py`
- 修改：`backend/app/models/writing.py`
- 修改：`backend/app/schemas/writing.py`
- 创建：`backend/alembic/versions/d1e2f3a4b5c6_phase_3_dynamic_plot_planning.py`
- 创建：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- 提供 ORM 模型 `AuthorFoundation`、`AuthorFoundationRevision`、`PlotUnit`、`PlotPlanRevision`、`PlanningDecision`、`DraftRevision`。
- 提供 Pydantic 模型 `AuthorFoundationOut`、`AuthorFoundationUpdateRequest`、`AuthorFoundationRevisionOut`、`PlotUnitCreateRequest`、`PlotUnitOut`、`PlotPlanRevisionOut`、`PlanningDecisionOut`、`DecisionOptionOut`、`ChooseDecisionRequest`、`DraftRevisionOut`。
- 扩展 `WritingRun.status`，支持 `decision_required`，并增加 `decision_id: Optional[int]`、`context_snapshot_json: dict` 和 `planning_blocked: bool`。

- [ ] **步骤 1：先编写失败的模型和 Schema 测试**

```python
@pytest.mark.asyncio
async def test_phase3_models_preserve_revision_and_decision_boundaries(db):
    foundation = AuthorFoundation(
        novel_id=1,
        outline="作者已有第一卷大纲",
        current_intent="先完成边城调查",
        stage_goal="主角发现密令来源",
        constraints_json={"tone": "克制", "must_keep": ["旧案线索"]},
        version=1,
    )
    db.add(foundation)
    await db.flush()
    revision = AuthorFoundationRevision(
        novel_id=1,
        foundation_id=foundation.id,
        version=1,
        snapshot_json={"outline": foundation.outline, "stage_goal": foundation.stage_goal},
        change_reason="initial",
    )
    db.add(revision)
    await db.flush()
    unit = PlotUnit(
        novel_id=1,
        title="第一卷：边城旧案",
        scope_type="volume",
        start_position=1,
        end_position=5,
        author_goal="查清密令来源",
        start_state="主角抵达边城",
        end_state="主角确认旧案与密令相连",
        foundation_revision_id=revision.id,
        status="draft",
    )
    db.add(unit)
    await db.flush()
    plan = PlotPlanRevision(
        novel_id=1,
        plot_unit_id=unit.id,
        foundation_revision_id=revision.id,
        version=1,
        plan_json={"core_conflict": "调查会触动守城势力"},
        change_reason="initial generation",
        status="draft",
    )
    db.add(plan)
    await db.flush()
    decision = PlanningDecision(
        novel_id=1,
        plot_unit_id=unit.id,
        plot_plan_revision_id=plan.id,
        source="during_review",
        status="pending",
        conflict_summary="新目标要求推翻已发布事实",
        evidence_json={"published_chapter_ids": [10]},
        options_json=[{"label": "补充因果", "consequence": "保留事实"}, {"label": "改写未来", "consequence": "延后揭示"}],
        recommended_index=0,
        recommendation_reason="不会修改已发布章节",
        impact_scope_json={"type": "scene", "start": 2, "end": 2},
    )
    db.add(decision)
    await db.flush()
    assert plan.status == "draft"
    assert decision.source == "during_review"
    assert len(decision.options_json) == 2


def test_decision_request_requires_option_or_custom_intent():
    with pytest.raises(ValidationError):
        ChooseDecisionRequest()
    assert ChooseDecisionRequest(option_index=1).option_index == 1
    assert ChooseDecisionRequest(custom_intent="保留事实并延后揭示").custom_intent
```

- [ ] **步骤 2：运行聚焦测试，确认按预期 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -x -q`

预期：失败，因为 `app.models.plot_planning` 和新 Schema 尚不存在。

- [ ] **步骤 3：添加最小 ORM 模型和响应 Schema**

`backend/app/models/plot_planning.py` 必须使用带类型的 SQLAlchemy `Mapped` 字段和 `mapped_column` 声明，`JSON` 默认值使用 `dict`/`list`，并包含以下准确字段：

```python
class AuthorFoundation(Base):
    __tablename__ = "author_foundations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, unique=True, index=True)
    outline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_intent: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    constraints_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
    updated_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now, onupdate=datetime.datetime.now)


class AuthorFoundationRevision(Base):
    __tablename__ = "author_foundation_revisions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novels.id"), nullable=False, index=True)
    foundation_id: Mapped[int] = mapped_column(ForeignKey("author_foundations.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.now)
```

`PlotUnit`、`PlotPlanRevision`、`PlanningDecision` 和 `DraftRevision` 必须遵循本计划中的字段表；`DraftRevision.parent_revision_id` 是可空的自引用外键，所有可能在计划确认前产生的决策/计划外键都必须允许为空。在 `Novel` 中显式添加 `author_foundation` 和 `plot_units` 关系，并设置 `cascade="all, delete-orphan"`。

在 `plot_planning.py` 的 Schema 中为上述状态和来源值定义 `Literal` 别名。`ChooseDecisionRequest` 必须通过 `model_validator(mode="after")` 拒绝两个字段都没有或两个字段同时存在的请求体。

- [ ] **步骤 4：扩展写作 Schema/模型，同时保持 Phase 1/2 不回归**

向 `WritingRun` 添加：

```python
decision_id: Mapped[Optional[int]] = mapped_column(ForeignKey("planning_decisions.id"), nullable=True)
context_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
planning_blocked: Mapped[bool] = mapped_column(default=False)
```

向 `WritingRunOut` 添加相同字段；随后在 TypeScript/API 状态契约中加入 `decision_required`。保持 `draft_content`、`gated` 和 `has_pending_repairs` 不变。

- [ ] **步骤 5：生成并检查 Alembic 迁移**

运行：`cd backend && .venv/bin/python -m alembic revision --autogenerate -m "phase_3_dynamic_plot_planning"`

预期：生成的 revision 基于 `c3d4e5f6a7b8`，创建 6 张 Phase 3 表，添加 `writing_runs` 的 3 个字段，并且不重新创建 `volume_arcs` 或 `plan_versions`。只有在检查完 `upgrade()` 和 `downgrade()` 后，才将生成文件重命名为 `d1e2f3a4b5c6_phase_3_dynamic_plot_planning.py`。

- [ ] **步骤 6：运行测试并验证迁移**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -x -q`

预期：模型和 Schema 测试 PASS。

运行：`cd backend && .venv/bin/python -m alembic upgrade head`

预期：退出码为 0，并且 6 张新表及 `writing_runs` 的 3 个字段均存在。

### 任务 2：结构化规划、冲突、审查与修订 AI 协议

**文件：**
- 创建：`backend/app/ai/plot_planning.py`
- 修改：`backend/app/ai/writer.py`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`
- 创建：`backend/tests/test_phase_3_ai_integration.py`

**接口约定：**
- 提供 Pydantic 协议模型 `PlotPlanOutput`、`DecisionOption`、`ConflictOutput`、`DraftGenerationOutput`、`DraftReviewOutput`、`LocalRevisionOutput`。
- 扩展 `BaseWritingGenerator`，增加 `generate_plot_plan`、`generate_draft_result`、`review_draft` 和 `revise_draft`。
- 提供支持脚本化输出的 `FakePhase3WritingGenerator`，并让 `DeepSeekWritingGenerator` 校验每一次 JSON 响应。

- [ ] **步骤 1：先编写失败的协议测试**

```python
def test_conflict_output_requires_two_real_options():
    result = ConflictOutput(
        source="during_generation",
        core_conflict="已发布事实与新目标冲突",
        options=[
            DecisionOption(label="补充因果", consequence="保留已发布事实"),
            DecisionOption(label="改变未来目标", consequence="不触碰正文"),
        ],
        recommended_index=0,
        recommendation_reason="影响范围最小",
        impact_scope={"type": "scene", "start": 2, "end": 2},
    )
    assert len(result.options) == 2


def test_conflict_output_rejects_duplicate_or_fake_options():
    with pytest.raises(ValidationError):
        ConflictOutput(
            source="during_review",
            core_conflict="冲突",
            options=[
                DecisionOption(label="同一方案", consequence="保留"),
                DecisionOption(label="同一方案", consequence="保留"),
            ],
            recommended_index=0,
            recommendation_reason="理由",
            impact_scope={"type": "paragraph"},
        )


@pytest.mark.asyncio
async def test_fake_generation_can_return_decision_required():
    generator = FakePhase3WritingGenerator(
        draft_result=DraftGenerationOutput(
            status="decision_required",
            draft="不越过冲突点的部分正文",
            conflict=ConflictOutput(
                source="during_generation",
                core_conflict="世界规则不允许新目标",
                options=[
                    DecisionOption(label="补充代价", consequence="保留规则"),
                    DecisionOption(label="调整目标", consequence="保留角色动机"),
                ],
                recommended_index=0,
                recommendation_reason="最小影响",
                impact_scope={"type": "scene", "start": 1, "end": 1},
            ),
        )
    )
    result = await generator.generate_draft_result({"plot_plan": {}})
    assert result.status == "decision_required"
    assert result.conflict is not None
```

- [ ] **步骤 2：运行测试，确认 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_conflict_output_requires_two_real_options -x -q`

预期：失败，因为 Phase 3 协议模型尚不存在。

- [ ] **步骤 3：实现带校验的协议模型**

使用以下公开结构：

```python
class DecisionOption(BaseModel):
    label: str = Field(min_length=1)
    action: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    affected_future_scope: dict[str, Any] = Field(default_factory=dict)


class ConflictOutput(BaseModel):
    source: Literal["during_generation", "during_review"]
    core_conflict: str = Field(min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    options: list[DecisionOption]
    recommended_index: int = Field(ge=0)
    recommendation_reason: str = Field(min_length=1)
    impact_scope: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_options(self):
        labels = [f"{item.label}:{item.action}" for item in self.options]
        if len(self.options) not in (2, 3) or len(set(labels)) != len(labels):
            raise ValueError("必须提供 2-3 个不同的真实方案")
        if self.recommended_index >= len(self.options):
            raise ValueError("推荐方案索引越界")
        return self


class DraftGenerationOutput(BaseModel):
    status: Literal["draft_ready", "decision_required", "unsafe_planning"]
    draft: str = ""
    conflict: ConflictOutput | None = None
    unsafe_reason: str | None = None
```

`PlotPlanOutput` 的字段必须覆盖本计划 JSON 协议；`DraftReviewOutput` 分离 `narrative_conflicts: list[ConflictOutput]` 和 `quality_issues: list[dict]`；`LocalRevisionOutput` 必须包含 `candidate_content`、`scope`、`diff`、`plan_patch`、`expanded_scope: bool` 和 `expansion_reason`。`plan_patch` 是应用作者决定后合并到旧 `plan_json` 的最小未来计划变更。当模型返回少于两个可执行方案时，将状态设为 `unsafe_planning`，不拼接后端预置选项。

- [ ] **步骤 4：扩展生成器接口和 Fake 实现**

在 `BaseWritingGenerator` 增加以下方法，保留既有 `generate_draft()` 以兼容 Phase 1/2：

```python
async def generate_plot_plan(self, foundation: dict, plot_unit: dict, published_canon: dict) -> dict:
    raise NotImplementedError

async def generate_draft_result(self, context_package: dict) -> DraftGenerationOutput:
    raise NotImplementedError

async def review_draft(self, context_package: dict, draft: str) -> DraftReviewOutput:
    raise NotImplementedError

async def revise_draft(self, context_package: dict, draft: str, conflict: dict, selected_direction: str) -> LocalRevisionOutput:
    raise NotImplementedError
```

`FakePhase3WritingGenerator` 的构造函数接受每个方法的可选脚本结果，默认返回没有冲突的最小有效结果；它不读取环境变量。`DeepSeekWritingGenerator` 通过 `_call_validated_json(prompt, model_type)` 辅助方法调用真实 agent、解析 JSON 并执行 Pydantic 校验，解析失败直接抛出 `AIProtocolError`。

- [ ] **步骤 5：添加不联网的真实供应商提示词测试**

使用 monkeypatch 替换 `_call_validated_json`，断言 `generate_plot_plan()`、`review_draft()` 和 `revise_draft()` 传入的提示词包含 `author_foundation`、`published_canon`、`plot_plan`、`draft` 和 `impact_scope`；不要在单元测试中伪造 HTTP 响应或调用真实供应商。

- [ ] **步骤 6：验证协议和 Fake 实现**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -x -q`

预期：所有协议和 Fake 生成器测试 PASS。

### 任务 3：作者资料、剧情单元规划服务与上下文快照

**文件：**
- 创建：`backend/app/repositories/plot_planning_repo.py`
- 创建：`backend/app/services/plot_planning_service.py`
- 创建：`backend/app/services/context_package_service.py`
- 创建：`backend/app/api/planning.py`
- 修改：`backend/app/main.py`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- `PlotPlanningService(db, user_id, novel_id, generator=None)` 负责所有 Phase 3 资源和归属校验。
- `PlotPlanningService.update_foundation(data, change_reason)` 创建第一条作者资料/修订记录，或递增现有修订版本。
- `PlotPlanningService.generate_plan(plot_unit_id, author_input="")` 使用当前作者资料修订、已发布事实和可选作者输入，创建 `draft` 状态的 `PlotPlanRevision`。
- `PlotPlanningService.confirm_plan(plot_unit_id, revision_id)` 将之前的生效计划标记为 `superseded`，并将选中的修订标记为 `active`。
- `ContextPackageService.build_for_brief(brief_id, plot_plan_revision_id, author_input)` 返回 AI 实际使用的完整 `package_json` 快照。

- [ ] **步骤 1：先编写失败的仓储/服务测试**

```python
@pytest.mark.asyncio
async def test_foundation_update_creates_history_without_decision(db):
    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator())
    first = await service.update_foundation(
        {"outline": "第一版大纲", "current_intent": "调查", "stage_goal": "找到证据", "constraints_json": {}},
        change_reason="initial",
    )
    second = await service.update_foundation(
        {"stage_goal": "找到证据并保护证人"},
        change_reason="作者调整阶段目标",
    )
    revisions = await service.list_foundation_revisions()
    assert first.version == 1
    assert second.version == 2
    assert [revision.version for revision in revisions] == [2, 1]
    assert await service.list_pending_decisions() == []


@pytest.mark.asyncio
async def test_context_contains_only_locked_chapters_and_plan_snapshot(db):
    locked = Chapter(novel_id=1, title="已发布章", content="不可修改事实", status="locked")
    draft = Chapter(novel_id=1, title="未发布章", content="候选正文", status="draft")
    db.add_all([locked, draft])
    await db.flush()
    context = await ContextPackageService(db, user_id=1, novel_id=1).build_for_brief(
        brief_id=1,
        plot_plan_revision_id=1,
        author_input="本次让调查转向码头",
    )
    assert [item["id"] for item in context["published_canon"]["chapters"]] == [locked.id]
    assert "候选正文" not in str(context["published_canon"])
    assert context["snapshot"]["plot_plan_revision_id"] == 1
    assert context["author_input"] == "本次让调查转向码头"
```

- [ ] **步骤 2：运行聚焦测试，确认 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_foundation_update_creates_history_without_decision -x -q`

预期：失败，因为仓储和服务尚不存在。

- [ ] **步骤 3：实现带归属保护的仓储查询方法**

`plot_planning_repo.py` 必须提供 `get_foundation`、`get_latest_foundation_revision`、`list_foundation_revisions`、`create_foundation`、`create_foundation_revision`、`get_plot_unit`、`list_plot_units`、`create_plot_unit`、`list_plan_revisions`、`get_plan_revision`、`create_plan_revision`、`archive_active_plans`、`get_decision`、`list_pending_decisions`、`create_decision`、`update_decision`、`create_draft_revision` 和 `list_draft_revisions_by_run`。所有接收资源 ID 的查询都必须同时按 `novel_id` 过滤；跨用户或跨小说资源返回 `None`，由服务层转换为统一的资源不存在错误。

- [ ] **步骤 4：实现作者资料版本化和剧情计划确认**

`update_foundation()` 必须加载或创建一条 `AuthorFoundation`，只合并请求中提供的字段，递增 `version`，插入不可变快照记录，并将该小说现有的 `active` `PlotPlanRevision` 标记为 `stale`。它不得创建 `PlanningDecision`，也不得修改任何 `Chapter`。

`generate_plan(plot_unit_id, author_input="")` 必须先调用 `generator.generate_plot_plan()`，再插入数据库记录。保存的修订必须引用当前作者资料修订，以最新锁定章节 ID 作为 `based_on_published_chapter_id`，并保持 `draft` 状态。如果生成器抛出异常或返回无效数据，必须回滚会话且不能留下新计划。

`confirm_plan()` 必须确认所选修订属于指定剧情单元且 `status == "draft"`；将当前 `active` 修订归档为 `superseded`，将所选修订设为 `active`，并只提交一次事务。

- [ ] **步骤 5：实现上下文包构建器**

`ContextPackageService.build_for_brief()` 必须加载任务书、对应章节计划、选中的生效计划修订、当前作者资料修订、角色、世界设定、剧情事实、伏笔和章节。它必须将 `published_canon.chapters` 过滤为 `status == "locked"`，保留来源 ID，并包含 `snapshot` 对象。构建器可以查询全部章节来计算相关性，但只有锁定章节正文可以进入 `published_canon`。

- [ ] **步骤 6：实现 Phase 3 路由并注册 Router**

所有新端点都必须使用请求/响应 Schema，而不是原始 `dict`。每个处理器创建 `PlotPlanningService(db, current_user.id, novel_id)`，调用服务并使用 `model_validate(resource).model_dump()` 序列化具体资源。在 `backend/app/main.py` 中添加 `app.include_router(planning.router, prefix="/api/v1")`。

`POST /plot-units/{plot_unit_id}/plans/generate` 的请求体是 `{"author_input": "本次计划以证人脱身为目标"}`；`POST /plot-units` 接收的准确字段为 `title`、`scope_type`、`start_position`、`end_position`、`author_goal`、`start_state`、`end_state`。

- [ ] **步骤 7：验证服务/API 行为**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -x -q`

预期：作者资料历史、剧情单元归属、计划生成/确认、过期标记和仅包含锁定章节的上下文测试均 PASS。

### 任务 4：将 Phase 3 上下文接入章节任务书和写作生成

**文件：**
- 修改：`backend/app/services/writing_service.py`
- 修改：`backend/app/api/writing.py`
- 修改：`backend/app/schemas/writing.py`
- 修改：`backend/app/repositories/writing_repo.py`
- 修改：`backend/tests/test_phase_1_writing.py`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- `ChapterBriefGenerateRequest` 增加可选的 `plot_plan_revision_id` 和 `author_input`。
- `WritingRunCreateRequest` 增加可选的 `plot_plan_revision_id` 和 `author_input`。
- `WritingService.create_writing_run()` 记录 `context_snapshot_json`；选中 Phase 3 计划时使用 `generate_draft_result()`。
- Phase 3 生成可以结束为 `completed`/`draft_ready`、`decision_required` 或 `failed`；其中 `unsafe_planning` 结果必须落为 `failed` 并保存原因，且不改变现有 Phase 1/2 状态。

- [ ] **步骤 1：先添加感知计划的失败集成测试**

```python
@pytest.mark.asyncio
async def test_phase3_writing_run_passes_plan_and_locked_canon_to_generator(db):
    generator = RecordingPhase3WritingGenerator()
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator, gate_agent=FakeQualityGateAgent())
    run = await service.create_writing_run(
        brief_id=1,
        plot_plan_revision_id=1,
        author_input="本次必须让证人活着离开",
    )
    assert run.status == "completed"
    assert generator.last_context["snapshot"]["plot_plan_revision_id"] == 1
    assert generator.last_context["author_input"] == "本次必须让证人活着离开"
    assert [item["status"] for item in generator.last_context["published_canon"]["chapters"]] == ["locked"]
    assert run.context_snapshot_json["foundation_revision_id"] is not None


@pytest.mark.asyncio
async def test_decision_required_preserves_partial_unpublished_draft(db):
    generator = FakePhase3WritingGenerator(draft_result=decision_required_result())
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator, gate_agent=FakeQualityGateAgent())
    run = await service.create_writing_run(brief_id=1, plot_plan_revision_id=1)
    assert run.status == "decision_required"
    assert run.planning_blocked is True
    assert run.decision_id is not None
    assert run.draft_content == "不越过冲突点的部分正文"
    assert await db.get(Chapter, 1) is None or (await db.get(Chapter, 1)).status != "locked"
```

- [ ] **步骤 2：运行测试，确认 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_phase3_writing_run_passes_plan_and_locked_canon_to_generator -x -q`

预期：失败，因为现有 `WritingService` 尚不接受 Phase 3 上下文参数。

- [ ] **步骤 3：将 Phase 3 上下文贯穿任务书、上下文包和写作运行创建**

当存在 `plot_plan_revision_id` 时，`generate_chapter_brief()` 必须验证该修订属于当前小说且状态为 `active`，然后将 `plot_plan_revision_id` 写入任务书 JSON 元数据。`generate_context_package()` 和 `create_writing_run()` 必须调用 `ContextPackageService.build_for_brief()`，并原样持久化返回的上下文包。

未提供新 ID 时，旧流程保持不变。Phase 3 流程不得静默退回使用生效的 `NovelBlueprint` 来替代选定的剧情计划。

- [ ] **步骤 4：原子处理结构化生成结果**

在 `create_writing_run()` 中：

1. 创建一条 `running` 记录并 flush。
2. 调用 `generate_draft_result(package)`。
3. 保存上下文包中的完整 `context_snapshot_json`。
4. 对于 `draft_ready`，写入草稿并继续现有 Phase 2 质量门禁。
5. 对于 `decision_required`，保存部分草稿，创建共享决策记录和 `candidate` 状态的 `DraftRevision`，设置 `status="decision_required"`、`planning_blocked=True`，并禁止进入普通接受流程。
6. 对于 `unsafe_planning`，设置 `status="failed"`，保存 `error_message`，且不创建决策或方案。
7. 对于供应商或协议校验异常，设置 `status="failed"`，保留已有未发布内容，且不修改计划或章节。

决策创建代码必须位于 `PlotPlanningService.create_decision_from_conflict()`，使写作生成和草稿审查后续使用同一个归一化器。

- [ ] **步骤 5：保持现有 Phase 1/2 测试通过**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_1_writing.py tests/test_phase_2_quality_gate.py -x -q`

预期：所有现有测试通过；由于新增字段都有 Python/数据库默认值，直接实例化 `WritingRun` 的测试继续可用。

- [ ] **步骤 6：验证新的写作流程**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py -x -q`

预期：计划感知上下文、需要决策的生成、原子失败处理和锁定章节不被修改等测试均 PASS。

### 任务 5：共享冲突决策、草稿审查与普通质量问题分流

**文件：**
- 修改：`backend/app/services/plot_planning_service.py`
- 修改：`backend/app/services/writing_service.py`
- 修改：`backend/app/api/planning.py`
- 修改：`backend/app/api/writing.py`
- 修改：`backend/app/repositories/plot_planning_repo.py`
- 修改：`backend/app/ai/plot_planning.py`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- `PlotPlanningService.create_decision_from_conflict(conflict, source, run, context)` 创建一张归一化决策卡。
- `WritingService.review_writing_run(run_id)` 对 narrative conflict 调用同一方法，将普通质量问题分流到 Phase 2。
- `POST /writing-runs/{run_id}/review` 返回 `{decision: DecisionOut | null, review_issues: list[ReviewIssueOut]}`。
- `GET /planning-decisions` 只返回当前小说所属的决策，并支持可选的 `status` 查询过滤。

- [ ] **步骤 1：先编写两个发现入口的失败测试**

```python
@pytest.mark.asyncio
async def test_generation_and_review_use_same_decision_shape(db):
    generation_service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    review_service = PlotPlanningService(db=db, user_id=1, novel_id=1)
    conflict = conflict_output()
    during_generation = await generation_service.create_decision_from_conflict(conflict, source="during_generation", run_id=1)
    during_review = await review_service.create_decision_from_conflict(conflict.model_copy(update={"source": "during_review"}), source="during_review", run_id=1)
    assert during_generation.conflict_summary == during_review.conflict_summary
    assert during_generation.options_json == during_review.options_json
    assert during_generation.source == "during_generation"
    assert during_review.source == "during_review"


@pytest.mark.asyncio
async def test_review_does_not_turn_style_issue_into_decision(db):
    generator = FakePhase3WritingGenerator(
        review_result=DraftReviewOutput(
            narrative_conflicts=[],
            quality_issues=[{"issue_type": "style", "severity": "warning", "description": "句式重复", "location": "第2段"}],
        )
    )
    service = WritingService(db=db, user_id=1, novel_id=1, generator=generator)
    result = await service.review_writing_run(1)
    assert result["decision"] is None
    assert len(result["review_issues"]) == 1
    assert await PlotPlanningService(db, 1, 1).list_pending_decisions() == []
```

- [ ] **步骤 2：运行测试，确认 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_generation_and_review_use_same_decision_shape -x -q`

预期：失败，因为草稿审查和共享决策创建尚未实现。

- [ ] **步骤 3：实现共享决策归一化器**

`create_decision_from_conflict()` 必须将结构化冲突复制到 `options_json`，持久化证据和影响范围，设置 `status="pending"`，并将受影响生效计划的 `PlotPlanRevision.status` 设置为 `blocked`。方案少于两个时必须拒绝创建，不得插入伪造方案。`source` 参数必须校验为两个允许值之一，不能从自由文本推断。

- [ ] **步骤 4：实现草稿审查**

`review_writing_run()` 必须验证写作运行属于当前小说，仅在实际存在未发布草稿且状态为 `completed` 或 `accepted` 时继续，并且必须存在 Phase 3 上下文快照。它调用 `review_draft(context, run.draft_content)`。对每个 `narrative_conflicts` 项，使用 `source="during_review"` 调用共享归一化器；对每个 `quality_issues` 项，创建现有 Phase 2 `ReviewIssue` 记录。审查调用失败时不得创建新决策，现有草稿保持不变。

- [ ] **步骤 5：添加路由和归属测试**

实现 `GET /planning-decisions`、`GET /planning-decisions/{decision_id}` 和 `POST /writing-runs/{run_id}/review`。访问其他小说的资源必须返回现有的 `40400` 行为。添加未登录请求、跨用户请求和成功审查响应测试。

- [ ] **步骤 6：验证分流和共享行为**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_2_quality_gate.py -x -q`

预期：PASS；只有文风问题的审查不会创建 `PlanningDecision`，而写作生成和草稿审查产生的冲突具有完全一致的方案/推荐字段。

### 任务 6：作者决策处理、计划版本化、草稿局部修订与发布边界

**文件：**
- 修改：`backend/app/services/plot_planning_service.py`
- 修改：`backend/app/services/writing_service.py`
- 修改：`backend/app/repositories/novel_repo.py`
- 修改：`backend/app/services/novel_service.py`
- 修改：`backend/app/api/novels.py`
- 修改：`backend/app/api/writing.py`
- 修改：`backend/app/schemas/novel.py`
- 修改：`backend/app/schemas/plot_planning.py`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- `PlotPlanningService.choose_decision(decision_id, option_index=None, custom_intent=None)` 返回 `(decision, plan_revision, draft_revision, run)`。
- `WritingService.accept_writing_run()` 只写入未发布的 `Chapter`，并拒绝仍有待处理规划决策的运行。
- `NovelService.publish_chapter()` 经过阻断条件检查后，只能将非锁定章节改为 `locked`。

- [ ] **步骤 1：先编写最小修订和不可变正典的失败测试**

```python
@pytest.mark.asyncio
async def test_choose_decision_preserves_unaffected_text_and_creates_new_plan(db):
    service = PlotPlanningService(db=db, user_id=1, novel_id=1, generator=FakePhase3WritingGenerator(
        revision_result=LocalRevisionOutput(
            candidate_content="开头不变。修订后的冲突场景。结尾不变。",
            scope={"type": "paragraph", "start": 2, "end": 2},
            diff={"removed": ["旧冲突场景"], "added": ["修订后的冲突场景"]},
            plan_patch={"progression": [{"order": 2, "purpose": "承接补充因果"}]},
            expanded_scope=False,
            expansion_reason="",
        )
    ))
    decision, new_plan, revision, run = await service.choose_decision(7, option_index=0)
    assert decision.status == "resolved"
    assert new_plan.version == 2
    assert revision.status == "candidate"
    assert revision.candidate_content.startswith("开头不变。")
    assert revision.candidate_content.endswith("结尾不变。")
    assert new_plan.status == "active"


@pytest.mark.asyncio
async def test_locked_chapter_rejects_update_accept_and_delete(client, novel_and_headers):
    novel, headers = novel_and_headers
    chapter = await create_locked_chapter(client, novel["id"], headers, "发布事实")
    update = await client.put(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
        json={"content": "试图改写"},
    )
    assert update.status_code == 400
    delete = await client.delete(
        f"/api/v1/novels/{novel['id']}/chapters/{chapter['id']}",
        headers=headers,
    )
    assert delete.status_code == 400
```

- [ ] **步骤 2：运行聚焦测试，确认 RED 失败**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py::test_locked_chapter_rejects_update_accept_and_delete -x -q`

预期：失败，因为当前章节更新/删除和写作接受路径仍允许修改 `locked` 内容。

- [ ] **步骤 3：实现决策选择事务**

在任何数据库写操作之前，加载待处理决策、对应运行、当前生效计划、父草稿修订和上下文快照。校验作者只能选择一种方式，然后使用选中的方案或自定义意图调用 `generator.revise_draft()`。只有在返回有效 `LocalRevisionOutput` 后，才执行以下操作：

1. 创建新的 `PlotPlanRevision`，其 `version = active.version + 1`，`change_reason` 包含决策 ID，`plan_json = merge(active.plan_json, revision_result.plan_patch)`，状态为 `active`。
2. 将旧的生效计划标记为 `superseded`。
3. 在 JSON 元数据中将受影响的未来 `ChapterPlan`/`ChapterBrief` 标记为过期，但不得触碰任何锁定章节。
4. 创建关联父修订和决策卡的 `DraftRevision`，写入 `base_content`、`candidate_content`、`scope_json`、`diff_json`，状态为 `candidate`。
5. 将决策设置为 `resolved`，保存作者选择或自定义意图，设置运行的 `planning_blocked=False`，只替换运行中的未发布草稿候选内容，然后一次性提交。

如果计划生成或局部修订失败，回滚 savepoint，并保持决策为 `pending`、旧计划为 `active`、原始草稿不变。如果作者输入发生变化导致旧决策已不是当前决策，则将其标记为 `superseded`，重新生成决策，不得应用过期输出。

- [ ] **步骤 4：实现接受草稿与发布的分离动作**

修改 `accept_writing_run()`：拒绝 `decision_required`、`planning_blocked=True` 或存在待处理 `PlanningDecision` 的运行。写入既有章节时，必须验证 `chapter.status != "locked"`，否则抛出 `AppException("已发布章节不可覆盖")`。接受后的章节仍为 `draft`，并且只有作者接受后，该运行最新的 `DraftRevision` 才能从 `candidate` 变为 `applied`。

添加 `NovelService.publish_chapter()` 和 `PUT /novels/{novel_id}/chapters/{chapter_id}/publish`。它必须拒绝已锁定章节、存在待处理决策的章节，或关联运行仍为 `planning_blocked=True` 的章节；成功时只设置 `status="locked"`。在 `ChapterRepo.update()` 和 `ChapterRepo.delete()` 中加入相同保护，避免服务/API 路径绕过发布边界。

- [ ] **步骤 5：处理过期决策卡的替代关系**

当待处理决策存在时，如果执行 `update_foundation()` 或作者目标更新，将该决策标记为 `superseded`，章节和草稿保持不变。后续写作/审查读取最新上下文，并可以创建新的待处理决策卡。

- [ ] **步骤 6：验证决策处理、失败和发布规则**

运行：`cd backend && .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning.py tests/test_phase_1_manual_memory.py tests/test_phase_1_writing.py -x -q`

预期：方案/自定义意图选择、旧计划历史、未受影响正文保留、待处理决策阻止发布、锁定章节拒绝更新/接受/删除，以及 AI 失败原子性测试均 PASS。

### 任务 7：前端规划工作台与决策卡协作

**文件：**
- 创建：`frontend/src/types/plotPlanning.ts`
- 创建：`frontend/src/api/planning.ts`
- 创建：`frontend/src/stores/plotPlanning.ts`
- 创建：`frontend/src/components/writing/PlotUnitPanel.vue`
- 创建：`frontend/src/components/writing/DecisionCard.vue`
- 创建：`frontend/src/components/writing/DraftRevisionDiff.vue`
- 修改：`frontend/src/types/writing.ts`
- 修改：`frontend/src/types/novel.ts`
- 修改：`frontend/src/api/writing.ts`
- 修改：`frontend/src/stores/writing.ts`
- 修改：`frontend/src/views/novels/WritingWorkspaceView.vue`
- 修改：`frontend/src/components/editor/WritingEditor.vue`
- 修改：`frontend/src/views/editor/EditorView.vue`
- 测试：`frontend/src/__tests__/PlotPlanning.spec.ts`
- 测试：`frontend/src/__tests__/WritingEditor.spec.ts`

**接口约定：**
- `PlotPlanningStore` 管理作者资料、资料修订、剧情单元、生效计划、待处理决策、当前草稿修订、加载状态和错误状态。
- `DecisionCard.vue` 接收 `PlanningDecision`，并以 `{ optionIndex?: number; customIntent?: string }` 触发 `choose` 事件。
- `DraftRevisionDiff.vue` 接收 `DraftRevision`，渲染未变更/删除/新增片段，不编辑锁定章节。

- [ ] **步骤 1：先编写失败的类型、Store 和组件测试**

```ts
it('renders a decision card with recommendation and two executable options', () => {
  const wrapper = mount(DecisionCard, { props: { decision: decisionFixture } })
  expect(wrapper.text()).toContain('核心冲突')
  expect(wrapper.text()).toContain('AI 推荐')
  expect(wrapper.text()).toContain('补充因果')
  expect(wrapper.text()).toContain('调整未来目标')
})

it('does not expose publish action for locked chapters', () => {
  const wrapper = mount(WritingEditor, { props: { chapter: Object.assign({}, chapterFixture, { status: 'locked' }) } })
  expect(wrapper.find('[data-testid="publish-chapter"]').exists()).toBe(false)
  expect(wrapper.find('textarea').attributes('readonly')).toBeDefined()
})
```

- [ ] **步骤 2：运行测试，确认 RED 失败**

运行：`cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts src/__tests__/WritingEditor.spec.ts`

预期：失败，因为新类型、组件和锁定编辑器行为尚不存在。

- [ ] **步骤 3：添加精确的前端契约**

`frontend/src/types/plotPlanning.ts` 必须与后端字段一致，并为 `PlotPlanStatus`、`DecisionSource`、`DecisionStatus` 和 `DraftRevisionStatus` 使用字面量联合类型。`WritingRun.status` 改为 `'running' | 'completed' | 'decision_required' | 'failed' | 'accepted' | 'discarded'`，同时包含 `decision_id`、`context_snapshot_json` 和 `planning_blocked`。

`frontend/src/api/planning.ts` 必须实现：

```ts
export function getFoundation(novelId: number): Promise<AuthorFoundation>
export function updateFoundation(novelId: number, data: AuthorFoundationUpdate): Promise<AuthorFoundation>
export function listPlotUnits(novelId: number): Promise<PlotUnit[]>
export function createPlotUnit(novelId: number, data: PlotUnitCreate): Promise<PlotUnit>
export function generatePlotPlan(novelId: number, plotUnitId: number, authorInput: string): Promise<PlotPlanRevision>
export function confirmPlotPlan(novelId: number, plotUnitId: number, revisionId: number): Promise<PlotPlanRevision>
export function listDecisions(novelId: number, status?: DecisionStatus): Promise<PlanningDecision[]>
export function chooseDecision(novelId: number, decisionId: number, data: ChooseDecisionRequest): Promise<DecisionResolution>
export function reviewWritingRun(novelId: number, runId: number): Promise<ReviewWritingRunResponse>
export function publishChapter(novelId: number, chapterId: number): Promise<Chapter>
```

- [ ] **步骤 4：实现 Store 和聚焦 UI 组件**

`usePlotPlanningStore()` 只有在确认 API 成功后才能更新生效计划；决策处理后使用服务器响应替换本地决策，并在 API 失败时保留之前的候选草稿。`DecisionCard.vue` 必须显示核心冲突、2 或 3 个方案、推荐意见和自定义意图输入框，默认不展开完整证据链。`DraftRevisionDiff.vue` 使用服务器返回的 `diff_json`，在作者选中候选版本前，应用/替换按钮保持禁用。

- [ ] **步骤 5：接入现有写作工作台**

在 `WritingWorkspaceView.vue` 中加入紧凑的 Phase 3 流程：作者资料编辑、剧情单元目标、计划生成审阅/确认、章节任务书/上下文生成、草稿生成、可选审查、决策卡、局部差异、接受为草稿和发布为锁定。保留现有蓝图和 Phase 2 修复面板，不创建独立 CRUD 仪表盘。

通过 `stores/writing.ts` 将 `plot_plan_revision_id` 和 `author_input` 传递给现有 API 调用。将 `decision_required` 显示为阻塞式协作状态，而不是成功草稿。在 `WritingEditor.vue` 和 `EditorView.vue` 中，锁定章节只读，且没有保存/删除/发布控件；`draft`/`reviewed` 章节保留正常编辑能力。

- [ ] **步骤 6：验证前端行为**

运行：`cd frontend && npm run test:unit -- src/__tests__/PlotPlanning.spec.ts src/__tests__/WritingEditor.spec.ts && npm run type-check`

预期：PASS，无 TypeScript 错误，现有修复/编辑器测试继续通过。

### 任务 8：确定性端到端验收场景与鉴权覆盖

**文件：**
- 修改：`backend/tests/test_phase_3_dynamic_plot_planning.py`
- 创建：`backend/tests/test_phase_3_dynamic_plot_planning_integration.py`
- 修改：`frontend/src/__tests__/PlotPlanning.spec.ts`
- 仅当实现发现已审阅契约需要修正时，才修改 `docs/superpowers/specs/2026-07-10-v2-phase-3-dynamic-plot-planning-design.md`

**接口约定：**
- 提供包含既有作者资料、锁定正典、Fake 生成器和一份未发布草稿的确定性测试夹具。
- 提供真实供应商集成测试；没有 `DEEPSEEK_API_KEY` 时跳过，生产路径绝不使用 Fake 方案。

- [ ] **步骤 1：编写完整的确定性场景**

测试必须按以下顺序执行这些 HTTP/服务层操作：

```python
novel = await create_novel_with_foundation_and_memory(
    client,
    headers,
    outline="作者已有第一卷大纲：主角在边城调查旧案",
    stage_goal="查清旧案并保护证人",
)
unit = await create_plot_unit(novel, title="第一卷", author_goal="查清旧案")
draft_plan = await generate_plan(unit)
active_plan = await confirm_plan(unit, draft_plan.id)
brief = await generate_brief(active_plan.id)
run = await generate_draft(brief.id, fake_generator=ready_generator)
assert run.context_snapshot_json["plot_plan_revision_id"] == active_plan.id
assert run.status == "completed"

conflicting_run = await generate_draft(brief.id, fake_generator=decision_required_generator)
assert conflicting_run.status == "decision_required"
decision = await get_decision(conflicting_run.decision_id)
assert len(decision.options) in (2, 3)
assert decision.recommended_index is not None

resolution = await choose_decision(decision.id, option_index=decision.recommended_index)
assert resolution.draft_revision.status == "candidate"
assert original_unaffected_text in resolution.draft_revision.candidate_content
assert resolution.plan_revision.version == active_plan.version + 1

accepted = await accept_run(conflicting_run.id)
assert accepted.chapter.status == "draft"
published = await publish_chapter(accepted.chapter.id)
assert published.status == "locked"
assert await try_update_chapter(published.id, "改写") == 400
next_run = await generate_next_chapter(client, novel_id=novel["id"], headers=headers)
assert published.id in next_run.context_snapshot_json["published_chapter_ids"]
```

- [ ] **步骤 2：添加异常路径断言**

在同一测试模块中覆盖以下情况：没有冲突时不生成决策；低影响且可自动解决的问题不阻塞流程；审查冲突和生成冲突使用相同响应结构；作者资料更新创建新修订但不改变锁定内容；待处理决策阻止发布；作者资料更新后旧决策变为 `superseded`；供应商失败时不产生新的生效计划且不修改章节；跨用户请求返回 `404`。

- [ ] **步骤 3：添加真实 DeepSeek 集成验证**

`test_phase_3_dynamic_plot_planning_integration.py` 必须使用 `DeepSeekWritingGenerator`，创建已有大纲/角色/世界设定夹具，创建一章包含已知事实的锁定章节，并断言：

1. 生成的上下文包含作者资料快照和锁定章节 ID。
2. 返回的计划/草稿不等于任何 `FakePhase3WritingGenerator` 夹具字符串。
3. 审查或生成结果包含经过 Pydantic 校验的结构化字段。
4. 如果返回局部修订，`impact_scope` 之外的文本保持不变。

仅在明确配置密钥后运行：

```bash
cd backend
DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" .venv/bin/python -m pytest tests/test_phase_3_dynamic_plot_planning_integration.py -q
```

没有密钥时，预期测试收集成功并按指定原因跳过；有有效密钥时，预期真实 AI 场景通过，且决策方案不是后端预置数据。

- [ ] **步骤 4：运行全部后端测试**

运行：`cd backend && .venv/bin/python -m pytest tests/ -x -q`

预期：所有确定性测试通过；只有明确依赖密钥的真实集成测试可以跳过。

- [ ] **步骤 5：运行全部前端检查**

运行：`cd frontend && npm run test:unit && npm run type-check && npm run lint && npm run build`

预期：所有命令退出码均为 0。

### 任务 9：最终迁移、文档和实现审阅

**文件：**
- 如果自动生成结果需要审阅后的修正，修改 `backend/alembic/versions/d1e2f3a4b5c6_phase_3_dynamic_plot_planning.py`
- 只有当新模型未出现在 `Base.metadata` 中时，才修改 `backend/alembic/env.py`
- 创建：`docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md`
- 测试：`backend/tests/test_phase_3_dynamic_plot_planning.py`

**接口约定：**
- 迁移从 `c3d4e5f6a7b8` 升级，并能干净降级。
- 验收文档记录确定性测试和真实 AI 测试的准确命令及输出。

- [ ] **步骤 1：验证迁移链和 Schema 漂移**

运行：`cd backend && .venv/bin/python -m alembic heads`

预期：只有一个 head，即 `d1e2f3a4b5c6`。

运行：`cd backend && .venv/bin/python -m alembic upgrade c3d4e5f6a7b8 && .venv/bin/python -m alembic upgrade head`

预期：两个命令都退出码为 0；新运行时不依赖旧的 `volume_arcs` 或 `plan_versions` 表。

运行：`cd backend && .venv/bin/python -m alembic downgrade c3d4e5f6a7b8`

预期：所有 Phase 3 表和字段被删除，而 Phase 2 表保留。

- [ ] **步骤 2：检查最终 diff 的范围和锁定安全性**

运行：`git diff --stat && git diff -- backend/app/models backend/app/services backend/app/api backend/app/ai backend/tests frontend/src`

明确检查：没有写入路径在 `status == "locked"` 后赋值 `Chapter.content` 或删除章节；没有计划修订在 AI 校验前创建为 `status="active"`；没有决策端点返回硬编码方案。

- [ ] **步骤 3：编写验收记录**

在 `docs/superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md` 中记录：迁移 revision、确定性后端测试数量、真实 AI 测试命令/结果、前端测试/类型检查/lint/build 结果，以及任何因密钥而跳过的测试。如果真实 AI 场景没有成功运行，不得将 Phase 3 标记为完成。

- [ ] **步骤 4：运行最终验证命令**

```bash
cd backend && .venv/bin/python -m pytest tests/ -x -q
cd backend && .venv/bin/python -m alembic upgrade head
cd frontend && npm run test:unit
cd frontend && npm run type-check
cd frontend && npm run lint
cd frontend && npm run build
```

预期：每个命令退出码均为 0；任何跳过的测试都必须明确记录，不能计入真实 AI 验证通过。

## 设计稿覆盖自审

| 设计稿要求 | 计划覆盖 |
| --- | --- |
| 设计稿要求 | 计划覆盖 |
| --- | --- |
| 以既有作者资料启动 | 任务 1、3、4、8 |
| 作者资料有版本历史但已发布正典不可变 | 任务 1、3、6、8 |
| 剧情单元和可执行计划 | 任务 1、3、4 |
| 一次性确认计划 | 任务 3、7 |
| 写作上下文包含计划、作者资料、相关记忆和锁定正典 | 任务 3、4、8 |
| 写作生成阶段发现冲突 | 任务 2、4、5 |
| 草稿审查阶段发现冲突 | 任务 2、5、8 |
| 一个统一的决策流程 | 任务 2、5、6 |
| 两到三个真实方案和推荐意见 | 任务 2、5、7、8 |
| 无伪造方案的无法安全规划响应 | 任务 2、4、5 |
| 最小范围修订并保留未受影响正文 | 任务 2、6、7、8 |
| 草稿修订历史和差异 | 任务 1、6、7 |
| 接受草稿与发布分离 | 任务 6、7、8 |
| 锁定章节不可覆盖 | 任务 6、7、8 |
| 待处理决策阻止受影响内容发布 | 任务 5、6、8 |
| 新作者输入使旧决策失效 | 任务 3、6、8 |
| Phase 2 质量问题继续使用 ReviewIssue/PendingRepair | 任务 4、5、8 |
| 真实 DeepSeek 集成 | 任务 2、8、9 |
| 前后端测试、迁移和归属保护 | 任务 1、3、5、6、7、8、9 |

保存后，搜索本计划中的禁止占位符，要求没有匹配结果。类型一致性检查包括：API 请求、`ContextPackage.snapshot`、`WritingRun.context_snapshot_json`、前端类型和 AI 提示词中的 `plot_plan_revision_id` 都使用同一个整数 ID；后端和前端的决策方案索引都从 0 开始；`DraftRevision.status` 按 `candidate → applied` 流转且绝不改变锁定章节；两个发现入口都严格使用 `during_generation`/`during_review` 字面量。
