# Novel Agent — 前端初始化设计

> 日期：2026-06-25
> 状态：草案

## 1. 概述

本文档定义了 Novel Agent 前端初始化的完整设计方案，包括 TypeScript 类型系统、API 层、设计 Token 系统、通用组件库、路由与状态管理、以及页面视图。目标是完成与后端的无缝对接，建立统一风格的组件库，为后续开发提供基础。

### 技术栈

| 技术 | 用途 |
|------|------|
| Vue 3 (Composition API + `<script setup>`) | 前端框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Pinia | 状态管理 |
| Vue Router | 路由 |
| SCSS | 样式预处理 |
| Axios | HTTP 客户端 |

## 2. TypeScript 类型系统

位置：`src/types/`，与后端 Pydantic Schema 一一映射。

### `src/types/api.ts` — API 公共类型

```typescript
interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
```

### `src/types/auth.ts` — 认证类型

```typescript
interface RegisterRequest {
  username: string
  password: string
}

interface LoginRequest {
  username: string
  password: string
}

interface AuthResponse {
  token: string
  user_id: number
  username: string
}

interface User {
  id: number
  username: string
  created_at: string
  updated_at: string
}
```

### `src/types/novel.ts` — 小说/章节类型

```typescript
interface NovelCreate {
  title: string
  description?: string | null
}

interface NovelUpdate {
  title?: string | null
  description?: string | null
}

interface NovelListItem {
  id: number
  title: string
  description?: string | null
  created_at: string
  updated_at: string
}

interface NovelOut extends NovelListItem {
  chapters?: ChapterOut[]
}

interface ChapterCreate {
  title: string
  content?: string
}

interface ChapterUpdate {
  title?: string | null
  content?: string | null
}

interface ChapterOut {
  id: number
  novel_id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}
```

### `src/types/index.ts` — Barrel export

```typescript
export * from './api'
export * from './auth'
export * from './novel'
```

## 3. API 层

位置：`src/api/`，基于 Axios。

### `src/api/client.ts` — Axios 实例

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 请求拦截器：注入 token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：拆包 + 统一错误处理
client.interceptors.response.use(
  (response) => {
    const apiResponse = response.data as ApiResponse
    if (apiResponse.code !== 0) {
      return Promise.reject(new Error(apiResponse.message))
    }
    return apiResponse.data
  },
  (error) => {
    // 网络错误、401 等处理
    return Promise.reject(error)
  },
)
```

### `src/api/auth.ts`

```typescript
export function login(data: LoginRequest): Promise<AuthResponse>
export function register(data: RegisterRequest): Promise<AuthResponse>
```

### `src/api/novels.ts`

```typescript
export function listNovels(): Promise<NovelListItem[]>
export function createNovel(data: NovelCreate): Promise<NovelListItem>
export function getNovel(id: number): Promise<NovelOut>
export function updateNovel(id: number, data: NovelUpdate): Promise<NovelOut>
export function deleteNovel(id: number): Promise<void>

export function createChapter(novelId: number, data: ChapterCreate): Promise<ChapterOut>
export function getChapter(novelId: number, chapterId: number): Promise<ChapterOut>
export function updateChapter(novelId: number, chapterId: number, data: ChapterUpdate): Promise<ChapterOut>
export function deleteChapter(novelId: number, chapterId: number): Promise<void>
```

## 4. 设计 Token 系统

位置：`src/styles/`。

### 色彩系统

| Token | 值 | 用途 |
|-------|-----|------|
| `$color-primary` | `#D4A373` | 主色调 - 暖棕 |
| `$color-primary-light` | `#E9C9A0` | 主色浅色 |
| `$color-primary-dark` | `#B8895C` | 主色深色 |
| `$color-accent` | `#7FA1C3` | 点缀色 - 柔和蓝 |
| `$color-success` | `#8FBC8F` | 成功 |
| `$color-warning` | `#DDB892` | 警告 |
| `$color-error` | `#C97164` | 错误 |
| `$color-bg` | `#FDF8F0` | 页面背景 - 暖白 |
| `$color-bg-card` | `#FFFFFF` | 卡片背景 |
| `$color-bg-secondary` | `#F5EDE0` | 二级背景 |
| `$color-border` | `#E8DDD0` | 边框 |
| `$color-text` | `#3D3229` | 主文字 - 深暖灰 |
| `$color-text-secondary` | `#8A7D6F` | 次级文字 |
| `$color-text-placeholder` | `#BFB3A5` | 占位文字 |

### 间距

| Token | 值 |
|-------|-----|
| `$spacing-xs` | 4px |
| `$spacing-sm` | 8px |
| `$spacing-md` | 16px |
| `$spacing-lg` | 24px |
| `$spacing-xl` | 32px |
| `$spacing-2xl` | 48px |

### 圆角

| Token | 值 |
|-------|-----|
| `$radius-sm` | 4px |
| `$radius-md` | 8px |
| `$radius-lg` | 12px |
| `$radius-xl` | 16px |

### 阴影

| Token | 值 |
|-------|-----|
| `$shadow-sm` | `0 1px 3px rgba(61, 50, 41, 0.06)` |
| `$shadow-md` | `0 4px 12px rgba(61, 50, 41, 0.08)` |
| `$shadow-lg` | `0 8px 24px rgba(61, 50, 41, 0.10)` |

### 字体

| Token | 值 |
|-------|-----|
| `$font-family` | `'Noto Serif SC', 'Source Han Serif SC', 'Georgia', serif` |
| `$font-family-sans` | `'Noto Sans SC', 'Source Han Sans SC', 'Inter', sans-serif` |
| `$font-size-xs` | 12px |
| `$font-size-sm` | 14px |
| `$font-size-md` | 16px |
| `$font-size-lg` | 18px |
| `$font-size-xl` | 24px |
| `$font-size-2xl` | 32px |

## 5. 通用组件库

位置：`src/components/common/`

### AppButton.vue

- Props: `variant: 'primary' | 'secondary' | 'ghost' | 'danger'`, `size: 'sm' | 'md' | 'lg'`, `loading: boolean`, `disabled: boolean`
- Slots: default
- 转场动画：hover 背景色过渡

### AppInput.vue

- Props: `modelValue: string`, `type: 'text' | 'password'`, `placeholder`, `error: string`, `size`
- Emits: `update:modelValue`
- 样式：聚焦时主色边框 + 微妙阴影

### AppTextarea.vue

- Props: `modelValue: string`, `rows: number`, `placeholder`, `maxLength: number`, `error`
- Emits: `update:modelValue`

### AppCard.vue

- Props: `padding: string` (default: `$spacing-lg`)
- 样式：白色背景 + 圆角 + 阴影

### AppModal.vue

- Props: `visible: boolean`, `title: string`, `width: string`, `confirmText`, `cancelText`
- Emits: `update:visible`, `confirm`, `cancel`
- 遮罩层 + 居中卡片 + 进入/离开过渡动画

### AppConfirm.vue

- 基于 AppModal，简化确认场景
- Props: `visible`, `title`, `content`, `confirmText`, `confirmVariant`

### AppSpinner.vue

- Props: `size: 'sm' | 'md' | 'lg'`
- CSS 旋转动画

### AppEmpty.vue

- Props: `text: string`
- 居中图标 + 文字

### AppToast.vue

- 编程式调用：`toast.success(msg)`, `toast.error(msg)`, `toast.warning(msg)`
- 全局注册，通过 provide/inject 或 Pinia 共享
- 自动消失 + 进入/离开动画

## 6. 布局组件

位置：`src/components/layout/`

### AppLayout.vue

- 上：AppHeader
- 左：AppSidebar（折叠式）
- 右：RouterView（内容区）
- CSS Grid 或 Flexbox 布局

### AppHeader.vue

- Logo/应用名 左侧
- 用户信息 + 登出按钮 右侧

### AppSidebar.vue

- 导航菜单项列表
- 当前路由高亮
- 可选折叠（移动端抽屉）

## 7. 路由设计

```typescript
const routes = [
  { path: '/login',    component: LoginView,      meta: { guest: true } },
  { path: '/register', component: RegisterView,   meta: { guest: true } },
  { path: '/novels',   component: NovelListView,   meta: { auth: true } },
  { path: '/novels/:id',        component: NovelDetailView, meta: { auth: true } },
  { path: '/novels/:id/edit/:chapterId', component: EditorView, meta: { auth: true } },
  { path: '/',         redirect: '/novels' },
]
```

路由守卫逻辑：`meta.auth` 且无 token → 跳转 `/login`；`meta.guest` 且有 token → 跳转 `/novels`。

## 8. 状态管理

### useAuthStore

```typescript
interface AuthState {
  token: string | null
  userInfo: { id: number; username: string } | null
}

// Actions:
login(data: LoginRequest): Promise<void>
register(data: RegisterRequest): Promise<void>
logout(): void
restoreSession(): void  // 从 localStorage 恢复
```

### useNovelStore

```typescript
interface NovelState {
  novels: NovelListItem[]
  currentNovel: NovelOut | null
  currentChapter: ChapterOut | null
}

// Actions:
loadNovels(): Promise<void>
createNovel(data: NovelCreate): Promise<void>
getNovel(id: number): Promise<void>
updateNovel(id: number, data: NovelUpdate): Promise<void>
deleteNovel(id: number): Promise<void>
loadChapter(novelId: number, chapterId: number): Promise<void>
createChapter(novelId: number, data: ChapterCreate): Promise<void>
updateChapter(novelId: number, chapterId: number, data: ChapterUpdate): Promise<void>
deleteChapter(novelId: number, chapterId: number): Promise<void>
```

## 9. 页面视图

### LoginView / RegisterView

- 居中卡片布局（全屏垂直居中）
- AppInput × 2 (用户名、密码)
- AppButton 提交
- 底部切换链接（登录 ↔ 注册）
- 表单验证：用户名 2-50 字符、密码 ≥6 字符

### NovelListView

- AppLayout 包裹
- 顶部：标题 + "新建小说" AppButton → 弹出 AppModal (标题 + 描述表单)
- 内容：网格卡片布局，每张 AppCard 展示小说标题、描述片段、日期
- 空状态：AppEmpty
- 点击卡片 → 跳转 NovelDetailView
- 每张卡片有删除按钮（AppConfirm 确认）

### NovelDetailView

- AppLayout 包裹
- 左侧栏：章节列表（侧边栏样式），"新建章节" 按钮
- 右侧：选中章节的内容预览（AppCard），"编辑" 按钮 → 跳转 EditorView
- 章节项可删除（AppConfirm）

### EditorView

- 全屏沉浸式布局（隐藏侧栏）
- 顶栏：小说名称 + "← 返回" 按钮
- 章节标题 AppInput
- 大文本编辑区 AppTextarea（自适应高度）
- 底栏："保存" AppButton
- Ctrl+S 快捷键保存

## 10. 文件结构总览

```
frontend/src/
├── main.ts
├── App.vue
├── router/
│   └── index.ts
├── stores/
│   ├── auth.ts
│   └── novels.ts
├── api/
│   ├── client.ts
│   ├── auth.ts
│   └── novels.ts
├── types/
│   ├── index.ts
│   ├── api.ts
│   ├── auth.ts
│   └── novel.ts
├── styles/
│   ├── variables.scss
│   ├── reset.scss
│   ├── global.scss
│   └── mixins.scss
├── components/
│   ├── common/
│   │   ├── AppButton.vue
│   │   ├── AppInput.vue
│   │   ├── AppTextarea.vue
│   │   ├── AppCard.vue
│   │   ├── AppModal.vue
│   │   ├── AppConfirm.vue
│   │   ├── AppSpinner.vue
│   │   ├── AppEmpty.vue
│   │   └── AppToast.vue
│   └── layout/
│       ├── AppLayout.vue
│       ├── AppHeader.vue
│       └── AppSidebar.vue
└── views/
    ├── auth/
    │   ├── LoginView.vue
    │   └── RegisterView.vue
    ├── novels/
    │   ├── NovelListView.vue
    │   └── NovelDetailView.vue
    └── editor/
        └── EditorView.vue
```

## 11. 依赖清单

新增依赖 (package.json)：
- `axios` — HTTP 客户端
- `sass` — SCSS 编译

## 12. 验收标准

1. 所有 TypeScript 类型与后端 Pydantic Schema 字段完全对齐
2. 所有 API 接口调用参数与后端路由签名匹配，无 422/400 等参数错误
3. 组件库各组件独立可用，Props/Emits 类型完整
4. Design Token 系统统一，所有页面风格一致
5. 路由守卫正常工作，登录态/访客态正确跳转
6. 新增 axios/sass 依赖安装成功
