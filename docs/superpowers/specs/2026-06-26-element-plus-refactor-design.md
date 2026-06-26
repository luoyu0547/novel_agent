# 前端 Element Plus 重构设计

> 日期：2026-06-26
> 状态：已确认，待出实施计划

## 背景与动机

当前前端存在三类问题：

1. **自制组件不完整**：`common/` 下缺少 `AppSelect`，章节状态、世界观分类等枚举字段用原生 `<select>` + 内联样式，与 `AppInput`/`AppTextarea` 的统一样式割裂。
2. **表单毫无美观**：新建/编辑表单字段平铺、无标签、无分组、无校验，间距靠 `<div style="height:12px">` 硬塞；章节正文编辑器是撑高的裸 `textarea`，衬线字体令牌未用上。
3. **路由未正确使用**：`App.vue` 用 `<router-view/>` 渲染视图，但每个视图各自 `import AppLayout` 当壳子并把内容当 slot 塞入，AppLayout 此前甚至误用 `<router-view/>`（渲染 depth 1，无嵌套路由→空）。布局在路由层不存在，每页重复挂载，Header/Sidebar 路由切换时重渲染。

## 目标

- 引入 Element Plus 作为唯一 UI 组件库，按需引入，主题定制为现有暖色文学风。
- 重构所有页面与组件，统一设计系统。
- 改为真正的嵌套路由，布局与页面解耦。
- 重做表单（标签/分组/校验/间距）与章节正文编辑器（沉浸式纯文本写作区）。

## 视觉方向

保留现有暖色文学风设计令牌（`src/styles/_variables.scss` 为唯一真相源）：
- 主色 `#D4A373`（棕金）、底色 `#FDF8F0`（米黄）、衬线字体 `Noto Serif SC`。
- 通过 Element Plus 的 SCSS 变量覆盖 + 运行时 CSS 变量兜底，让 `el-*` 组件服从该令牌。

## §1 依赖、按需引入与主题化

**新增依赖**（`package.json`）：
- `element-plus`（运行时）
- `unplugin-vue-components` + `unplugin-auto-import`（dev，按需自动引入 el-* 组件与 API）
- `@element-plus/icons-vue`

**按需引入配置**（`vite.config.ts`）：
- `AutoImport` + `Components` 插件配置 `ElementPlusResolver({ importStyle: 'sass' })`，SCSS 按需注入。

**主题化**（`src/styles/element-theme.scss`，在 Element Plus SCSS 变量被引用之前覆盖）：
- `$colors.primary` → `#D4A373`，lighter/darker 派生自 `$color-primary-light`/`$color-primary-dark`
- `$bg-color` / `$bg-color-page` → `#FDF8F0` / `#FFFFFF`
- `$text-color*` → 现有 `$color-text*`
- `$border-color` → `#E8DDD0`
- `$font-family` → `'Noto Serif SC', serif`
- 圆角/阴影映射到现有 `$radius-*` / `$shadow-*`
- `main.ts` 引入顺序：`element-theme.scss` → Element Plus 基础样式
- 运行时 `:root` CSS 变量兜底（`--el-color-primary` 等，覆盖动态计算色）
- `_variables.scss` 仍是设计令牌唯一真相源，element-theme.scss 从它 `@use` 派生

## §2 嵌套路由重构

**重构后结构**：
```
App.vue                     // 只放 <router-view/>（depth 0）
└─ 路由: component: AppLayout  // 布局作为父路由组件
   AppLayout.vue            // Header + Sidebar + <router-view/>（depth 1）
   └─ children 子路由:
      /novels               → NovelListView
      /novels/:id           → NovelDetailView (含 NovelWorkspaceTabs)
      /novels/:id/characters→ CharacterListView
      /novels/:id/settings  → WorldSettingsView
/login, /register           // 独立路由，不进 AppLayout（guest 页）
/novels/:id/edit/:chapterId → EditorView // 独立全屏路由，不进 AppLayout
```

**关键变化**：
- `AppLayout` 恢复使用 `<router-view/>`（这次正确——它是父路由组件）
- 所有子页面删除 `<AppLayout>...</AppLayout>` 包裹和 `import AppLayout`，内容直接作为子路由组件输出
- `/` redirect 到 `/novels`；路由守卫 `meta.auth`/`meta.guest` 逻辑不变，可放父路由 `beforeEnter` 对整组生效
- EditorView 保持独立全屏路由（写作沉浸感，不需要侧边栏）
- NovelWorkspaceTabs 保留为页面内导航组件（章节/角色/设定 Tab）

**导航高亮修正**：
- `AppSidebar` 用 `el-menu`（`router` 模式），`default-active` 绑定 `route.path`
- 侧边栏项：`我的小说`(`/novels`)；高亮按 `route.path` 匹配
- 进入小说详情后侧边栏仍高亮"我的小说"，小说内子页由 `NovelWorkspaceTabs` 区分——职责清晰

## §3 组件映射与替换

| 自制组件 | 替换为 | 处理方式 |
|---|---|---|
| `AppButton.vue` | `el-button` | 删除；`variant`→`type`，`size`→`size`，`loading` 透传 |
| `AppInput.vue` | `el-input` | 删除；`size`/`placeholder`/`disabled` 直接对应 |
| `AppTextarea.vue` | `el-input type="textarea"` | 删除；`rows`/`autosize` 支持 |
| `AppModal.vue` | `el-dialog` | 删除；`v-model:visible`→`v-model`，footer slot 自定义按钮 |
| `AppConfirm.vue` | `ElMessageBox.confirm()` | 删除组件，改调用式 API |
| `AppToast.vue` | `ElMessage` / `ElNotification` | 删除组件，改调用式 API |
| `AppSpinner.vue` | `v-loading` 指令 / `el-skeleton` | 删除；列表加载用 `v-loading`，初始用骨架屏 |
| `AppCard.vue` | `el-card` | 删除；`shadow="hover"` 替代 hover 阴影 |
| `AppEmpty.vue` | `el-empty` | 删除；`description` 透传 |
| 原生 `<select>` | `el-select` + `el-option` | 两处统一替换，枚举选项从 `types` 派生 |
| `NovelWorkspaceTabs.vue` | `el-tabs`（路由模式） | 保留文件，内部改 `el-tabs` |

**保留组件**：`AppLayout.vue` / `AppHeader.vue` / `AppSidebar.vue`（布局壳，Element Plus 无直接对应；`AppSidebar` 内部用 `el-menu`）。

**新增组件**：
- `src/components/editor/WritingEditor.vue` —— 沉浸式写作器（详见 §5）
- `src/constants/options.ts` —— 集中映射枚举 `value→label`，供 `el-option` 派生，消除视图硬编码，保证前后端枚举一致

## §4 表单重构

**统一容器**：所有新建/编辑弹窗内表单用 `el-form` 包裹：
- `label-position="top"`（标签在上方）
- `label-width` 统一，`el-form-item` 自带规范间距，删除所有 `<div style="height:12px">`
- `:model` 绑定 form ref，`:rules` 声明校验

**字段改造**（以"新建小说"为例）：
| 字段 | 控件 | label | 校验 |
|---|---|---|---|
| 标题 | `el-input` | 小说标题 | required, max 100 |
| 简介 | `el-input type=textarea :autosize={minRows:3}` | 小说简介 | 可选 |
| 类型 | `el-select filterable allow-create` | 小说类型 | 可选 |
| 风格指南 | `el-input type=textarea :autosize={minRows:4}` | 风格指南 | 可选 |

**校验与交互**：
- `el-form` 的 `rules` 声明必填/长度，提交前 `formRef.validate()` 校验失败阻止提交并自动标红
- `el-form-item` 的 `error` 自动显示，无需手写错误 `<p>`
- 弹窗确认按钮触发 `validate()`，通过后才调 store

**统一应用**：
- 新建/编辑小说（NovelListView / NovelDetailView）
- 新建/编辑章节（NovelDetailView 章节弹窗）
- 新建/编辑角色（CharacterListView）—— 8 字段分组：基本信息（名/身份/叙事功能）、性格与动机、表达（说话方式/行为规则/当前状态）
- 新建/编辑世界观设定（WorldSettingsView）—— 标题/分类(select)/内容
- 章节编辑器侧边栏标题输入

**分组排版**：长表单（角色卡 8 字段）用 `el-divider` 或 `el-card` 嵌套做视觉分组，避免一列到底；弹窗宽度按内容保留（角色卡 `720px`）。

## §5 章节正文编辑器（沉浸式写作区）

**新建 `src/components/editor/WritingEditor.vue`**，职责单一：接收 `v-model:content`、`v-model:title`，对外暴露字数与保存状态。

**布局**：
```
EditorView (全屏路由，无 AppLayout)
├─ 顶部栏: 返回 | 小说名 | 状态(el-select) | 字数统计 | 保存指示 | 专注开关
├─ 写作区 (居中 max-width 760px)
│  ├─ 章节标题: el-input 无边框大字号 (font-size-xl, font-weight-700)
│  └─ 正文: el-input type=textarea + :autosize={minRows:20}
│       · 衬线 Noto Serif SC, 18px, line-height 2
│       · $color-text 文本, $color-bg-card 背景
│       · :deep 去边框/去 resize/focus 无描边，纯排印美感
│  └─ 摘要区: el-divider 分隔, el-input textarea autosize
```

**实现选择**：`el-input type=textarea` + `:autosize` + `:deep` 样式覆盖，而非 contenteditable——纯文本场景 textarea 足矣，避免 contenteditable 光标/换行坑。

**字数统计**：computed 实时 `content.length`（中文按字符），顶部栏显示"已写 N 字"。

**自动保存**：debounce 3 秒自动 `updateChapter`，顶部栏显示"保存中…/已保存 HH:MM"状态（`el-text` small + loading 图标），Ctrl/Cmd+S 立即保存（保留现快捷键）。

**专注模式**：顶部栏"专注"按钮，开启后隐藏摘要区、收窄写作区、淡化顶部栏（opacity 过渡），点击写作区外恢复。纯 CSS 切换 class。

**状态下拉**：顶部 `el-select`，选项从 `types` 派生（草稿/已确认/锁定）。

## §6 各页面重构细节

**NovelListView（我的小说）**
- 标题栏 + "新建小说" `el-button type=primary`
- 空态：`el-empty` + "立即创建"引导按钮
- 卡片网格：`el-row` + `el-col`（`:gutter`, `:xs=24 :sm=12 :md=8` 响应式）
- 小说卡：`el-card shadow=hover`，hover 显示删除；标题 `el-link`，描述 `el-text truncated`，日期 `el-text small secondary`
- 新建弹窗：`el-dialog` + §4 表单

**NovelDetailView（小说详情）**
- `NovelWorkspaceTabs` 置顶
- 左侧章节列表：`el-menu`，`el-menu-item` 列章节，激活项高亮，hover 显示删除
- 右侧：小说标题 + "编辑信息"按钮；章节预览 `el-card` 包裹正文；无选中 `el-empty`
- 弹窗：`el-dialog` + `ElMessageBox.confirm`

**CharacterListView（角色卡片）**
- 顶部 Tab + "新建角色"按钮
- 卡片网格响应式
- 角色卡：`el-card`，字段用 `el-descriptions` 紧凑展示；行为规则用 `el-tag` 列表
- 编辑弹窗：`el-dialog width=720px` + §4 分组表单（三段 `el-divider`）

**WorldSettingsView（世界观设定）**
- 顶部 Tab + "新建设定"按钮
- 分类筛选：`el-radio-group` button 风格（`el-radio-button`）含"全部"
- 设定卡：`el-card`，标题 + `el-tag`（分类标签带派生颜色）+ 内容预览
- 编辑弹窗：标题 + 分类(`el-select`) + 内容(`el-input textarea autosize`)

**EditorView（章节编辑）**
- 全屏路由，不进 AppLayout
- 内部用 §5 的 `WritingEditor`
- 顶部栏：返回 + 小说名 + 状态 select + 字数 + 保存指示 + 专注开关

**AppHeader**
- 保留布局，"退出登录" `el-button text`；用户名 `el-text secondary`
- 用户名可做 `el-dropdown`（头像/用户名下拉含退出）——轻量增强

**AppSidebar**
- `el-menu` router 模式：`:default-active="route.path" router`
- `el-menu-item index="/novels"`"我的小说"
- 为后续扩展留接口

## §7 测试与验证策略

**单元测试**：
- `App.spec.ts` 保留（App.vue 仍只含 `<router-view/>`）
- `behaviorRules.spec.ts` 保留不动
- 新增 `WritingEditor.spec.ts`：测 `v-model` 双向绑定、字数统计、debounce 自动保存
- 表单校验测试：必填项标红、`validate()` 失败阻止提交

**类型检查**：`npm run type-check` 通过；unplugin 生成 `components.d.ts`/`auto-imports.d.ts`；删除自制组件后清理悬空 import。

**Lint**：`npm run lint` 通过（不含既有 `client.ts` `any` 报错）；新增代码不引入新 `any`。

**E2E（Playwright）**：`npm run test:e2e`；若现有用例基于旧自制组件 class 选择器失效，同步更新选择器到 el-* 生成 class 或加 `data-testid`。关键路径手测：登录→新建小说→进详情→新建章节→进编辑器写作→保存→新建角色/设定。

**验证顺序**：
1. `npm run type-check`
2. `npm run lint`（不含既有 client.ts 报错）
3. `npm run test:unit`
4. `npm run build`（确认按需引入打包无报错）
5. `npm run dev` 手测关键路径 + 截图核对暖色主题生效

**回归点**：
- AppLayout 嵌套路由切换时 Header/Sidebar 不重渲染（路由正确性验证）
- `el-dialog` 的 `v-model` 与原 `v-model:visible` 行为一致
- `ElMessageBox.confirm` 的 Promise 返回与原 emit 事件流等价

## 范围边界

- 本次重构覆盖：依赖引入、主题化、嵌套路由、组件映射替换、表单重构、写作器、各页面。
- 不在本次范围：`client.ts` 既有 `any` 报错、后端代码、新增业务功能（如回收站等后续扩展）。
