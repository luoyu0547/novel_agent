# novel-agent 系统需求文档第二版

第二版将 novel-agent 定位为**作者可控的 AI 自主写作工作台**：规划驱动写作，写作产生正文，正文反哺记忆，记忆再支撑后续规划和写作。

为便于连续阅读和按主题查找，第二版正文已拆分到同名目录。建议第一次阅读时按以下顺序进行。

## 推荐阅读顺序

| 顺序 | 文档 | 主要内容 |
|---|---|---|
| 1 | [定位与项目基线](./novel-agent系统需求文档第二版/01-定位与项目基线.md) | 产品定位、与第一版的关系、现有能力和核心缺口 |
| 2 | [核心概念](./novel-agent系统需求文档第二版/02-核心概念.md) | 蓝图、章节任务书、上下文包、写作运行、质量门禁等概念 |
| 3 | [Agent 设计](./novel-agent系统需求文档第二版/03-Agent设计.md) | 六类 Agent 的职责、输入、输出和边界 |
| 4 | [核心产品流程](./novel-agent系统需求文档第二版/04-核心产品流程.md) | 新书启动、已有小说续写、单章写作和记忆回写 |
| 5 | [数据结构需求](./novel-agent系统需求文档第二版/05-数据结构需求.md) | 需求层数据结构、字段和状态 |
| 6 | [阶段路线图](./novel-agent系统需求文档第二版/06-阶段路线图.md) | 阶段 0–5 的目标、范围、成功标准和关联设计 |
| 7 | [页面与设计原则](./novel-agent系统需求文档第二版/07-页面与设计原则.md) | 写作工作台页面、重点信息和产品原则 |
| 8 | [边界与讨论](./novel-agent系统需求文档第二版/08-边界与讨论.md) | 当前不建议优先建设的能力和仍需细化的问题 |
| 9 | [最小验证目标](./novel-agent系统需求文档第二版/09-最小验证目标.md) | 最小端到端闭环和第二版核心判断标准 |

## 有效关联文档

以下文档从不同层级描述项目需求、设计、实施与验收，均是理解第二版的有效上下文。

### 需求基础

- [novel-agent 系统需求文档第一版](./novel-agent系统需求文档第一版.md)

### Phase 1：最小自主写作闭环

- [设计规格](./superpowers/specs/2026-06-28-v2-phase-1-autonomous-writing-design.md)
- [实施计划](./superpowers/plans/2026-06-28-v2-phase-1-autonomous-writing.md)

### Phase 2：章节质量门禁

- [设计规格](./superpowers/specs/2026-07-04-v2-phase-2-quality-gate-design.md)
- [实施计划](./superpowers/plans/2026-07-04-v2-phase-2-quality-gate.md)

### Phase 3：动态剧情规划与写作协作

- [动态剧情规划设计](./superpowers/specs/2026-07-10-v2-phase-3-dynamic-plot-planning-design.md)
- [动态剧情规划实施计划](./superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning.md)
- [动态剧情规划验收记录](./superpowers/plans/2026-07-10-v2-phase-3-dynamic-plot-planning-acceptance.md)
- [生产闭环设计](./superpowers/specs/2026-07-12-v2-phase-3-production-closure-design.md)
- [生产闭环实施计划](./superpowers/plans/2026-07-12-v2-phase-3-production-closure.md)

## 维护约定

- 第一版、第二版拆分正文及相关设计、实施和验收文档均保持有效。
- 本文件只维护第二版的阅读入口和关联导航，不重复保存需求正文。
- 第二版正文统一在 `docs/novel-agent系统需求文档第二版/` 中维护。
- 调整正文时应保持页间导航、阶段关联和需求语义一致。
