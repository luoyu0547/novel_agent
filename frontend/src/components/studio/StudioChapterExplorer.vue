<script setup lang="ts">
import type { ChapterOut } from '@/types/novel'
import type { WritingSession } from '@/types/writingStudio'

export interface SelectPayload {
  kind: 'chapter' | 'draft'
  chapterId?: number
  sessionId?: number
}

const props = defineProps<{
  chapters: ChapterOut[]
  sessions: WritingSession[]
  selectedChapterId: number | null
  selectedSessionId: number | null
}>()

const emit = defineEmits<{
  select: [payload: SelectPayload]
}>()

function handleChapterClick(chapterId: number) {
  emit('select', { kind: 'chapter', chapterId })
}

function handleSessionClick(sessionId: number) {
  emit('select', { kind: 'draft', sessionId })
}
</script>

<template>
  <div class="studio-explorer">
    <div v-if="chapters.length || sessions.length" class="studio-explorer__content">
      <!-- Accepted chapters group -->
      <div v-if="chapters.length" data-testid="studio-chapters-group" class="studio-explorer__group">
        <div class="studio-explorer__group-title">章节</div>
        <div
          v-for="chapter in chapters"
          :key="chapter.id"
          :data-testid="`explorer-chapter-${chapter.id}`"
          class="studio-explorer__item"
          :class="{ 'is-active': selectedChapterId === chapter.id }"
          @click="handleChapterClick(chapter.id)"
        >
          <span class="studio-explorer__item-title">{{ chapter.title }}</span>
          <el-tag v-if="chapter.status === 'locked'" size="small" type="info">已锁定</el-tag>
        </div>
      </div>

      <!-- Unaccepted drafts / sessions group -->
      <div v-if="sessions.length" data-testid="studio-drafts-group" class="studio-explorer__group">
        <div class="studio-explorer__group-title">草稿</div>
        <div
          v-for="session in sessions"
          :key="session.id"
          :data-testid="`explorer-session-${session.id}`"
          class="studio-explorer__item"
          :class="{ 'is-active': selectedSessionId === session.id }"
          @click="handleSessionClick(session.id)"
        >
          <span class="studio-explorer__item-title">{{ session.title }}</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else data-testid="explorer-empty" class="studio-explorer__empty">
      <span>暂无内容</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.studio-explorer {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;

  &__content {
    display: flex;
    flex-direction: column;
    gap: $spacing-md;
  }

  &__group {
    display: flex;
    flex-direction: column;
  }

  &__group-title {
    font-size: $font-size-xs;
    font-weight: 600;
    color: $color-text-secondary;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: $spacing-xs $spacing-md;
    margin-bottom: $spacing-xs;
  }

  &__item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-sm $spacing-md;
    cursor: pointer;
    border-radius: $radius-sm;
    transition: background $transition-fast;
    gap: $spacing-sm;

    &:hover {
      background: $color-bg-secondary;
    }

    &.is-active {
      background: $color-primary-light;
      color: $color-text;
    }
  }

  &__item-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    font-size: $font-size-sm;
  }

  &__empty {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: $color-text-placeholder;
    font-size: $font-size-sm;
    padding: $spacing-xl;
  }
}
</style>
