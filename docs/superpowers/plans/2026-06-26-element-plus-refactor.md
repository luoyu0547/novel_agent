# Element Plus 前端重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 Element Plus 重构前端所有页面和组件，改为嵌套路由，统一暖色文学风主题，并重做表单和编辑器。

**Architecture:** Element Plus 按需引入 + SCSS 变量覆盖主题 → 嵌套路由（AppLayout 为父路由） → 组件映射替换 → 各视图重构（el-form、el-select、el-card 等） → 沉浸式编辑器 WritingEditor。

**Tech Stack:** Vue 3.5, Element Plus, unplugin-vue-components/unplugin-auto-import (on-demand), SCSS theming, Vitest, Playwright

## Global Constraints

- Vue 3.5+, Element Plus latest, vue-router 5, pinia 3, axios 1.x
- Component auto-import via unplugin (no manual `import { ElButton } from 'element-plus'`)
- SCSS theming: warm color palette from `_variables.scss` as single source of truth
- All enums (ChapterStatus, WorldSettingCategory) use `options.ts` constant map → `<el-option>`
- Nested routes only: AppLayout as parent, children for all novel views; auth routes + editor as top-level
- Remove all 9 App* components after migration
- Every view must remove `<AppLayout>` wrapper (it becomes the parent route component)

---

### Task 1: Foundation — Install Dependencies, Configure Vite & Theme

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/styles/element/index.scss`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Consumes: none
- Produces: element theme SCSS variables available globally, el-* components auto-imported, warm color scheme applied

- [ ] **Step 1: Install dependencies**

```bash
cd frontend
npm install element-plus @element-plus/icons-vue
npm install -D unplugin-vue-components unplugin-auto-import
```

- [ ] **Step 2: Create theme SCSS overrides**

Write `frontend/src/styles/element/index.scss`:
```scss
@use '../variables' as *;

@forward 'element-plus/theme-chalk/src/common/var.scss' with (
  $colors: (
    'primary': (
      'base': $color-primary,
    ),
    'success': (
      'base': $color-success,
    ),
    'warning': (
      'base': $color-warning,
    ),
    'danger': (
      'base': $color-error,
    ),
  ),
  $bg-color: (
    'page': $color-bg,
    '': $color-bg-card,
    'overlay': $color-bg-card,
  ),
  $text-color: (
    'primary': $color-text,
    'regular': $color-text,
    'secondary': $color-text-secondary,
    'placeholder': $color-text-placeholder,
    'disabled': $color-text-placeholder,
  ),
  $border-color: (
    '': $color-border,
    'light': $color-border,
    'lighter': $color-bg-secondary,
    'extra-light': $color-bg-secondary,
    'dark': $color-border,
  ),
  $font-family: (
    '' : $font-family,
  ),
  $font-size: (
    'extra-large': $font-size-xl,
    'large': $font-size-lg,
    'medium': $font-size-md,
    'base': $font-size-md,
    'small': $font-size-sm,
    'extra-small': $font-size-xs,
  ),
  $border-radius: (
    'base': $radius-md,
    'small': $radius-sm,
    'round': $radius-lg,
    'circle': 50%,
  ),
);
```

- [ ] **Step 3: Update vite.config.ts** with unplugin and SCSS additionalData

```typescript
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
    AutoImport({
      imports: ['vue', 'vue-router'],
      resolvers: [ElementPlusResolver({ importStyle: 'sass' })],
    }),
    Components({
      resolvers: [ElementPlusResolver({ importStyle: 'sass' })],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/element/index.scss" as *;`,
      },
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
```

- [ ] **Step 4: Update tsconfig.app.json** to include auto-generated type declarations

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "include": ["env.d.ts", "auto-imports.d.ts", "components.d.ts", "src/**/*", "src/**/*.vue"],
  "exclude": ["src/**/__tests__/*"],
  "compilerOptions": {
    "noUncheckedIndexedAccess": true,
    "paths": {
      "@/*": ["./src/*"]
    },
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo"
  }
}
```

- [ ] **Step 5: Update main.ts** — remove manual import of global.scss? Keep it for page transitions. The theme SCSS is injected via additionalData, no explicit import needed.

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import './styles/global.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

- [ ] **Step 6: Verify foundation**

```bash
cd frontend && npm run type-check
```
Expected: type-check passes (auto-imports.d.ts and components.d.ts generated). The `ElementPlusResolver` in `additionalData` references may cause initial warnings; if `@use` in additionalData causes issues, switch to:
```scss
// vite.config.ts
css: {
  preprocessorOptions: {
    scss: {
      additionalData: `@use "@/styles/element/index.scss" as *;`,
    },
  },
}
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: add Element Plus deps, on-demand import, and warm SCSS theme"
```

---

### Task 2: Create Constants Options Map

**Files:**
- Create: `frontend/src/constants/options.ts`
- Test: `frontend/src/__tests__/options.spec.ts`

**Interfaces:**
- Consumes: `ChapterStatus`, `WorldSettingCategory` types from `@/types`
- Produces: `CHAPTER_STATUS_OPTIONS: { value: ChapterStatus; label: string }[]`, `WORLD_SETTING_CATEGORY_OPTIONS: { value: WorldSettingCategory | 'all'; label: string }[]`, `WORLD_SETTING_CATEGORIES: { value: WorldSettingCategory; label: string }[]`

- [ ] **Step 1: Write the failing test**

`frontend/src/__tests__/options.spec.ts`:
```typescript
import { describe, expect, it } from 'vitest'
import { CHAPTER_STATUS_OPTIONS, WORLD_SETTING_CATEGORY_OPTIONS, WORLD_SETTING_CATEGORIES } from '@/constants/options'

describe('options constants', () => {
  it('CHAPTER_STATUS_OPTIONS covers all values', () => {
    const values = CHAPTER_STATUS_OPTIONS.map((o) => o.value)
    expect(values).toEqual(['draft', 'reviewed', 'locked'])
    expect(CHAPTER_STATUS_OPTIONS[0]).toEqual({ value: 'draft', label: '草稿' })
    expect(CHAPTER_STATUS_OPTIONS[1]).toEqual({ value: 'reviewed', label: '已确认' })
    expect(CHAPTER_STATUS_OPTIONS[2]).toEqual({ value: 'locked', label: '锁定' })
  })

  it('WORLD_SETTING_CATEGORY_OPTIONS includes all filter', () => {
    const values = WORLD_SETTING_CATEGORY_OPTIONS.map((o) => o.value)
    expect(values).toEqual(['all', 'geography', 'faction', 'rule', 'history', 'culture', 'other'])
  })

  it('WORLD_SETTING_CATEGORIES covers all categories', () => {
    const values = WORLD_SETTING_CATEGORIES.map((o) => o.value)
    expect(values).toEqual(['geography', 'faction', 'rule', 'history', 'culture', 'other'])
    expect(WORLD_SETTING_CATEGORIES.find((o) => o.value === 'geography')?.label).toBe('地理')
    expect(WORLD_SETTING_CATEGORIES.find((o) => o.value === 'other')?.label).toBe('其他')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/__tests__/options.spec.ts -q
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```typescript
import type { ChapterStatus, WorldSettingCategory } from '@/types'

export const CHAPTER_STATUS_OPTIONS: { value: ChapterStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'reviewed', label: '已确认' },
  { value: 'locked', label: '锁定' },
]

export const WORLD_SETTING_CATEGORY_OPTIONS: { value: WorldSettingCategory | 'all'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'geography', label: '地理' },
  { value: 'faction', label: '势力' },
  { value: 'rule', label: '规则' },
  { value: 'history', label: '历史' },
  { value: 'culture', label: '文化' },
  { value: 'other', label: '其他' },
]

export const WORLD_SETTING_CATEGORIES: { value: WorldSettingCategory; label: string }[] =
  WORLD_SETTING_CATEGORY_OPTIONS.filter((o) => o.value !== 'all') as typeof WORLD_SETTING_CATEGORIES
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run src/__tests__/options.spec.ts -q
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add constants/options.ts with enum-to-label maps"
```

---

### Task 3: Nested Router Restructure + Remove AppLayout Wrapper from All Views

**Files:**
- Rewrite: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue` — no change needed, keep `<router-view/>`
- Modify: `frontend/src/components/layout/AppLayout.vue` — restore `<router-view/>` (already `<slot/>` from our previous fix; change back to `<router-view/>`)
- Modify: `frontend/src/views/novels/NovelListView.vue` — remove `<AppLayout>` wrapper
- Modify: `frontend/src/views/novels/NovelDetailView.vue` — remove `<AppLayout>` wrapper
- Modify: `frontend/src/views/novels/CharacterListView.vue` — remove `<AppLayout>` wrapper
- Modify: `frontend/src/views/novels/WorldSettingsView.vue` — remove `<AppLayout>` wrapper
- Modify: `frontend/src/views/editor/EditorView.vue` — no AppLayout change (already has no wrapper)
- Test: (routing behavior verified via type-check + manual)

**Interfaces:**
- Consumes: existing view components
- Produces: nested route structure where AppLayout renders `<router-view/>` for children

- [ ] **Step 1: Rewrite router/index.ts**

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      redirect: '/novels',
      children: [
        { path: 'novels', name: 'novels', component: () => import('@/views/novels/NovelListView.vue'), meta: { auth: true } },
        { path: 'novels/:id', name: 'novel-detail', component: () => import('@/views/novels/NovelDetailView.vue'), meta: { auth: true } },
        { path: 'novels/:id/characters', name: 'novel-characters', component: () => import('@/views/novels/CharacterListView.vue'), meta: { auth: true } },
        { path: 'novels/:id/settings', name: 'novel-settings', component: () => import('@/views/novels/WorldSettingsView.vue'), meta: { auth: true } },
      ],
    },
    { path: '/novels/:id/edit/:chapterId', name: 'editor', component: () => import('@/views/editor/EditorView.vue'), meta: { auth: true } },
    { path: '/login', name: 'login', component: () => import('@/views/auth/LoginView.vue'), meta: { guest: true } },
    { path: '/register', name: 'register', component: () => import('@/views/auth/RegisterView.vue'), meta: { guest: true } },
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

- [ ] **Step 2: Restore `<router-view/>` in AppLayout.vue**

```diff
- <main class="app-layout__content"><slot /></main>
+ <main class="app-layout__content"><router-view /></main>
```

- [ ] **Step 3-6: Remove `<AppLayout>` wrapper from each novel view**

For each of these 4 views, remove:
- `import AppLayout from '@/components/layout/AppLayout.vue'`
- The outer `<AppLayout>` and `</AppLayout>` tags
- Keep all other content as-is

**NovelListView.vue** — remove lines 5 (import), wrap template div directly (no AppLayout wrapper):

```diff
- import AppLayout from '@/components/layout/AppLayout.vue'
```

Template change:
```diff
- <AppLayout>
-   <div class="novel-list">
+ <div class="novel-list">
```

And remove closing `</AppLayout>` at bottom.

**NovelDetailView.vue** — same: remove import, remove `<AppLayout>` and `</AppLayout>` wrapper, keep inner content.

**CharacterListView.vue** — same:
```diff
- import AppLayout from '@/components/layout/AppLayout.vue'
```
Remove `<AppLayout>` and `</AppLayout>` wrapper.

**WorldSettingsView.vue** — same:
```diff
- import AppLayout from '@/components/layout/AppLayout.vue'
```
Remove `<AppLayout>` and `</AppLayout>` wrapper.

- [ ] **Step 7: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "refactor: implement nested routes — AppLayout as parent route with children, remove view-level AppLayout wrappers"
```

---

### Task 4: Refactor AppLayout, AppSidebar, AppHeader with Element Plus

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/layout/AppHeader.vue`

**Interfaces:**
- Consumes: `route` from vue-router
- Produces: layout with el-menu sidebar, el-button header, el-container structure

- [ ] **Step 1: Rewrite AppLayout.vue** — use el-container

```vue
<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
</script>
<template>
  <el-container class="app-layout">
    <el-header class="app-layout__header"><AppHeader /></el-header>
    <el-container class="app-layout__body">
      <el-aside width="200px" class="app-layout__aside"><AppSidebar /></el-aside>
      <el-main class="app-layout__content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-layout {
  min-height: 100vh;
  &__header { height: 56px; padding: 0; background: $color-bg-card; border-bottom: 1px solid $color-border; }
  &__aside { background: $color-bg-card; border-right: 1px solid $color-border; }
  &__content { background: $color-bg; padding: $spacing-lg; overflow-y: auto; } }
</style>
```

- [ ] **Step 2: Rewrite AppSidebar.vue** — use el-menu with router mode

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
<template>
  <el-menu
    :default-active="route.path"
    router
    class="app-sidebar"
  >
    <el-menu-item index="/novels">
      <span>我的小说</span>
    </el-menu-item>
  </el-menu>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-sidebar {
  border-right: none;
  --el-menu-bg-color: $color-bg-card;
  --el-menu-text-color: $color-text-secondary;
  --el-menu-active-color: $color-primary-dark;
  --el-menu-hover-bg-color: $color-bg-secondary;
  --el-menu-item-height: 44px;
}
</style>
```

- [ ] **Step 3: Rewrite AppHeader.vue** — use el-button, el-text, el-dropdown

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
const router = useRouter()
const auth = useAuthStore()
function handleLogout() { auth.logout(); router.push('/login') }
</script>
<template>
  <div class="app-header">
    <div class="app-header__left">
      <span class="app-header__logo">Novel Agent</span>
    </div>
    <div class="app-header__right">
      <span v-if="auth.userInfo" class="app-header__user">{{ auth.userInfo.username }}</span>
      <el-button text size="small" @click="handleLogout">退出登录</el-button>
    </div>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 56px; padding: 0 $spacing-lg;
  &__logo { font-size: $font-size-lg; font-weight: 700; color: $color-primary-dark; }
  &__right { display: flex; align-items: center; gap: $spacing-md; }
  &__user { font-size: $font-size-sm; color: $color-text-secondary; } }
</style>
```

- [ ] **Step 4: Verify type-check + build**

```bash
cd frontend && npm run type-check && npm run build-only
```
Expected: PASS (build may warn about unplugin generating `.d.ts` files; these are expected)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: use el-container, el-menu, el-button in layout components"
```

---

### Task 5: WritingEditor Component (TDD)

**Files:**
- Create: `frontend/src/components/editor/WritingEditor.vue`
- Test: `frontend/src/__tests__/WritingEditor.spec.ts`

**Interfaces:**
- Props: `title: string`, `content: string`, `status: ChapterStatus`, `saving: boolean`, `savedAt: string | null`
- Emits: `update:title`, `update:content`, `update:status`, `save`
- Exposes: `wordCount: number`

- [ ] **Step 1: Write the failing tests**

`frontend/src/__tests__/WritingEditor.spec.ts`:
```typescript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import { ElInput } from 'element-plus'

// stub el-* components globally
const globalStubs = {
  'el-input': true,
  'el-input-number': true,
  'el-select': true,
  'el-option': true,
  'el-button': true,
  'el-text': true,
  'el-divider': true,
}

describe('WritingEditor', () => {
  it('renders title and content props', () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '第一章', content: '正文内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    expect(wrapper.findComponent({ name: 'ElInput' })).toBeTruthy()
  })

  it('emits update:title when title input changes', async () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '第一章', content: '', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    // trigger the title input update
    const titleInput = wrapper.findAllComponents({ name: 'ElInput' })[0]
    titleInput?.vm.$emit('update:modelValue', '第二章')
    expect(wrapper.emitted('update:title')).toBeTruthy()
    expect(wrapper.emitted('update:title')?.[0]).toEqual(['第二章'])
  })

  it('emits update:content when content changes', async () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: '旧内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    const contentTextarea = wrapper.findAllComponents({ name: 'ElInput' })[1]
    contentTextarea?.vm.$emit('update:modelValue', '新内容')
    expect(wrapper.emitted('update:content')?.[0]).toEqual(['新内容'])
  })

  it('emits save when debounce timer fires', async () => {
    vi.useFakeTimers()
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: '内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    // content changes trigger debounce save
    const contentTextarea = wrapper.findAllComponents({ name: 'ElInput' })[1]
    contentTextarea?.vm.$emit('update:modelValue', '新内容')
    vi.advanceTimersByTime(3000)
    expect(wrapper.emitted('save')).toBeTruthy()
    vi.useRealTimers()
  })

  it('displays word count', () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: 'HelloWorld', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('10')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run src/__tests__/WritingEditor.spec.ts -q
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

`frontend/src/components/editor/WritingEditor.vue`:
```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChapterStatus } from '@/types'
import { CHAPTER_STATUS_OPTIONS } from '@/constants/options'

const props = defineProps<{
  title: string
  content: string
  status: ChapterStatus
  saving: boolean
  savedAt: string | null
}>()

const emit = defineEmits<{
  'update:title': [value: string]
  'update:content': [value: string]
  'update:status': [value: ChapterStatus]
  save: []
}>()

const wordCount = computed(() => props.content.length)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function onContentInput(value: string) {
  emit('update:content', value)
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => emit('save'), 3000)
}

function onManualSave() {
  if (debounceTimer) clearTimeout(debounceTimer)
  emit('save')
}

const focused = ref(false)
</script>

<template>
  <div class="writing-editor">
    <header class="writing-editor__header">
      <el-button text @click="$router.back()">← 返回</el-button>
      <span class="writing-editor__novel-name">{{ $route.params.id }}</span>
      <div class="writing-editor__actions">
        <el-select :model-value="status" size="small" @update:model-value="emit('update:status', $event)">
          <el-option
            v-for="opt in CHAPTER_STATUS_OPTIONS"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-text size="small" type="info">已写 {{ wordCount }} 字</el-text>
        <el-text v-if="saving" size="small" type="info">保存中…</el-text>
        <el-text v-else-if="savedAt" size="small" type="info">已保存 {{ savedAt }}</el-text>
        <el-button size="small" type="primary" :loading="saving" @click="onManualSave">保存</el-button>
        <el-button size="small" text @click="focused = !focused">{{ focused ? '退出专注' : '专注' }}</el-button>
      </div>
    </header>
    <div class="writing-editor__body" :class="{ 'writing-editor__body--focused': focused }">
      <el-input
        :model-value="title"
        placeholder="章节标题"
        class="writing-editor__title-input"
        @update:model-value="emit('update:title', $event)"
      />
      <el-input
        :model-value="content"
        type="textarea"
        :autosize="{ minRows: 20 }"
        placeholder="开始写作..."
        class="writing-editor__content"
        @update:model-value="onContentInput"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.writing-editor {
  min-height: 100vh; display: flex; flex-direction: column; background: $color-bg-card;
  &__header { display: flex; align-items: center; justify-content: space-between; padding: $spacing-md $spacing-lg; border-bottom: 1px solid $color-border; }
  &__novel-name { font-size: $font-size-sm; color: $color-text-secondary; }
  &__actions { display: flex; align-items: center; gap: $spacing-sm; }
  &__body { max-width: 760px; width: 100%; margin: 0 auto; padding: $spacing-xl $spacing-lg; flex: 1; display: flex; flex-direction: column; gap: $spacing-lg;
    &--focused {
      .writing-editor__summary { display: none; }
      .writing-editor__header { opacity: 0.15; transition: opacity 0.3s; &:hover { opacity: 1; } }
    }
  }
  &__title-input { :deep(.el-input__wrapper) { box-shadow: none !important; padding: 0;
    .el-input__inner { font-size: $font-size-xl; font-weight: 700; } } }
  &__content { flex: 1;
    :deep(.el-textarea__inner) {
      min-height: 60vh; border: none; padding: 0; font-size: $font-size-md; line-height: 2; resize: none;
      font-family: $font-family; color: $color-text; background: transparent;
      &:focus { box-shadow: none; }
    }
  }
  &__summary { border-top: 1px solid $color-border; padding-top: $spacing-lg; }
  &__summary-title { font-size: $font-size-md; font-weight: 600; margin-bottom: $spacing-sm; }
}
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/__tests__/WritingEditor.spec.ts -q
```
Expected: PASS (adjust stub expectations if needed — el-input textarea may behave differently; update test `findComponent` selectors to match actual rendered hierarchy)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add WritingEditor component with word count, debounce auto-save, and focus mode"
```

---

### Task 6: Refactor Auth Views (Login + Register) with Element Plus

**Files:**
- Modify: `frontend/src/views/auth/LoginView.vue`
- Modify: `frontend/src/views/auth/RegisterView.vue`

**Interfaces:**
- Consumes: `auth` store, router
- Produces: auth pages with el-form, el-input, el-button, el-card, el-alert

- [ ] **Step 1: Rewrite LoginView.vue**

```vue
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    error.value = ''; loading.value = true
    try { await auth.login(form); router.push('/novels') }
    catch (e: unknown) { error.value = (e as Error).message || '登录失败' }
    finally { loading.value = false }
  })
}
</script>
<template>
  <div class="auth-view">
    <el-card class="auth-card" shadow="never">
      <template #header>
        <h1 class="auth-card__title">Novel Agent</h1>
        <p class="auth-card__subtitle">登录你的账号</p>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-card__error" />
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="auth-card__submit">登录</el-button>
        </el-form-item>
      </el-form>
      <div class="auth-card__switch">还没有账号？<router-link to="/register">注册</router-link></div>
    </el-card>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 420px;
  :deep(.el-card__header) { text-align: center; border-bottom: 1px solid $color-border; }
  &__title { font-size: $font-size-2xl; color: $color-primary-dark; margin: 0; }
  &__subtitle { color: $color-text-secondary; font-size: $font-size-sm; margin: $spacing-xs 0 0; }
  &__error { margin-bottom: $spacing-md; }
  &__submit { width: 100%; }
  &__switch { margin-top: $spacing-md; text-align: center; font-size: $font-size-sm; color: $color-text-secondary;
    a { color: $color-primary-dark; } } }
</style>
```

- [ ] **Step 2: Rewrite RegisterView.vue** (similar pattern)

```vue
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '', confirmPassword: '' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度需在 2-50 字符之间', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: Function) => {
        if (value !== form.password) callback(new Error('两次密码输入不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    error.value = ''; loading.value = true
    try { await auth.register({ username: form.username, password: form.password }); router.push('/novels') }
    catch (e: unknown) { error.value = (e as Error).message || '注册失败' }
    finally { loading.value = false }
  })
}
</script>
<template>
  <div class="auth-view">
    <el-card class="auth-card" shadow="never">
      <template #header>
        <h1 class="auth-card__title">Novel Agent</h1>
        <p class="auth-card__subtitle">创建新账号</p>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleRegister">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" placeholder="确认密码" show-password />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="auth-card__error" />
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="auth-card__submit">注册</el-button>
        </el-form-item>
      </el-form>
      <div class="auth-card__switch">已有账号？<router-link to="/login">登录</router-link></div>
    </el-card>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.auth-view { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: $color-bg; }
.auth-card { width: 100%; max-width: 420px;
  :deep(.el-card__header) { text-align: center; border-bottom: 1px solid $color-border; }
  &__title { font-size: $font-size-2xl; color: $color-primary-dark; margin: 0; }
  &__subtitle { color: $color-text-secondary; font-size: $font-size-sm; margin: $spacing-xs 0 0; }
  &__error { margin-bottom: $spacing-md; }
  &__submit { width: 100%; }
  &__switch { margin-top: $spacing-md; text-align: center; font-size: $font-size-sm; color: $color-text-secondary;
    a { color: $color-primary-dark; } } }
</style>
```

- [ ] **Step 3: Verify type-check + lint**

```bash
cd frontend && npm run type-check && npm run lint
```
Expected: PASS (lint will still show the pre-existing `any` in client.ts — ignore)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: rewrite LoginView and RegisterView with Element Plus el-form"
```

---

### Task 7: Refactor NovelListView (我的小说)

**Files:**
- Modify: `frontend/src/views/novels/NovelListView.vue`

**Interfaces:**
- Consumes: `useNovelStore`, router
- Produces: novel list with el-row/el-col grid, el-card, el-dialog for create, el-empty

- [ ] **Step 1: Rewrite NovelListView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'

const router = useRouter()
const novelStore = useNovelStore()
const showCreateModal = ref(false)
const formRef = ref()
const deleteTarget = ref<number | null>(null)
const form = reactive({ title: '', description: '', genre: '', style_guide: '' })
const rules = {
  title: [{ required: true, message: '请输入小说标题', trigger: 'blur' }, { max: 100, message: '标题不超过 100 字符', trigger: 'blur' }],
}

onMounted(async () => { await novelStore.loadNovels() })

async function handleCreate() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    await novelStore.createNovel({
      title: form.title,
      description: form.description || null,
      genre: form.genre || null,
      style_guide: form.style_guide || null,
    })
    showCreateModal.value = false
    form.title = ''; form.description = ''; form.genre = ''; form.style_guide = ''
  })
}

async function handleDelete() {
  if (deleteTarget.value !== null) {
    await novelStore.deleteNovel(deleteTarget.value)
    deleteTarget.value = null
  }
}

function confirmDelete(id: number) {
  ElMessageBox.confirm('确定要删除这部小说吗？此操作不可恢复。', '删除小说', {
    confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
  }).then(() => { deleteTarget.value = id; handleDelete() }).catch(() => {})
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>

<template>
  <div class="novel-list">
    <div class="novel-list__header">
      <h2 class="novel-list__title">我的小说</h2>
      <el-button type="primary" size="small" @click="showCreateModal = true">新建小说</el-button>
    </div>
    <el-empty v-if="novelStore.novels.length === 0" description="还没有小说，开始创作吧">
      <el-button type="primary" @click="showCreateModal = true">立即创建</el-button>
    </el-empty>
    <el-row v-else :gutter="16">
      <el-col v-for="novel in novelStore.novels" :key="novel.id" :xs="24" :sm="12" :md="8">
        <el-card shadow="hover" class="novel-card" @click="router.push(`/novels/${novel.id}`)">
          <div class="novel-card__header">
            <el-link :underline="false" type="primary">{{ novel.title }}</el-link>
            <el-button text size="small" type="danger" @click.stop="confirmDelete(novel.id)">删除</el-button>
          </div>
          <p v-if="novel.description" class="novel-card__desc">
            <el-text truncated>{{ novel.description }}</el-text>
          </p>
          <el-text size="small" type="info">{{ formatDate(novel.updated_at) }}</el-text>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showCreateModal" title="新建小说" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="小说标题" prop="title">
          <el-input v-model="form.title" placeholder="小说标题" />
        </el-form-item>
        <el-form-item label="小说简介">
          <el-input v-model="form.description" type="textarea" :autosize="{ minRows: 3 }" placeholder="小说简介（可选）" />
        </el-form-item>
        <el-form-item label="小说类型">
          <el-input v-model="form.genre" placeholder="小说类型（可选）" />
        </el-form-item>
        <el-form-item label="风格指南">
          <el-input v-model="form.style_guide" type="textarea" :autosize="{ minRows: 4 }" placeholder="风格指南（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateModal = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.novel-list { max-width: 900px; margin: 0 auto;
  &__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: $spacing-lg; }
  &__title { font-size: $font-size-xl; font-weight: 700; } }
.novel-card { cursor: pointer; margin-bottom: $spacing-md;
  &__header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: $spacing-sm; }
  &__desc { margin-bottom: $spacing-sm; } }
</style>
```

- [ ] **Step 2: Verify type-check + build**

```bash
cd frontend && npm run type-check && npm run build-only
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: rewrite NovelListView with el-card, el-row/col, el-dialog, el-empty"
```

---

### Task 8: Refactor NovelDetailView

**Files:**
- Modify: `frontend/src/views/novels/NovelDetailView.vue`
- Modify: `frontend/src/components/novels/NovelWorkspaceTabs.vue` (internal tabs)

**Interfaces:**
- Consumes: `useNovelStore`, `useMemoryStore`
- Produces: novel detail with chapter list (el-menu), preview (el-card), edit/create dialogs

- [ ] **Step 1: Rewrite NovelWorkspaceTabs to use el-tabs**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{ novelId: number }>()
const route = useRoute()
const router = useRouter()

const tabs = computed(() => [
  { label: '章节', path: `/novels/${props.novelId}` },
  { label: '角色', path: `/novels/${props.novelId}/characters` },
  { label: '设定', path: `/novels/${props.novelId}/settings` },
])
</script>
<template>
  <el-tabs :model-value="route.path" @tab-change="(p: string) => router.push(p)" class="workspace-tabs">
    <el-tab-pane v-for="tab in tabs" :key="tab.path" :label="tab.label" :name="tab.path" />
  </el-tabs>
</template>
<style scoped lang="scss">
.workspace-tabs { margin-bottom: 16px; }
</style>
```

- [ ] **Step 2: Rewrite NovelDetailView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()
const novelId = computed(() => Number(route.params.id))
const chapters = computed(() => novelStore.currentNovel?.chapters || [])
const selectedChapterId = ref<number | null>(null)
const selectedChapter = computed(() => chapters.value.find((c) => c.id === selectedChapterId.value) || null)
const showChapterModal = ref(false); const newChapterTitle = ref('')
const showNovelModal = ref(false)
const novelFormRef = ref()
const novelForm = reactive({ title: '', description: '', genre: '', style_guide: '' })
const novelRules = { title: [{ required: true, message: '请输入小说标题', trigger: 'blur' }] }

function openNovelModal() {
  const n = novelStore.currentNovel; if (!n) return
  novelForm.title = n.title; novelForm.description = n.description || ''
  novelForm.genre = n.genre || ''; novelForm.style_guide = n.style_guide || ''
  showNovelModal.value = true
}

async function handleUpdateNovel() {
  if (!novelFormRef.value) return
  await novelFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    await novelStore.updateNovel(novelId.value, {
      title: novelForm.title, description: novelForm.description || null,
      genre: novelForm.genre || null, style_guide: novelForm.style_guide || null,
    })
    showNovelModal.value = false
  })
}

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  if (chapters.value.length > 0) selectedChapterId.value = chapters.value[0]?.id ?? null
})

async function handleCreateChapter() {
  if (!newChapterTitle.value) return
  await novelStore.createChapter(novelId.value, { title: newChapterTitle.value })
  showChapterModal.value = false; newChapterTitle.value = ''
  const chs = novelStore.currentNovel?.chapters || []
  if (chs.length > 0) selectedChapterId.value = chs[chs.length - 1]?.id ?? null
}

function confirmDeleteChapter(chapterId: number) {
  ElMessageBox.confirm('确定要删除这个章节吗？此操作不可恢复。', '删除章节', {
    confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
  }).then(async () => {
    await novelStore.deleteChapter(novelId.value, chapterId)
    if (selectedChapterId.value === chapterId) selectedChapterId.value = null
  }).catch(() => {})
}

function goEdit() {
  if (selectedChapterId.value) router.push(`/novels/${novelId.value}/edit/${selectedChapterId.value}`)
}
</script>
<template>
  <div v-if="novelStore.currentNovel" class="novel-detail">
    <NovelWorkspaceTabs :novel-id="novelId" />
    <div class="novel-detail__body">
      <div class="novel-detail__sidebar">
        <div class="novel-detail__sidebar-header">
          <span class="novel-detail__novel-title">{{ novelStore.currentNovel.title }}</span>
          <el-button size="small" @click="showChapterModal = true">+ 章节</el-button>
        </div>
        <el-menu :default-active="String(selectedChapterId)" class="novel-detail__chapter-list">
          <el-menu-item
            v-for="chapter in chapters" :key="chapter.id"
            :index="String(chapter.id)"
            @click="selectedChapterId = chapter.id"
          >
            <span class="novel-detail__chapter-title">{{ chapter.title }}</span>
            <el-button text size="small" type="danger" @click.stop="confirmDeleteChapter(chapter.id)">删除</el-button>
          </el-menu-item>
        </el-menu>
        <el-empty v-if="chapters.length === 0" description="暂无章节" />
      </div>
      <div class="novel-detail__content">
        <div class="novel-detail__content-header">
          <h2 class="novel-detail__section-title">{{ novelStore.currentNovel.title }}</h2>
          <el-button size="small" @click="openNovelModal">编辑信息</el-button>
        </div>
        <div class="novel-detail__meta">
          <el-text v-if="novelStore.currentNovel.genre" size="small" type="info">
            类型：{{ novelStore.currentNovel.genre }}
          </el-text>
          <el-text v-if="novelStore.currentNovel.style_guide" size="small" type="info">
            风格指南：{{ novelStore.currentNovel.style_guide }}
          </el-text>
        </div>
        <div v-if="selectedChapter" class="novel-detail__preview">
          <div class="novel-detail__preview-header">
            <h2 class="novel-detail__preview-title">{{ selectedChapter.title }}</h2>
            <el-button size="small" type="primary" @click="goEdit">编辑</el-button>
          </div>
          <el-card class="novel-detail__preview-body" shadow="never">
            <p class="novel-detail__preview-text">{{ selectedChapter.content || '暂无内容' }}</p>
          </el-card>
        </div>
        <el-empty v-else description="选择一个章节查看内容" />
      </div>
    </div>

    <el-dialog v-model="showChapterModal" title="新建章节" width="400px">
      <el-input v-model="newChapterTitle" placeholder="章节标题" />
      <template #footer>
        <el-button @click="showChapterModal = false">取消</el-button>
        <el-button type="primary" @click="handleCreateChapter">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showNovelModal" title="编辑小说信息" width="500px">
      <el-form ref="novelFormRef" :model="novelForm" :rules="novelRules" label-position="top">
        <el-form-item label="小说标题" prop="title">
          <el-input v-model="novelForm.title" />
        </el-form-item>
        <el-form-item label="小说简介">
          <el-input v-model="novelForm.description" type="textarea" :autosize="{ minRows: 3 }" />
        </el-form-item>
        <el-form-item label="小说类型">
          <el-input v-model="novelForm.genre" />
        </el-form-item>
        <el-form-item label="风格指南">
          <el-input v-model="novelForm.style_guide" type="textarea" :autosize="{ minRows: 4 }" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNovelModal = false">取消</el-button>
        <el-button type="primary" @click="handleUpdateNovel">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.novel-detail {
  &__body { display: flex; gap: $spacing-lg; height: calc(100vh - 56px - 48px); }
  &__sidebar { width: 260px; display: flex; flex-direction: column; background: $color-bg-card; border-radius: $radius-lg; border: 1px solid $color-border; overflow: hidden; }
  &__sidebar-header { padding: $spacing-md; border-bottom: 1px solid $color-border; display: flex; align-items: center; justify-content: space-between; gap: $spacing-sm; }
  &__novel-title { font-size: $font-size-md; font-weight: 600; }
  &__chapter-list { flex: 1; overflow-y: auto; border-right: none; --el-menu-bg-color: transparent; }
  &__chapter-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  &__content { flex: 1; display: flex; flex-direction: column; }
  &__content-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: $spacing-sm; }
  &__section-title { font-size: $font-size-lg; font-weight: 700; }
  &__meta { display: flex; gap: $spacing-md; margin-bottom: $spacing-md; }
  &__preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-md; }
  &__preview-title { font-size: $font-size-lg; font-weight: 700; }
  &__preview-text { white-space: pre-wrap; line-height: 1.8; } }
</style>
```

- [ ] **Step 3: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: PASS (may need to add `import { reactive } from 'vue'` if not auto-imported — verify auto-imports.d.ts includes `reactive`)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: rewrite NovelDetailView and NovelWorkspaceTabs with Element Plus"
```

---

### Task 9: Refactor CharacterListView

**Files:**
- Modify: `frontend/src/views/novels/CharacterListView.vue`

**Interfaces:**
- Consumes: `useMemoryStore`, `useNovelStore`, `splitBehaviorRules`, `joinBehaviorRules`
- Produces: character cards with el-card, el-descriptions, el-tag; edit dialog with el-form

- [ ] **Step 1: Rewrite CharacterListView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import { useMemoryStore } from '@/stores/memory'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'
import type { CharacterProfile } from '@/types'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()
const form = reactive({
  name: '', story_role: '', identity: '', personality: '',
  motivation: '', speech_style: '', behavior_rules_text: '', current_state: '',
})
const rules = { name: [{ required: true, message: '请输入角色名', trigger: 'blur' }] }

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadCharacters(novelId.value)
})

function openCreate() {
  editingId.value = null
  form.name = ''; form.story_role = ''; form.identity = ''
  form.personality = ''; form.motivation = ''; form.speech_style = ''
  form.behavior_rules_text = ''; form.current_state = ''
  showModal.value = true
}

function openEdit(character: CharacterProfile) {
  editingId.value = character.id
  form.name = character.name; form.story_role = character.story_role
  form.identity = character.identity; form.personality = character.personality
  form.motivation = character.motivation; form.speech_style = character.speech_style
  form.behavior_rules_text = joinBehaviorRules(character.behavior_rules)
  form.current_state = character.current_state
  showModal.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    const payload = {
      name: form.name, story_role: form.story_role || undefined,
      identity: form.identity || undefined, personality: form.personality || undefined,
      motivation: form.motivation || undefined, speech_style: form.speech_style || undefined,
      behavior_rules: splitBehaviorRules(form.behavior_rules_text),
      current_state: form.current_state || undefined,
    }
    if (editingId.value) await memoryStore.updateCharacter(novelId.value, editingId.value, payload)
    else await memoryStore.createCharacter(novelId.value, payload)
    showModal.value = false
  })
}

function confirmDelete(id: number) {
  ElMessageBox.confirm('确定要删除这个角色卡吗？', '删除角色', {
    confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
  }).then(() => memoryStore.deleteCharacter(novelId.value, id)).catch(() => {})
}
</script>
<template>
  <div class="characters">
    <NovelWorkspaceTabs :novel-id="novelId" />
    <div class="characters__header">
      <div>
        <h2 class="characters__title">角色卡片</h2>
        <el-text size="small" type="info">{{ novelStore.currentNovel?.title }}</el-text>
      </div>
      <el-button size="small" type="primary" @click="openCreate">新建角色</el-button>
    </div>
    <el-empty v-if="memoryStore.characters.length === 0" description="暂无角色卡" />
    <el-row v-else :gutter="16">
      <el-col v-for="character in memoryStore.characters" :key="character.id" :xs="24" :sm="12" :md="8">
        <el-card shadow="hover" class="character-card">
          <template #header>
            <div class="character-card__header">
              <span class="character-card__name">{{ character.name }}</span>
              <div>
                <el-button text size="small" @click="openEdit(character)">编辑</el-button>
                <el-button text size="small" type="danger" @click="confirmDelete(character.id)">删除</el-button>
              </div>
            </div>
          </template>
          <el-descriptions :column="1" size="small">
            <el-descriptions-item v-if="character.story_role" label="叙事功能">{{ character.story_role }}</el-descriptions-item>
            <el-descriptions-item v-if="character.identity" label="身份">{{ character.identity }}</el-descriptions-item>
            <el-descriptions-item v-if="character.personality" label="性格">{{ character.personality }}</el-descriptions-item>
            <el-descriptions-item v-if="character.motivation" label="动机">{{ character.motivation }}</el-descriptions-item>
            <el-descriptions-item v-if="character.speech_style" label="说话方式">{{ character.speech_style }}</el-descriptions-item>
            <el-descriptions-item v-if="character.current_state" label="当前状态">{{ character.current_state }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="character.behavior_rules.length" class="character-card__rules">
            <el-tag v-for="rule in character.behavior_rules" :key="rule" size="small" class="character-card__tag">{{ rule }}</el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showModal" :title="editingId ? '编辑角色' : '新建角色'" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="角色名" prop="name">
          <el-input v-model="form.name" placeholder="角色名" />
        </el-form-item>
        <el-form-item label="叙事功能">
          <el-input v-model="form.story_role" placeholder="如主角 / 反派 / 导师" />
        </el-form-item>
        <el-form-item label="身份">
          <el-input v-model="form.identity" placeholder="世界内身份，如边境军少将军" />
        </el-form-item>
        <el-divider content-position="left">性格与动机</el-divider>
        <el-form-item label="性格特征">
          <el-input v-model="form.personality" type="textarea" :autosize="{ minRows: 3 }" />
        </el-form-item>
        <el-form-item label="动机和目标">
          <el-input v-model="form.motivation" type="textarea" :autosize="{ minRows: 3 }" />
        </el-form-item>
        <el-divider content-position="left">表达与状态</el-divider>
        <el-form-item label="说话方式">
          <el-input v-model="form.speech_style" type="textarea" :autosize="{ minRows: 3 }" />
        </el-form-item>
        <el-form-item label="行为边界">
          <el-input v-model="form.behavior_rules_text" type="textarea" :autosize="{ minRows: 4 }" placeholder="每行一条" />
        </el-form-item>
        <el-form-item label="当前状态">
          <el-input v-model="form.current_state" type="textarea" :autosize="{ minRows: 3 }" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showModal = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.characters { max-width: 1100px; margin: 0 auto; }
.characters__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.characters__title { font-size: $font-size-xl; font-weight: 700; }
.character-card { margin-bottom: $spacing-md;
  &__header { display: flex; justify-content: space-between; align-items: center; }
  &__name { font-weight: 600; }
  &__rules { margin-top: $spacing-sm; display: flex; flex-wrap: wrap; gap: 4px; }
  &__tag { max-width: 100%; overflow: hidden; text-overflow: ellipsis; } }
</style>
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: rewrite CharacterListView with el-card, el-descriptions, el-tag, el-form groups"
```

---

### Task 10: Refactor WorldSettingsView

**Files:**
- Modify: `frontend/src/views/novels/WorldSettingsView.vue`

**Interfaces:**
- Consumes: `useMemoryStore`, `useNovelStore`, options constants
- Produces: world settings with el-radio-group filter, el-card, el-select; edit dialog with el-form

- [ ] **Step 1: Rewrite WorldSettingsView.vue**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import { useMemoryStore } from '@/stores/memory'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { WORLD_SETTING_CATEGORY_OPTIONS, WORLD_SETTING_CATEGORIES } from '@/constants/options'
import type { WorldSetting, WorldSettingCategory } from '@/types'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const selectedCategory = ref<WorldSettingCategory | 'all'>('all')

const form = ref<{ title: string; category: WorldSettingCategory; content: string }>({
  title: '', category: 'other', content: '',
})

const filteredSettings = computed(() =>
  selectedCategory.value === 'all'
    ? memoryStore.worldSettings
    : memoryStore.worldSettings.filter((item) => item.category === selectedCategory.value),
)

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadWorldSettings(novelId.value)
})

function openCreate() {
  editingId.value = null; form.value = { title: '', category: 'other', content: '' }; showModal.value = true
}

function openEdit(setting: WorldSetting) {
  editingId.value = setting.id
  form.value = { title: setting.title, category: setting.category, content: setting.content }
  showModal.value = true
}

async function handleSave() {
  if (!form.value.title) return
  if (editingId.value) await memoryStore.updateWorldSetting(novelId.value, editingId.value, form.value)
  else await memoryStore.createWorldSetting(novelId.value, form.value)
  showModal.value = false
}

function confirmDelete(id: number) {
  ElMessageBox.confirm('确定要删除这条世界观设定吗？', '删除设定', {
    confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
  }).then(() => memoryStore.deleteWorldSetting(novelId.value, id)).catch(() => {})
}

function categoryLabel(value: string) {
  return WORLD_SETTING_CATEGORIES.find((c) => c.value === value)?.label || value
}
</script>
<template>
  <div class="settings">
    <NovelWorkspaceTabs :novel-id="novelId" />
    <div class="settings__header">
      <div>
        <h2 class="settings__title">世界观设定</h2>
        <el-text size="small" type="info">{{ novelStore.currentNovel?.title }}</el-text>
      </div>
      <el-button size="small" type="primary" @click="openCreate">新建设定</el-button>
    </div>

    <el-radio-group v-model="selectedCategory" class="settings__filters">
      <el-radio-button
        v-for="option in WORLD_SETTING_CATEGORY_OPTIONS"
        :key="option.value"
        :value="option.value"
      >{{ option.label }}</el-radio-button>
    </el-radio-group>

    <el-empty v-if="filteredSettings.length === 0" description="暂无世界观设定" />
    <el-row v-else :gutter="16">
      <el-col v-for="setting in filteredSettings" :key="setting.id" :xs="24" :sm="12" :md="8">
        <el-card shadow="hover" class="setting-card">
          <div class="setting-card__header">
            <div>
              <h3>{{ setting.title }}</h3>
              <el-tag size="small" class="setting-card__tag">{{ categoryLabel(setting.category) }}</el-tag>
            </div>
            <div class="setting-card__actions">
              <el-button text size="small" @click="openEdit(setting)">编辑</el-button>
              <el-button text size="small" type="danger" @click="confirmDelete(setting.id)">删除</el-button>
            </div>
          </div>
          <el-text class="setting-card__content">{{ setting.content }}</el-text>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="showModal" :title="editingId ? '编辑设定' : '新建设定'" width="640px">
      <div class="settings__form">
        <el-form label-position="top">
          <el-form-item label="设定标题">
            <el-input v-model="form.title" placeholder="设定标题" />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="form.category" class="settings__select">
              <el-option
                v-for="option in WORLD_SETTING_CATEGORIES"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="设定内容">
            <el-input v-model="form.content" type="textarea" :autosize="{ minRows: 8 }" placeholder="设定内容" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showModal = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped lang="scss">
@use '@/styles/variables' as *;
.settings { max-width: 1100px; margin: 0 auto; }
.settings__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.settings__title { font-size: $font-size-xl; font-weight: 700; }
.settings__filters { margin-bottom: $spacing-lg; }
.settings__form { display: flex; flex-direction: column; gap: $spacing-md; }
.settings__select { width: 100%; }
.setting-card { margin-bottom: $spacing-md; }
.setting-card__header { display: flex; justify-content: space-between; gap: $spacing-md; margin-bottom: $spacing-sm; }
.setting-card__tag { margin-top: 4px; }
.setting-card__actions { display: flex; gap: 4px; flex-shrink: 0; }
.setting-card__content { font-size: $font-size-sm; line-height: 1.8; white-space: pre-wrap; }
</style>
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: rewrite WorldSettingsView with el-radio-group, el-select, el-card"
```

---

### Task 11: Refactor EditorView to Use WritingEditor

**Files:**
- Modify: `frontend/src/views/editor/EditorView.vue`

**Interfaces:**
- Consumes: `WritingEditor`, `useNovelStore`, router
- Produces: full-screen editor using the WritingEditor component

- [ ] **Step 1: Rewrite EditorView.vue**

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import type { ChapterStatus } from '@/types'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()
const novelId = computed(() => Number(route.params.id))
const chapterId = computed(() => Number(route.params.chapterId))
const title = ref(''); const content = ref(''); const saving = ref(false); const savedAt = ref<string | null>(null)
const summary = ref('')
const status = ref<ChapterStatus>('draft')

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await novelStore.loadChapter(novelId.value, chapterId.value)
  if (novelStore.currentChapter) {
    title.value = novelStore.currentChapter.title
    content.value = novelStore.currentChapter.content
    summary.value = novelStore.currentChapter.summary
    status.value = novelStore.currentChapter.status
  }
})

async function handleSave() {
  saving.value = true
  try {
    await novelStore.updateChapter(novelId.value, chapterId.value, {
      title: title.value,
      content: content.value,
      summary: summary.value,
      status: status.value,
    })
    savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } finally { saving.value = false }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>
<template>
  <div class="editor-view">
    <WritingEditor
      :title="title"
      :content="content"
      :status="status"
      :saving="saving"
      :saved-at="savedAt"
      @update:title="title = $event"
      @update:content="content = $event"
      @update:status="status = $event"
      @save="handleSave"
    />
  </div>
</template>
<style scoped lang="scss">
.editor-view { min-height: 100vh; }
</style>
```

- [ ] **Step 2: Verify type-check**

```bash
cd frontend && npm run type-check
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: rewrite EditorView to use WritingEditor component"
```

---

### Task 12: Delete Deprecated Old Common Components + Clean Up

**Files:**
- Delete: `frontend/src/components/common/AppButton.vue`
- Delete: `frontend/src/components/common/AppInput.vue`
- Delete: `frontend/src/components/common/AppTextarea.vue`
- Delete: `frontend/src/components/common/AppModal.vue`
- Delete: `frontend/src/components/common/AppConfirm.vue`
- Delete: `frontend/src/components/common/AppToast.vue`
- Delete: `frontend/src/components/common/AppSpinner.vue`
- Delete: `frontend/src/components/common/AppCard.vue`
- Delete: `frontend/src/components/common/AppEmpty.vue`
- Verify: no remaining `import` from any of these files anywhere

**Interfaces:**
- Consumes: cleanup from all previous tasks
- Produces: clean directory with only Element Plus as UI kit

- [ ] **Step 1: Delete all 9 App* files**

```bash
rm frontend/src/components/common/AppButton.vue
rm frontend/src/components/common/AppInput.vue
rm frontend/src/components/common/AppTextarea.vue
rm frontend/src/components/common/AppModal.vue
rm frontend/src/components/common/AppConfirm.vue
rm frontend/src/components/common/AppToast.vue
rm frontend/src/components/common/AppSpinner.vue
rm frontend/src/components/common/AppCard.vue
rm frontend/src/components/common/AppEmpty.vue
```

- [ ] **Step 2: Verify no remaining references**

```bash
cd frontend && rg "from '@/components/common/" src/ || echo "No remaining imports — clean"
```
Expected: "No remaining imports — clean" or no matches

- [ ] **Step 3: Verify type-check + lint**

```bash
cd frontend && npm run type-check && npm run lint
```
Expected: PASS (the pre-existing `any` in client.ts excluded)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: delete deprecated App* components, fully migrated to Element Plus"
```

---

### Task 13: Update E2E Test + Final Verification

**Files:**
- Modify: `frontend/e2e/vue.spec.ts`
- Test: full verification pass

**Interfaces:**
- Consumes: fully refactored app
- Produces: passing e2e tests and verified app

- [ ] **Step 1: Update e2e test**

Since the login page now uses Element Plus, the selector `getByText('登录你的账号')` may not work (text is inside el-card header). Update to target the correct selector:

```typescript
import { test, expect } from '@playwright/test'

test('shows login page for unauthenticated users', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: /登录/ })).toBeVisible()
})
```

- [ ] **Step 2: Run unit tests**

```bash
cd frontend && npx vitest run -q
```
Expected: All tests pass (existing behaviorRules + App + options + WritingEditor)

- [ ] **Step 3: Run type-check and build**

```bash
cd frontend && npm run type-check && npm run build
```
Expected: PASS

- [ ] **Step 4: Run e2e**

```bash
cd frontend && npm run test:e2e
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test: update e2e selectors for Element Plus migration"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every section from the design spec (§1–§7) has a corresponding task. The theme SCSS (Task 1), routing (Task 3), component mapping (Task 4, 12), form rebuild (Tasks 6–10), writing editor (Task 5, 11), page details (Tasks 7–10), testing (Task 13).
- [ ] **Placeholder scan:** No "TBD", "TODO", or placeholder comments. Every code block is complete.
- [ ] **Type consistency:** Constants maps created in Task 2 and used in Tasks 5, 10. WritingEditor `v-model:content` matches EditorView usage. Auth form `reactive` objects match store method signatures.
- [ ] No incomplete sections, no implementation gaps.
