# Novel Agent 前端初始化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成前端 TypeScript 类型系统、API 层、设计 Token、组件库、路由、Store、页面视图的初始化，与后端无缝对接。

**Architecture:** Vue 3 Composition API + TypeScript + Pinia + Vue Router + SCSS + Axios。纯手写组件，暖色简约风设计系统，与后端 FastAPI 一一对齐。

**Tech Stack:** Vue 3.5, TypeScript 6, Vite 8, Pinia 3, Vue Router 5, SCSS (sass), Axios

**Vite proxy:** `/api` → `http://localhost:8000` (dev only)

## Global Constraints

- TypeScript 类型与后端 Pydantic Schema 字段完全对齐（见 spec）
- 所有组件使用 `<script setup lang="ts">` + scoped SCSS
- 设计 Token 统一引用 `src/styles/_variables.scss`
- 不使用第三方 UI 组件库，全部手写
- 后端 API 前缀 `/api/v1`，统一响应格式 `{code, message, data}`
- JWT token 存储在 `localStorage`，key 为 `token`
- 命名规范：组件 `PascalCase.vue`，文件 `camelCase.ts`，类型 `PascalCase`
- 路由守卫：`meta.auth` 需登录，`meta.guest` 仅访客
- 每次 commit 信息前缀 `feat: ` 或 `chore: `

---

### Task 1: 安装依赖 + Vite proxy 配置

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Consumes: existing project scaffold
- Produces: axios + sass installed，Vite proxy 配置完成

- [ ] **Step 1: 安装依赖**

```bash
npm install axios
npm install -D sass
```

- [ ] **Step 2: 更新 vite.config.ts 添加 proxy**

```typescript
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig({
  plugins: [vue(), vueJsx(), vueDevTools()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
```

- [ ] **Step 3: 验证安装**

```bash
node -e "require('axios')" && echo "axios OK"
npx sass --version && echo "sass OK"
```

Expected: 无报错。

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts
git commit -m "chore: install axios, sass and configure vite proxy"
```

---

### Task 2: 创建 TypeScript 类型定义

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/types/auth.ts`
- Create: `frontend/src/types/novel.ts`
- Create: `frontend/src/types/index.ts`

**Interfaces:**
- Consumes: nothing (independent)
- Produces: 全部与后端对齐的类型

- [ ] **Step 1: 创建 src/types/api.ts**

```typescript
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
```

- [ ] **Step 2: 创建 src/types/auth.ts**

```typescript
export interface RegisterRequest {
  username: string
  password: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface AuthResponse {
  token: string
  user_id: number
  username: string
}

export interface User {
  id: number
  username: string
  created_at: string
  updated_at: string
}
```

- [ ] **Step 3: 创建 src/types/novel.ts**

```typescript
export interface NovelCreate {
  title: string
  description?: string | null
}

export interface NovelUpdate {
  title?: string | null
  description?: string | null
}

export interface NovelListItem {
  id: number
  title: string
  description?: string | null
  created_at: string
  updated_at: string
}

export interface ChapterCreate {
  title: string
  content?: string
}

export interface ChapterUpdate {
  title?: string | null
  content?: string | null
}

export interface ChapterOut {
  id: number
  novel_id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface NovelOut extends NovelListItem {
  chapters?: ChapterOut[]
}
```

- [ ] **Step 4: 创建 src/types/index.ts**

```typescript
export * from './api'
export * from './auth'
export * from './novel'
```

- [ ] **Step 5: TypeScript 编译验证**

```bash
npx vue-tsc --noEmit
```

Expected: 无错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/
git commit -m "feat: add TypeScript type definitions matching backend schemas"
```

---

### Task 3: 创建 SCSS 设计系统

**Files:**
- Create: `frontend/src/styles/_variables.scss`
- Create: `frontend/src/styles/_mixins.scss`
- Create: `frontend/src/styles/reset.scss`
- Create: `frontend/src/styles/global.scss`

**Interfaces:**
- Consumes: nothing (独立设计 token)
- Produces: SCSS 变量、mixins、reset、全局样式

- [ ] **Step 1: 创建 src/styles/_variables.scss**

```scss
// === 色彩系统 ===
$color-primary: #D4A373;
$color-primary-light: #E9C9A0;
$color-primary-dark: #B8895C;
$color-accent: #7FA1C3;
$color-success: #8FBC8F;
$color-warning: #DDB892;
$color-error: #C97164;
$color-bg: #FDF8F0;
$color-bg-card: #FFFFFF;
$color-bg-secondary: #F5EDE0;
$color-border: #E8DDD0;
$color-text: #3D3229;
$color-text-secondary: #8A7D6F;
$color-text-placeholder: #BFB3A5;

// === 间距 ===
$spacing-xs: 4px;
$spacing-sm: 8px;
$spacing-md: 16px;
$spacing-lg: 24px;
$spacing-xl: 32px;
$spacing-2xl: 48px;

// === 圆角 ===
$radius-sm: 4px;
$radius-md: 8px;
$radius-lg: 12px;
$radius-xl: 16px;

// === 阴影 ===
$shadow-sm: 0 1px 3px rgba(61, 50, 41, 0.06);
$shadow-md: 0 4px 12px rgba(61, 50, 41, 0.08);
$shadow-lg: 0 8px 24px rgba(61, 50, 41, 0.10);

// === 字体 ===
$font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Georgia', serif;
$font-family-sans: 'Noto Sans SC', 'Source Han Sans SC', 'Inter', sans-serif;
$font-size-xs: 12px;
$font-size-sm: 14px;
$font-size-md: 16px;
$font-size-lg: 18px;
$font-size-xl: 24px;
$font-size-2xl: 32px;

// === 断点 ===
$breakpoint-sm: 640px;
$breakpoint-md: 768px;
$breakpoint-lg: 1024px;
$breakpoint-xl: 1280px;

// === 过渡 ===
$transition-fast: 0.15s ease;
$transition-normal: 0.25s ease;
```

- [ ] **Step 2: 创建 src/styles/_mixins.scss**

```scss
@use 'variables' as *;

@mixin flex-center { display: flex; align-items: center; justify-content: center; }
@mixin text-ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@mixin card { background: $color-bg-card; border-radius: $radius-lg; box-shadow: $shadow-sm; }
@mixin focus-ring { outline: none; &:focus-visible { box-shadow: 0 0 0 2px rgba($color-primary, 0.3); } }
```

- [ ] **Step 3: 创建 src/styles/reset.scss**

```scss
@use 'variables' as *;

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: $font-size-md; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body { font-family: $font-family-sans; color: $color-text; background: $color-bg; line-height: 1.6; }
a { color: $color-primary-dark; text-decoration: none; &:hover { color: $color-primary; } }
button { cursor: pointer; border: none; background: none; font-family: inherit; font-size: inherit; }
input, textarea { font-family: inherit; font-size: inherit; }
ul, ol { list-style: none; }
```

- [ ] **Step 4: 创建 src/styles/global.scss**

```scss
@use 'variables' as *;

.page-enter-active, .page-leave-active { transition: opacity $transition-normal; }
.page-enter-from, .page-leave-to { opacity: 0; }
```

- [ ] **Step 5: 验证 SCSS 编译**

```bash
npx sass src/styles/global.scss --load-path=src/styles
```

Expected: 无错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/
git commit -m "feat: add SCSS design system with variables, mixins, reset, global styles"
```

---

### Task 4: 创建 API 客户端层

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/novels.ts`

**Interfaces:**
- Consumes: `ApiResponse` from Task 2
- Produces: `client` (axios instance), `login()`, `register()`, CRUD functions for novels/chapters

- [ ] **Step 1: 创建 src/api/client.ts**

```typescript
import axios from 'axios'
import type { ApiResponse } from '@/types'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) { config.headers.Authorization = `Bearer ${token}` }
  return config
})

client.interceptors.response.use(
  (response) => {
    const apiResponse = response.data as ApiResponse<unknown>
    if (apiResponse.code !== 0) {
      return Promise.reject(new Error(apiResponse.message))
    }
    return apiResponse.data as unknown
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default client
```

- [ ] **Step 2: 创建 src/api/auth.ts**

```typescript
import client from './client'
import type { LoginRequest, RegisterRequest, AuthResponse } from '@/types'

export function login(data: LoginRequest): Promise<AuthResponse> {
  return client.post('/auth/login', data)
}
export function register(data: RegisterRequest): Promise<AuthResponse> {
  return client.post('/auth/register', data)
}
```

- [ ] **Step 3: 创建 src/api/novels.ts**

```typescript
import client from './client'
import type { NovelCreate, NovelUpdate, NovelListItem, NovelOut, ChapterCreate, ChapterUpdate, ChapterOut } from '@/types'

export function listNovels(): Promise<NovelListItem[]> { return client.get('/novels') }
export function createNovel(data: NovelCreate): Promise<NovelListItem> { return client.post('/novels', data) }
export function getNovel(id: number): Promise<NovelOut> { return client.get(`/novels/${id}`) }
export function updateNovel(id: number, data: NovelUpdate): Promise<NovelOut> { return client.put(`/novels/${id}`, data) }
export function deleteNovel(id: number): Promise<void> { return client.delete(`/novels/${id}`) }
export function createChapter(novelId: number, data: ChapterCreate): Promise<ChapterOut> { return client.post(`/novels/${novelId}/chapters`, data) }
export function getChapter(novelId: number, chapterId: number): Promise<ChapterOut> { return client.get(`/novels/${novelId}/chapters/${chapterId}`) }
export function updateChapter(novelId: number, chapterId: number, data: ChapterUpdate): Promise<ChapterOut> { return client.put(`/novels/${novelId}/chapters/${chapterId}`, data) }
export function deleteChapter(novelId: number, chapterId: number): Promise<void> { return client.delete(`/novels/${novelId}/chapters/${chapterId}`) }
```

- [ ] **Step 4: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: add axios API client with auth interceptor and API functions"
```

---

### Task 5: 创建 Pinia Stores

**Files:**
- Delete: `frontend/src/stores/counter.ts`
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/stores/novels.ts`

**Interfaces:**
- Consumes: API functions from Task 4, types from Task 2
- Produces: `useAuthStore`, `useNovelStore`

- [ ] **Step 1: 删除旧的 counter store**

```bash
rm frontend/src/stores/counter.ts
```

- [ ] **Step 2: 创建 src/stores/auth.ts**

```typescript
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister } from '@/api/auth'
import type { LoginRequest, RegisterRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userInfo = ref<{ id: number; username: string } | null>(null)

  async function login(data: LoginRequest) {
    const res = await apiLogin(data)
    token.value = res.token
    userInfo.value = { id: res.user_id, username: res.username }
    localStorage.setItem('token', res.token)
  }

  async function register(data: RegisterRequest) {
    const res = await apiRegister(data)
    token.value = res.token
    userInfo.value = { id: res.user_id, username: res.username }
    localStorage.setItem('token', res.token)
  }

  function logout() {
    token.value = null
    userInfo.value = null
    localStorage.removeItem('token')
  }

  function restoreSession() {
    const t = localStorage.getItem('token')
    if (t) token.value = t
  }

  return { token, userInfo, login, register, logout, restoreSession }
})
```

- [ ] **Step 3: 创建 src/stores/novels.ts**

```typescript
import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as novelsApi from '@/api/novels'
import type { NovelCreate, NovelUpdate, NovelListItem, NovelOut, ChapterCreate, ChapterUpdate, ChapterOut } from '@/types'

export const useNovelStore = defineStore('novel', () => {
  const novels = ref<NovelListItem[]>([])
  const currentNovel = ref<NovelOut | null>(null)
  const currentChapter = ref<ChapterOut | null>(null)

  async function loadNovels() { novels.value = await novelsApi.listNovels() }
  async function createNovel(data: NovelCreate) { const n = await novelsApi.createNovel(data); novels.value.unshift(n) }
  async function getNovel(id: number) { currentNovel.value = await novelsApi.getNovel(id) }
  async function updateNovel(id: number, data: NovelUpdate) { await novelsApi.updateNovel(id, data); if (currentNovel.value?.id === id) currentNovel.value = await novelsApi.getNovel(id) }
  async function deleteNovel(id: number) { await novelsApi.deleteNovel(id); novels.value = novels.value.filter((n) => n.id !== id) }
  async function createChapter(novelId: number, data: ChapterCreate) { const c = await novelsApi.createChapter(novelId, data); if (currentNovel.value?.id === novelId) { currentNovel.value.chapters = currentNovel.value.chapters || []; currentNovel.value.chapters.push(c) } }
  async function loadChapter(novelId: number, chapterId: number) { currentChapter.value = await novelsApi.getChapter(novelId, chapterId) }
  async function updateChapter(novelId: number, chapterId: number, data: ChapterUpdate) { await novelsApi.updateChapter(novelId, chapterId, data); if (currentNovel.value?.id === novelId) currentNovel.value = await novelsApi.getNovel(novelId) }
  async function deleteChapter(novelId: number, chapterId: number) { await novelsApi.deleteChapter(novelId, chapterId); if (currentNovel.value?.id === novelId && currentNovel.value.chapters) currentNovel.value.chapters = currentNovel.value.chapters.filter((c) => c.id !== chapterId) }

  return { novels, currentNovel, currentChapter, loadNovels, createNovel, getNovel, updateNovel, deleteNovel, createChapter, loadChapter, updateChapter, deleteChapter }
})
```

- [ ] **Step 4: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/
git commit -m "feat: add auth and novel Pinia stores"
```

---

### Task 6: 创建 Vue Router + 守卫

**Files:**
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: view 组件 (lazy-loaded, 将在后续 task 中创建)
- Produces: 路由表 + `beforeEach` 守卫

- [ ] **Step 1: 重写 src/router/index.ts**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue'), meta: { guest: true } },
    { path: '/novels', name: 'novels', component: () => import('@/views/novels/NovelListView.vue'), meta: { auth: true } },
    { path: '/novels/:id', name: 'novel-detail', component: () => import('@/views/novels/NovelDetailView.vue'), meta: { auth: true } },
    { path: '/novels/:id/edit/:chapterId', name: 'editor', component: () => import('@/views/editor/EditorView.vue'), meta: { auth: true } },
    { path: '/', redirect: '/novels' },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.auth && !token) next('/login')
  else if (to.meta.guest && token) next('/novels')
  else next()
})

export default router
```

- [ ] **Step 2: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "feat: add Vue Router with route guards"
```

---

### Task 7: 创建基础通用组件 (Button, Input, Textarea, Card)

**Files:**
- Create: `frontend/src/components/common/AppButton.vue`
- Create: `frontend/src/components/common/AppInput.vue`
- Create: `frontend/src/components/common/AppTextarea.vue`
- Create: `frontend/src/components/common/AppCard.vue`

**Interfaces:**
- Consumes: SCSS variables/mixins from Task 3
- Produces: 四个基础 UI 组件

- [ ] **Step 1: 创建 AppButton.vue**

```vue
<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>(), { variant: 'primary', size: 'md', loading: false, disabled: false })

defineEmits<{ click: [e: MouseEvent] }>()
</script>

<template>
  <button
    class="app-btn"
    :class="[`app-btn--${variant}`, `app-btn--${size}`, { 'app-btn--loading': loading }]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="app-btn__spinner" />
    <slot />
  </button>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: $radius-md; font-weight: 500; transition: all $transition-fast; white-space: nowrap;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &--sm { padding: 4px 16px; font-size: $font-size-sm; }
  &--md { padding: 8px 24px; font-size: $font-size-md; }
  &--lg { padding: 16px 32px; font-size: $font-size-lg; }
  &--primary { background: $color-primary; color: #fff; &:not(:disabled):hover { background: $color-primary-dark; } }
  &--secondary { background: $color-bg-secondary; color: $color-text; &:not(:disabled):hover { background: $color-border; } }
  &--ghost { background: transparent; color: $color-text-secondary; &:not(:disabled):hover { background: $color-bg-secondary; color: $color-text; } }
  &--danger { background: $color-error; color: #fff; &:not(:disabled):hover { background: darken($color-error, 8%); } }
  &--loading { cursor: wait; }
  &__spinner { width: 16px; height: 16px; border: 2px solid currentColor; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; }
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 2: 创建 AppInput.vue**

```vue
<script setup lang="ts">
defineProps<{ modelValue: string; type?: 'text' | 'password'; placeholder?: string; error?: string; size?: 'sm' | 'md' | 'lg' }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <input
      :type="type || 'text'" :value="modelValue" :placeholder="placeholder"
      :class="[`app-input__field`, `app-input__field--${size || 'md'}`]"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="app-input__error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-input { width: 100%;
  &__field { width: 100%; border: 1px solid $color-border; border-radius: $radius-md; background: $color-bg-card; color: $color-text; transition: all $transition-fast;
    &::placeholder { color: $color-text-placeholder; }
    &:focus { border-color: $color-primary; box-shadow: 0 0 0 3px rgba($color-primary, 0.15); outline: none; }
    &--sm { padding: 4px 8px; font-size: $font-size-sm; }
    &--md { padding: 8px 16px; font-size: $font-size-md; }
    &--lg { padding: 16px 24px; font-size: $font-size-lg; } }
  &--error &__field { border-color: $color-error; }
  &__error { margin-top: 4px; font-size: $font-size-sm; color: $color-error; } }
</style>
```

- [ ] **Step 3: 创建 AppTextarea.vue**

```vue
<script setup lang="ts">
defineProps<{ modelValue: string; rows?: number; placeholder?: string; maxLength?: number; error?: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="app-textarea" :class="{ 'app-textarea--error': error }">
    <textarea
      :value="modelValue" :rows="rows || 6" :placeholder="placeholder" :maxlength="maxLength"
      class="app-textarea__field"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
    <p v-if="error" class="app-textarea__error">{{ error }}</p>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-textarea { width: 100%;
  &__field { width: 100%; padding: 8px 16px; border: 1px solid $color-border; border-radius: $radius-md; background: $color-bg-card; color: $color-text; font-size: $font-size-md; line-height: 1.8; resize: vertical; transition: all $transition-fast;
    &::placeholder { color: $color-text-placeholder; }
    &:focus { border-color: $color-primary; box-shadow: 0 0 0 3px rgba($color-primary, 0.15); outline: none; } }
  &--error &__field { border-color: $color-error; }
  &__error { margin-top: 4px; font-size: $font-size-sm; color: $color-error; } }
</style>
```

- [ ] **Step 4: 创建 AppCard.vue**

```vue
<script setup lang="ts">
withDefaults(defineProps<{ padding?: string }>(), { padding: '24px' })
</script>

<template>
  <div class="app-card" :style="{ padding }"><slot /></div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-card { background: $color-bg-card; border-radius: $radius-lg; box-shadow: $shadow-sm; border: 1px solid $color-border; }
</style>
```

- [ ] **Step 5: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/common/AppButton.vue frontend/src/components/common/AppInput.vue frontend/src/components/common/AppTextarea.vue frontend/src/components/common/AppCard.vue
git commit -m "feat: add AppButton, AppInput, AppTextarea, AppCard components"
```
### Task 8: 创建弹窗与反馈组件

**Files:**
- Create: `frontend/src/components/common/AppModal.vue`
- Create: `frontend/src/components/common/AppConfirm.vue`
- Create: `frontend/src/components/common/AppSpinner.vue`
- Create: `frontend/src/components/common/AppEmpty.vue`
- Create: `frontend/src/components/common/AppToast.vue`

**Interfaces:**
- Consumes: `AppButton` from Task 7, SCSS variables
- Produces: 模态框、确认弹窗、加载指示器、空状态、消息提示组件

- [ ] **Step 1: 创建 AppModal.vue**

```vue
<script setup lang="ts">
import AppButton from './AppButton.vue'
withDefaults(defineProps<{ visible: boolean; title?: string; width?: string; confirmText?: string; cancelText?: string }>(), { width: '480px' })
const emit = defineEmits<{ 'update:visible': [value: boolean]; confirm: []; cancel: [] }>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="emit('update:visible', false)">
        <div class="modal-content" :style="{ maxWidth: width }">
          <div class="modal-header">
            <h3 class="modal-title">{{ title }}</h3>
            <button class="modal-close" @click="emit('update:visible', false)">✕</button>
          </div>
          <div class="modal-body"><slot /></div>
          <div v-if="confirmText || cancelText" class="modal-footer">
            <AppButton v-if="cancelText" variant="secondary" @click="emit('cancel')">{{ cancelText }}</AppButton>
            <AppButton v-if="confirmText" @click="emit('confirm')">{{ confirmText }}</AppButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { width: 90%; background: $color-bg-card; border-radius: $radius-xl; box-shadow: $shadow-lg; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-lg; border-bottom: 1px solid $color-border; }
.modal-title { font-size: $font-size-lg; font-weight: 600; }
.modal-close { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: $radius-sm; color: $color-text-secondary; transition: all $transition-fast; &:hover { background: $color-bg-secondary; color: $color-text; } }
.modal-body { padding: $spacing-lg; }
.modal-footer { display: flex; justify-content: flex-end; gap: $spacing-sm; padding: $spacing-lg; border-top: 1px solid $color-border; }
.modal-enter-active, .modal-leave-active { transition: opacity $transition-normal; .modal-content { transition: transform $transition-normal; } }
.modal-enter-from, .modal-leave-to { opacity: 0; .modal-content { transform: scale(0.95); } }
</style>
```

- [ ] **Step 2: 创建 AppConfirm.vue**

```vue
<script setup lang="ts">
import AppModal from './AppModal.vue'
withDefaults(defineProps<{ visible: boolean; title?: string; content?: string; confirmText?: string; cancelText?: string; confirmVariant?: 'primary' | 'danger' }>(), { title: '确认操作', content: '确定要执行此操作吗？', confirmText: '确认', cancelText: '取消', confirmVariant: 'primary' })
const emit = defineEmits<{ 'update:visible': [value: boolean]; confirm: []; cancel: [] }>()
</script>

<template>
  <AppModal :visible="visible" :title="title" :confirm-text="confirmText" :cancel-text="cancelText"
    @update:visible="emit('update:visible', $event)" @confirm="emit('confirm')" @cancel="emit('cancel')">
    <p>{{ content }}</p>
  </AppModal>
</template>
```

- [ ] **Step 3: 创建 AppSpinner.vue**

```vue
<script setup lang="ts">
withDefaults(defineProps<{ size?: 'sm' | 'md' | 'lg' }>(), { size: 'md' })
</script>
<template><div class="app-spinner" :class="`app-spinner--${size}`" /></template>
<style scoped lang="scss">
.app-spinner { border-radius: 50%; border: 3px solid currentColor; border-top-color: transparent; animation: spin 0.6s linear infinite; color: inherit;
  &--sm { width: 20px; height: 20px; border-width: 2px; } &--md { width: 32px; height: 32px; } &--lg { width: 48px; height: 48px; border-width: 4px; } }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Step 4: 创建 AppEmpty.vue**

```vue
<script setup lang="ts">
withDefaults(defineProps<{ text?: string }>(), { text: '暂无数据' })
</script>
<template>
  <div class="app-empty">
    <div class="app-empty__icon">📝</div>
    <p class="app-empty__text">{{ text }}</p>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-empty { display: flex; flex-direction: column; align-items: center; padding: $spacing-2xl; color: $color-text-secondary;
  &__icon { font-size: 48px; margin-bottom: $spacing-md; opacity: 0.5; } &__text { font-size: $font-size-md; } }
</style>
```

- [ ] **Step 5: 创建 AppToast.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
interface ToastItem { id: number; message: string; type: 'success' | 'error' | 'warning' }
const toasts = ref<ToastItem[]>([])
let nextId = 0
function add(message: string, type: ToastItem['type']) { const id = nextId++; toasts.value.push({ id, message, type }); setTimeout(() => { remove(id) }, 3000) }
function remove(id: number) { toasts.value = toasts.value.filter((t) => t.id !== id) }
function success(message: string) { add(message, 'success') }
function error(message: string) { add(message, 'error') }
function warning(message: string) { add(message, 'warning') }
defineExpose({ success, error, warning })
</script>
<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div v-for="toast in toasts" :key="toast.id" class="toast-item" :class="`toast-item--${toast.type}`">{{ toast.message }}</div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.toast-container { position: fixed; top: $spacing-lg; right: $spacing-lg; z-index: 2000; display: flex; flex-direction: column; gap: $spacing-sm; }
.toast-item { padding: $spacing-sm $spacing-lg; border-radius: $radius-md; font-size: $font-size-sm; color: #fff; box-shadow: $shadow-md; min-width: 200px;
  &--success { background: $color-success; } &--error { background: $color-error; } &--warning { background: $color-warning; color: $color-text; } }
.toast-enter-active { transition: all $transition-normal; } .toast-leave-active { transition: all $transition-fast; }
.toast-enter-from { opacity: 0; transform: translateX(100%); } .toast-leave-to { opacity: 0; transform: translateX(100%); }
</style>
```

- [ ] **Step 6: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/common/
git commit -m "feat: add AppModal, AppConfirm, AppSpinner, AppEmpty, AppToast components"
```

---

### Task 9: 创建布局组件

**Files:**
- Create: `frontend/src/components/layout/AppLayout.vue`
- Create: `frontend/src/components/layout/AppHeader.vue`
- Create: `frontend/src/components/layout/AppSidebar.vue`

**Interfaces:**
- Consumes: `useAuthStore`, router
- Produces: 主布局组件

- [ ] **Step 1: 创建 AppHeader.vue**

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/common/AppButton.vue'
const router = useRouter()
const auth = useAuthStore()
function handleLogout() { auth.logout(); router.push('/login') }
</script>
<template>
  <header class="app-header">
    <div class="app-header__left"><span class="app-header__logo">Novel Agent</span></div>
    <div class="app-header__right">
      <span v-if="auth.userInfo" class="app-header__user">{{ auth.userInfo.username }}</span>
      <AppButton variant="ghost" size="sm" @click="handleLogout">退出登录</AppButton>
    </div>
  </header>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-header { display: flex; align-items: center; justify-content: space-between; height: 56px; padding: 0 $spacing-lg; background: $color-bg-card; border-bottom: 1px solid $color-border;
  &__logo { font-family: $font-family; font-size: $font-size-lg; font-weight: 700; color: $color-primary-dark; }
  &__right { display: flex; align-items: center; gap: $spacing-md; }
  &__user { font-size: $font-size-sm; color: $color-text-secondary; } }
</style>
```

- [ ] **Step 2: 创建 AppSidebar.vue**

```vue
<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
const route = useRoute(); const router = useRouter()
interface NavItem { label: string; path: string; icon: string }
const navItems: NavItem[] = [{ label: '我的小说', path: '/novels', icon: '' }]
</script>
<template>
  <aside class="app-sidebar">
    <nav class="app-sidebar__nav">
      <button v-for="item in navItems" :key="item.path" class="app-sidebar__item" :class="{ 'app-sidebar__item--active': route.path.startsWith('/novels') }" @click="router.push(item.path)">
        <span class="app-sidebar__label">{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-sidebar { width: 200px; background: $color-bg-card; border-right: 1px solid $color-border; padding: $spacing-md 0;
  &__nav { display: flex; flex-direction: column; gap: 2px; }
  &__item { display: flex; align-items: center; gap: $spacing-sm; padding: $spacing-sm $spacing-lg; font-size: $font-size-sm; color: $color-text-secondary; transition: all $transition-fast; text-align: left; width: 100%;
    &:hover { background: $color-bg-secondary; color: $color-text; }
    &--active { background: $color-bg-secondary; color: $color-primary-dark; font-weight: 600; border-right: 3px solid $color-primary; } } }
</style>
```

- [ ] **Step 3: 创建 AppLayout.vue**

```vue
<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
</script>
<template>
  <div class="app-layout">
    <AppHeader />
    <div class="app-layout__body">
      <AppSidebar />
      <main class="app-layout__content"><router-view /></main>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-layout { min-height: 100vh; display: flex; flex-direction: column;
  &__body { display: flex; flex: 1; }
  &__content { flex: 1; padding: $spacing-lg; overflow-y: auto; background: $color-bg; } }
</style>
```

- [ ] **Step 4: TypeScript 验证** `npx vue-tsc --noEmit`
- [ ] **Step 5: Commit** `git add frontend/src/components/layout/ && git commit -m "feat: add AppLayout, AppHeader, AppSidebar layout components"`

---

### Task 10: 创建认证页面

**Files:**
- Create: `frontend/src/views/auth/LoginView.vue`
- Create: `frontend/src/views/auth/RegisterView.vue`

**Interfaces:**
- Consumes: `useAuthStore`, `AppButton`, `AppInput`
- Produces: 登录/注册页面

- [ ] **Step 1: 创建 LoginView.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'

const router = useRouter()
const auth = useAuthStore()
const username = ref(''); const password = ref(''); const error = ref(''); const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) { error.value = '请填写用户名和密码'; return }
  error.value = ''; loading.value = true
  try { await auth.login({ username: username.value, password: password.value }); router.push('/novels') }
  catch (e: unknown) { error.value = (e as Error).message || '登录失败' }
  finally { loading.value = false }
}
</script>
<template>
  <div class="auth-view">
    <div class="auth-card">
      <h1 class="auth-card__title">Novel Agent</h1>
      <p class="auth-card__subtitle">登录你的账号</p>
      <form class="auth-card__form" @submit.prevent="handleLogin">
        <AppInput v-model="username" placeholder="用户名" />
        <AppInput v-model="password" type="password" placeholder="密码" />
        <p v-if="error" class="auth-card__error">{{ error }}</p>
        <AppButton type="submit" :loading="loading" class="auth-card__submit">登录</AppButton>
      </form>
      <p class="auth-card__switch">还没有账号？<router-link to="/register">注册</router-link></p>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 400px; padding: $spacing-2xl; background: $color-bg-card; border-radius: $radius-xl; box-shadow: $shadow-md; border: 1px solid $color-border; }
.auth-card__title { font-family: $font-family; font-size: $font-size-2xl; text-align: center; color: $color-primary-dark; margin-bottom: $spacing-xs; }
.auth-card__subtitle { text-align: center; color: $color-text-secondary; margin-bottom: $spacing-xl; font-size: $font-size-sm; }
.auth-card__form { display: flex; flex-direction: column; gap: $spacing-md; }
.auth-card__error { font-size: $font-size-sm; color: $color-error; }
.auth-card__submit { width: 100%; margin-top: $spacing-sm; }
.auth-card__switch { margin-top: $spacing-lg; text-align: center; font-size: $font-size-sm; color: $color-text-secondary; }
</style>
```

- [ ] **Step 2: 创建 RegisterView.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'

const router = useRouter()
const auth = useAuthStore()
const username = ref(''); const password = ref(''); const confirmPassword = ref(''); const error = ref(''); const loading = ref(false)

async function handleRegister() {
  if (!username.value || !password.value) { error.value = '请填写用户名和密码'; return }
  if (username.value.length < 2 || username.value.length > 50) { error.value = '用户名长度需在 2-50 字符之间'; return }
  if (password.value.length < 6) { error.value = '密码长度不能少于 6 位'; return }
  if (password.value !== confirmPassword.value) { error.value = '两次密码输入不一致'; return }
  error.value = ''; loading.value = true
  try { await auth.register({ username: username.value, password: password.value }); router.push('/novels') }
  catch (e: unknown) { error.value = (e as Error).message || '注册失败' }
  finally { loading.value = false }
}
</script>
<template>
  <div class="auth-view">
    <div class="auth-card">
      <h1 class="auth-card__title">Novel Agent</h1>
      <p class="auth-card__subtitle">创建新账号</p>
      <form class="auth-card__form" @submit.prevent="handleRegister">
        <AppInput v-model="username" placeholder="用户名" />
        <AppInput v-model="password" type="password" placeholder="密码" />
        <AppInput v-model="confirmPassword" type="password" placeholder="确认密码" />
        <p v-if="error" class="auth-card__error">{{ error }}</p>
        <AppButton type="submit" :loading="loading" class="auth-card__submit">注册</AppButton>
      </form>
      <p class="auth-card__switch">已有账号？<router-link to="/login">登录</router-link></p>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 400px; padding: $spacing-2xl; background: $color-bg-card; border-radius: $radius-xl; box-shadow: $shadow-md; border: 1px solid $color-border; }
.auth-card__title { font-family: $font-family; font-size: $font-size-2xl; text-align: center; color: $color-primary-dark; margin-bottom: $spacing-xs; }
.auth-card__subtitle { text-align: center; color: $color-text-secondary; margin-bottom: $spacing-xl; font-size: $font-size-sm; }
.auth-card__form { display: flex; flex-direction: column; gap: $spacing-md; }
.auth-card__error { font-size: $font-size-sm; color: $color-error; }
.auth-card__submit { width: 100%; margin-top: $spacing-sm; }
.auth-card__switch { margin-top: $spacing-lg; text-align: center; font-size: $font-size-sm; color: $color-text-secondary; }
</style>
```

- [ ] **Step 3: TypeScript 验证** `npx vue-tsc --noEmit`
- [ ] **Step 4: Commit** `git add frontend/src/views/auth/ && git commit -m "feat: add login and register views"`

---

### Task 11: 创建小说页面

**Files:**
- Create: `frontend/src/views/novels/NovelListView.vue`
- Create: `frontend/src/views/novels/NovelDetailView.vue`

**Interfaces:**
- Consumes: `useNovelStore`, `AppLayout`, 通用组件
- Produces: 小说列表页、小说详情页

- [ ] **Step 1: 创建 NovelListView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'

const router = useRouter()
const novelStore = useNovelStore()
const showCreateModal = ref(false); const newTitle = ref(''); const newDescription = ref(''); const deleteTarget = ref<number | null>(null)

onMounted(async () => { await novelStore.loadNovels() })

async function handleCreate() {
  if (!newTitle.value) return
  await novelStore.createNovel({ title: newTitle.value, description: newDescription.value || null })
  showCreateModal.value = false; newTitle.value = ''; newDescription.value = ''
}
async function handleDelete() { if (deleteTarget.value !== null) { await novelStore.deleteNovel(deleteTarget.value); deleteTarget.value = null } }
function formatDate(d: string) { return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }) }
</script>
<template>
  <AppLayout>
    <div class="novel-list">
      <div class="novel-list__header"><h2 class="novel-list__title">我的小说</h2><AppButton size="sm" @click="showCreateModal = true">新建小说</AppButton></div>
      <div v-if="novelStore.novels.length === 0" class="novel-list__empty"><AppEmpty text="还没有小说，开始创作吧" /></div>
      <div v-else class="novel-list__grid">
        <AppCard v-for="novel in novelStore.novels" :key="novel.id" class="novel-card" @click="router.push(`/novels/${novel.id}`)">
          <div class="novel-card__header"><h3 class="novel-card__title">{{ novel.title }}</h3><button class="novel-card__delete" @click.stop="deleteTarget = novel.id">删除</button></div>
          <p v-if="novel.description" class="novel-card__desc">{{ novel.description }}</p>
          <p class="novel-card__date">{{ formatDate(novel.updated_at) }}</p>
        </AppCard>
      </div>
      <AppModal v-model:visible="showCreateModal" title="新建小说" confirm-text="创建" cancel-text="取消" @confirm="handleCreate" @cancel="showCreateModal = false">
        <AppInput v-model="newTitle" placeholder="小说标题" />
        <div style="height:12px" />
        <AppTextarea v-model="newDescription" placeholder="小说简介（可选）" :rows="3" />
      </AppModal>
      <AppConfirm v-model:visible="deleteTarget !== null" title="删除小说" content="确定要删除这部小说吗？此操作不可恢复。" confirm-text="删除" :confirm-variant="'danger'" @confirm="handleDelete" @cancel="deleteTarget = null" />
    </div>
  </AppLayout>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.novel-list { max-width: 900px; margin: 0 auto;
  &__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: $spacing-lg; }
  &__title { font-size: $font-size-xl; font-weight: 700; }
  &__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: $spacing-md; }
  &__empty { margin-top: $spacing-2xl; } }
.novel-card { cursor: pointer; transition: all $transition-fast;
  &:hover { box-shadow: $shadow-md; transform: translateY(-2px); }
  &__header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: $spacing-sm; }
  &__title { font-size: $font-size-md; font-weight: 600; }
  &__delete { font-size: $font-size-sm; color: $color-error; opacity: 0; transition: opacity $transition-fast; padding: 2px 6px; border-radius: $radius-sm; &:hover { background: rgba($color-error, 0.1); } }
  &:hover &__delete { opacity: 1; }
  &__desc { font-size: $font-size-sm; color: $color-text-secondary; margin-bottom: $spacing-sm; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  &__date { font-size: $font-size-xs; color: $color-text-placeholder; } }
</style>
```

- [ ] **Step 2: 创建 NovelDetailView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()
const novelId = computed(() => Number(route.params.id))
const chapters = computed(() => novelStore.currentNovel?.chapters || [])
const selectedChapterId = ref<number | null>(null)
const selectedChapter = computed(() => chapters.value.find((c) => c.id === selectedChapterId.value) || null)
const showChapterModal = ref(false); const newChapterTitle = ref(''); const deleteTarget = ref<number | null>(null)

onMounted(async () => { await novelStore.getNovel(novelId.value); if (chapters.value.length > 0) selectedChapterId.value = chapters.value[0].id })

async function handleCreateChapter() {
  if (!newChapterTitle.value) return
  await novelStore.createChapter(novelId.value, { title: newChapterTitle.value })
  showChapterModal.value = false; newChapterTitle.value = ''
  const chs = novelStore.currentNovel?.chapters || []; if (chs.length > 0) selectedChapterId.value = chs[chs.length - 1].id
}
async function handleDeleteChapter() {
  if (deleteTarget.value) { await novelStore.deleteChapter(novelId.value, deleteTarget.value); deleteTarget.value = null }
}
function goEdit() { if (selectedChapterId.value) router.push(`/novels/${novelId.value}/edit/${selectedChapterId.value}`) }
</script>
<template>
  <AppLayout>
    <div v-if="novelStore.currentNovel" class="novel-detail">
      <div class="novel-detail__sidebar">
        <div class="novel-detail__sidebar-header"><h3 class="novel-detail__novel-title">{{ novelStore.currentNovel.title }}</h3><AppButton size="sm" variant="secondary" @click="showChapterModal = true">+ 章节</AppButton></div>
        <div class="novel-detail__chapter-list">
          <button v-for="chapter in chapters" :key="chapter.id" class="novel-detail__chapter-item" :class="{ 'novel-detail__chapter-item--active': chapter.id === selectedChapterId }" @click="selectedChapterId = chapter.id">
            <span class="novel-detail__chapter-title">{{ chapter.title }}</span>
            <button class="novel-detail__chapter-delete" @click.stop="deleteTarget = chapter.id">删除</button>
          </button>
          <div v-if="chapters.length === 0"><AppEmpty text="暂无章节" /></div>
        </div>
      </div>
      <div class="novel-detail__content">
        <div v-if="selectedChapter" class="novel-detail__preview">
          <div class="novel-detail__preview-header"><h2 class="novel-detail__preview-title">{{ selectedChapter.title }}</h2><AppButton size="sm" @click="goEdit">编辑</AppButton></div>
          <AppCard class="novel-detail__preview-body"><p class="novel-detail__preview-text">{{ selectedChapter.content || '暂无内容' }}</p></AppCard>
        </div>
        <div v-else class="novel-detail__no-selection"><AppEmpty text="选择一个章节查看内容" /></div>
      </div>
    </div>
    <AppModal v-model:visible="showChapterModal" title="新建章节" confirm-text="创建" cancel-text="取消" @confirm="handleCreateChapter" @cancel="showChapterModal = false">
      <AppInput v-model="newChapterTitle" placeholder="章节标题" />
    </AppModal>
    <AppConfirm v-model:visible="deleteTarget !== null" title="删除章节" content="确定要删除这个章节吗？此操作不可恢复。" confirm-text="删除" :confirm-variant="'danger'" @confirm="handleDeleteChapter" @cancel="deleteTarget = null" />
  </AppLayout>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.novel-detail { display: flex; gap: $spacing-lg; height: calc(100vh - 56px - 48px);
  &__sidebar { width: 260px; display: flex; flex-direction: column; background: $color-bg-card; border-radius: $radius-lg; border: 1px solid $color-border; overflow: hidden; }
  &__sidebar-header { padding: $spacing-md; border-bottom: 1px solid $color-border; display: flex; align-items: center; justify-content: space-between; gap: $spacing-sm; }
  &__novel-title { font-size: $font-size-md; font-weight: 600; }
  &__chapter-list { flex: 1; overflow-y: auto; padding: $spacing-sm; }
  &__chapter-item { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: $spacing-sm; border-radius: $radius-md; text-align: left; color: $color-text; transition: all $transition-fast; font-size: $font-size-sm;
    &:hover { background: $color-bg-secondary; }
    &--active { background: $color-bg-secondary; color: $color-primary-dark; font-weight: 600; } }
  &__chapter-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  &__chapter-delete { font-size: $font-size-xs; color: $color-error; opacity: 0; padding: 2px 4px; border-radius: $radius-sm; &:hover { background: rgba($color-error, 0.1); } }
  &__chapter-item:hover &__chapter-delete { opacity: 1; }
  &__content { flex: 1; display: flex; flex-direction: column; }
  &__preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-md; }
  &__preview-title { font-size: $font-size-lg; font-weight: 700; }
  &__preview-text { white-space: pre-wrap; line-height: 1.8; }
  &__no-selection { display: flex; align-items: center; justify-content: center; height: 100%; } }
</style>
```

- [ ] **Step 3: TypeScript 验证** `npx vue-tsc --noEmit`
- [ ] **Step 4: Commit** `git add frontend/src/views/novels/ && git commit -m "feat: add novel list and detail views"`

---

### Task 12: 创建写作编辑器页

**Files:**
- Create: `frontend/src/views/editor/EditorView.vue`

**Interfaces:**
- Consumes: `useNovelStore`, `AppButton`, `AppInput`, `AppTextarea`
- Produces: 全屏沉浸式编辑器

- [ ] **Step 1: 创建 EditorView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import AppButton from '@/components/common/AppButton.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()

const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false)

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await novelStore.loadChapter(novelId.value, chapterId.value)
  if (novelStore.currentChapter) {
    title.value = novelStore.currentChapter.title
    content.value = novelStore.currentChapter.content
  }
})

async function handleSave() {
  saving.value = true
  try {
    await novelStore.updateChapter(novelId.value, chapterId.value, { title: title.value, content: content.value })
  } finally { saving.value = false }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
<template>
  <div class="editor">
    <header class="editor__header">
      <button class="editor__back" @click="router.push(`/novels/${novelId}`)">← 返回</button>
      <span class="editor__novel-name">{{ novelStore.currentNovel?.title || '' }}</span>
      <AppButton size="sm" :loading="saving" @click="handleSave">保存</AppButton>
    </header>
    <div class="editor__body">
      <AppInput v-model="title" placeholder="章节标题" size="lg" class="editor__title-input" />
      <AppTextarea v-model="content" placeholder="开始写作..." class="editor__content" :rows="1" />
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.editor { min-height: 100vh; display: flex; flex-direction: column; background: $color-bg-card;
  &__header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-md $spacing-lg; border-bottom: 1px solid $color-border; }
  &__back { font-size: $font-size-sm; color: $color-text-secondary; transition: color $transition-fast; &:hover { color: $color-primary-dark; } }
  &__novel-name { font-size: $font-size-sm; color: $color-text-secondary; }
  &__body { max-width: 800px; width: 100%; margin: 0 auto; padding: $spacing-xl $spacing-lg; flex: 1; display: flex; flex-direction: column; gap: $spacing-lg; }
  &__title-input { :deep(input) { font-size: $font-size-xl; font-weight: 700; border: none; padding: 0; &:focus { box-shadow: none; } } }
  &__content { flex: 1; :deep(textarea) { height: 100%; min-height: 60vh; border: none; padding: 0; font-size: $font-size-md; line-height: 2; resize: none; &:focus { box-shadow: none; } } } }
</style>
```

- [ ] **Step 2: TypeScript 验证** `npx vue-tsc --noEmit`
- [ ] **Step 3: Commit** `git add frontend/src/views/editor/ && git commit -m "feat: add writing editor view"`

---

### Task 13: 更新 App.vue 入口 + 全局样式导入

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: 全局样式文件
- Produces: 完整入口

- [ ] **Step 1: 重写 App.vue**

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
onMounted(() => { auth.restoreSession() })
</script>

<template>
  <router-view />
</template>

<style lang="scss">
@use '@/styles/reset';
@use '@/styles/global';
</style>
```

- [ ] **Step 2: 更新 main.ts (保持不变，仅确保正确)**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 3: TypeScript 验证**

```bash
npx vue-tsc --noEmit
```

Expected: 无错误。

- [ ] **Step 4: 启动验证**

```bash
npm run dev
```

Expected: Vite dev server 启动成功，`http://localhost:5173` 可访问，重定向到 `/login`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/main.ts
git commit -m "feat: update App.vue entry with global styles and auth restore"
```

---

## Spec Coverage Check

| Spec 要求 | Task |
|-----------|------|
| TypeScript 类型与 Pydantic 对齐 | Task 2 |
| API 层 (axios + interceptor) | Task 4 |
| Design Token (SCSS variables) | Task 3 |
| 通用组件库 (Button, Input, Textarea, Card) | Task 7 |
| 弹窗组件 (Modal, Confirm, Spinner, Empty, Toast) | Task 8 |
| 布局组件 (Layout, Header, Sidebar) | Task 9 |
| Vue Router + 守卫 | Task 6 |
| Pinia Stores (auth, novel) | Task 5 |
| 认证页面 (Login, Register) | Task 10 |
| 小说页面 (List, Detail) | Task 11 |
| 编辑器页面 | Task 12 |
| 入口文件整合 | Task 13 |
| 依赖安装 + Vite proxy | Task 1 |

无遗漏。
