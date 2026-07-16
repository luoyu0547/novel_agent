<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import { useWritingStudioStore } from '@/stores/writingStudio'
import StudioChapterExplorer from '@/components/studio/StudioChapterExplorer.vue'
import StudioDocumentPane from '@/components/studio/StudioDocumentPane.vue'
import StudioConversationPane from '@/components/studio/StudioConversationPane.vue'
import StudioVersionInspector from '@/components/studio/StudioVersionInspector.vue'
import type { WritingSession, StudioDocument, StudioConfirmationAction } from '@/types/writingStudio'

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()
const studioStore = useWritingStudioStore()

const novelId = computed(() => Number(route.params.id))
const leftPaneVisible = ref(true)
const rightPaneVisible = ref(true)

// Selected items in explorer
const selectedChapterId = ref<number | null>(null)
const selectedSessionId = ref<number | null>(null)

// Version inspector drawer
const versionInspectorVisible = ref(false)

// Chapters from novel store
const chapters = computed(() => novelStore.currentNovel?.chapters || [])

// Sessions representing unaccepted drafts (placeholder until list API exists)
const sessions = computed<WritingSession[]>(() => {
  if (studioStore.session && studioStore.session.novel_id === novelId.value) {
    return [studioStore.session]
  }
  return []
})

// Active document for the center pane
const activeDocument = computed<StudioDocument | null>(() => {
  if (selectedSessionId.value && studioStore.document) {
    return studioStore.document
  }
  if (selectedChapterId.value) {
    const chapter = chapters.value.find(c => c.id === selectedChapterId.value)
    if (chapter) {
      return {
        kind: 'chapter' as const,
        chapterId: chapter.id,
        title: chapter.title,
        content: chapter.content,
        baseRevisionSequence: 0,
      }
    }
  }
  return null
})

// Handle explorer selection
function handleExplorerSelect(payload: { kind: 'chapter' | 'draft'; chapterId?: number; sessionId?: number }) {
  if (payload.kind === 'chapter' && payload.chapterId != null) {
    selectedChapterId.value = payload.chapterId
    selectedSessionId.value = null
  } else if (payload.kind === 'draft' && payload.sessionId != null) {
    selectedSessionId.value = payload.sessionId
    selectedChapterId.value = null
  }
}

// Navigate back to novel detail
function goBack() {
  router.push({ name: 'novel-detail', params: { id: novelId.value } })
}

// Load novel data on mount
onMounted(async () => {
  await novelStore.getNovel(novelId.value)

  // If chapter_id is in the query, pre-select it
  const queryChapterId = route.query.chapter_id
  if (queryChapterId) {
    selectedChapterId.value = Number(queryChapterId)
  }

  // If session_id is in the query, load the session
  const querySessionId = route.query.session_id
  if (querySessionId) {
    const sid = Number(querySessionId)
    selectedSessionId.value = sid
    try {
      await studioStore.loadSession(novelId.value, sid)
    } catch {
      // Session load failure is non-fatal; explorer still renders
    }
  }
})

// Watch for route query changes
watch(() => route.query.chapter_id, (newId) => {
  if (newId) {
    selectedChapterId.value = Number(newId)
    selectedSessionId.value = null
  }
})

watch(() => route.query.session_id, (newId) => {
  if (newId) {
    const sid = Number(newId)
    selectedSessionId.value = sid
    selectedChapterId.value = null
    studioStore.loadSession(novelId.value, sid).catch(() => {})
  }
})

// Toggle left pane
function toggleLeftPane() {
  leftPaneVisible.value = !leftPaneVisible.value
}

// Toggle right pane
function toggleRightPane() {
  rightPaneVisible.value = !rightPaneVisible.value
}

// Document pane event handlers
function handleUpdateTitle(value: string) {
  if (studioStore.document) {
    studioStore.document.title = value
  }
}

function handleUpdateContent(value: string) {
  if (studioStore.document) {
    studioStore.document.content = value
  }
}

async function handleSaveWorkingCopy(payload: { title: string; content: string; baseRevisionSequence: number }) {
  if (studioStore.document) {
    // Sync the latest values before saving
    studioStore.document.title = payload.title
    studioStore.document.content = payload.content
    try {
      await studioStore.saveWorkingCopy(novelId.value)
    } catch {
      // Error state is handled by the store's saveState
    }
  }
}

async function handleAccept() {
  if (studioStore.session) {
    // Find the latest needs_confirmation message
    const pending = [...studioStore.messages].reverse().find(m => m.action_status === 'needs_confirmation')
    if (pending) {
      await studioStore.confirmAction(novelId.value, pending.id, 'accept')
    }
  }
}

async function handleDiscard() {
  if (studioStore.session) {
    const pending = [...studioStore.messages].reverse().find(m => m.action_status === 'needs_confirmation')
    if (pending) {
      await studioStore.confirmAction(novelId.value, pending.id, 'discard')
    }
  }
}

// Conversation pane event handlers
async function handleSendMessage(text: string) {
  await studioStore.sendMessage(novelId.value, text)
}

async function handleConfirmAction(messageId: number, action: StudioConfirmationAction, payload: Record<string, unknown>) {
  await studioStore.confirmAction(novelId.value, messageId, action, payload)
}

function handleOpenSources(writingRunId: number) {
  // Sources are rendered inline in StudioMessage via StudioSourcesPanel
  // This handler is available for future top-level source navigation
}

async function handleRetryMessage(messageId: number) {
  // Retry: re-send the original author message that preceded the failed one
  const idx = studioStore.messages.findIndex(m => m.id === messageId)
  if (idx > 0) {
    const prev = studioStore.messages[idx - 1]
    if (prev && prev.role === 'author' && prev.content_json?.text) {
      await studioStore.sendMessage(novelId.value, prev.content_json.text as string)
    }
  }
}

// Sending state derived from store
const sending = ref(false)

function handleOpenVersionInspector() {
  versionInspectorVisible.value = true
}

defineExpose({ toggleLeftPane, toggleRightPane })
</script>

<template>
  <div class="studio">
    <!-- Top bar -->
    <header class="studio__topbar">
      <div class="studio__topbar-left">
        <el-button text @click="goBack" data-testid="studio-back-btn">
          返回
        </el-button>
        <span class="studio__title">{{ novelStore.currentNovel?.title || '创作工坊' }}</span>
      </div>
      <div class="studio__topbar-right">
        <el-button
          text
          data-testid="studio-left-toggle"
          @click="toggleLeftPane"
        >
          {{ leftPaneVisible ? '隐藏目录' : '显示目录' }}
        </el-button>
        <el-button
          text
          data-testid="studio-right-toggle"
          @click="toggleRightPane"
        >
          {{ rightPaneVisible ? '隐藏面板' : '显示面板' }}
        </el-button>
      </div>
    </header>

    <!-- Three-pane workbench -->
    <div
      class="studio__workbench"
      :class="{
        'studio__workbench--left-hidden': !leftPaneVisible,
        'studio__workbench--right-hidden': !rightPaneVisible,
      }"
      data-testid="studio-workbench"
    >
      <!-- Left pane: Chapter explorer -->
      <aside v-if="leftPaneVisible" class="studio__left-pane" data-testid="studio-left-pane">
        <StudioChapterExplorer
          :chapters="chapters"
          :sessions="sessions"
          :selected-chapter-id="selectedChapterId"
          :selected-session-id="selectedSessionId"
          @select="handleExplorerSelect"
        />
      </aside>

      <!-- Center pane: Document editor -->
      <main class="studio__center-pane" data-testid="studio-center-pane">
        <StudioDocumentPane
          :document="activeDocument"
          :save-state="studioStore.saveState"
          @update:title="handleUpdateTitle"
          @update:content="handleUpdateContent"
          @save-working-copy="handleSaveWorkingCopy"
          @accept="handleAccept"
          @discard="handleDiscard"
          @open-version-inspector="handleOpenVersionInspector"
        />
      </main>

      <!-- Right pane: AI conversation -->
      <aside v-if="rightPaneVisible" class="studio__right-pane" data-testid="studio-right-pane">
        <StudioConversationPane
          :messages="studioStore.messages"
          :novel-id="novelId"
          :sending="sending"
          @send-message="handleSendMessage"
          @confirm-action="handleConfirmAction"
          @open-sources="handleOpenSources"
          @retry-message="handleRetryMessage"
        />
      </aside>
    </div>

    <!-- Responsive drawers for small screens -->
    <el-drawer
      v-model="leftPaneVisible"
      direction="ltr"
      size="240px"
      :with-header="false"
      class="studio__left-drawer"
    >
      <StudioChapterExplorer
        :chapters="chapters"
        :sessions="sessions"
        :selected-chapter-id="selectedChapterId"
        :selected-session-id="selectedSessionId"
        @select="handleExplorerSelect"
      />
    </el-drawer>

    <el-drawer
      v-model="rightPaneVisible"
      direction="rtl"
      size="380px"
      :with-header="false"
      data-testid="studio-ai-drawer"
      class="studio__right-drawer"
    >
      <StudioConversationPane
        :messages="studioStore.messages"
        :novel-id="novelId"
        :sending="sending"
        @send-message="handleSendMessage"
        @confirm-action="handleConfirmAction"
        @open-sources="handleOpenSources"
        @retry-message="handleRetryMessage"
      />
    </el-drawer>

    <!-- Version inspector drawer -->
    <StudioVersionInspector
      v-model="versionInspectorVisible"
      :versions="[]"
      :current-version="null"
      :revisions="[]"
      :issues="[]"
      :candidate="null"
      :selected-issue-id="null"
    />
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: $color-bg;

  &__topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 0 $spacing-md;
    background: $color-bg-card;
    border-bottom: 1px solid $color-border;
    flex-shrink: 0;
  }

  &__topbar-left,
  &__topbar-right {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
  }

  &__title {
    font-size: $font-size-md;
    font-weight: 600;
    color: $color-text;
  }

  &__workbench {
    display: grid;
    grid-template-columns: 240px minmax(640px, 1fr) 380px;
    flex: 1;
    min-height: 0;

    &--left-hidden {
      grid-template-columns: 0 minmax(640px, 1fr) 380px;
    }

    &--right-hidden {
      grid-template-columns: 240px minmax(640px, 1fr) 0;
    }

    &--left-hidden.studio__workbench--right-hidden {
      grid-template-columns: 0 minmax(640px, 1fr) 0;
    }
  }

  &__left-pane {
    background: $color-bg-card;
    border-right: 1px solid $color-border;
    overflow-y: auto;
  }

  &__center-pane {
    overflow-y: auto;
    background: $color-bg;
  }

  &__right-pane {
    background: $color-bg-card;
    border-left: 1px solid $color-border;
    overflow-y: auto;
  }

  // Hide drawers at desktop sizes; they show at mobile sizes
  &__left-drawer,
  &__right-drawer {
    display: none;
  }
}

// ── Responsive breakpoints ──────────────────────────────────────────

@media (max-width: 1279px) {
  .studio {
    &__workbench {
      grid-template-columns: 0 minmax(640px, 1fr) 380px;

      // When left pane is toggled on at medium width, overlay it
      &:not(.studio__workbench--left-hidden) {
        // Keep left column collapsed in grid, use drawer instead
      }
    }

    &__left-pane {
      display: none;
    }

    &__left-drawer {
      display: block;
    }
  }
}

@media (max-width: 1023px) {
  .studio {
    &__workbench {
      grid-template-columns: minmax(320px, 1fr);

      &--left-hidden,
      &--right-hidden {
        grid-template-columns: minmax(320px, 1fr);
      }
    }

    &__left-pane,
    &__right-pane {
      display: none;
    }

    &__left-drawer,
    &__right-drawer {
      display: block;
    }
  }
}
</style>
