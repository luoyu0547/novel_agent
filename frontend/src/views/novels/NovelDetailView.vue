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
import AppTextarea from '@/components/common/AppTextarea.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'

const route = useRoute(); const router = useRouter(); const novelStore = useNovelStore()
const novelId = computed(() => Number(route.params.id))
const chapters = computed(() => novelStore.currentNovel?.chapters || [])
const selectedChapterId = ref<number | null>(null)
const selectedChapter = computed(() => chapters.value.find((c) => c.id === selectedChapterId.value) || null)
const showChapterModal = ref(false); const newChapterTitle = ref(''); const deleteTarget = ref<number | null>(null)
const showNovelModal = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const editGenre = ref('')
const editStyleGuide = ref('')

function openNovelModal() {
  const novel = novelStore.currentNovel
  if (!novel) return
  editTitle.value = novel.title
  editDescription.value = novel.description || ''
  editGenre.value = novel.genre || ''
  editStyleGuide.value = novel.style_guide || ''
  showNovelModal.value = true
}

async function handleUpdateNovel() {
  if (!editTitle.value) return
  await novelStore.updateNovel(novelId.value, {
    title: editTitle.value,
    description: editDescription.value || null,
    genre: editGenre.value || null,
    style_guide: editStyleGuide.value || null,
  })
  showNovelModal.value = false
}

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
function closeDeleteConfirm() { deleteTarget.value = null }
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
        <NovelWorkspaceTabs :novel-id="novelId" />
        <div class="novel-detail__content-header">
          <h2 class="novel-detail__section-title">{{ novelStore.currentNovel.title }}</h2>
          <AppButton size="sm" variant="secondary" @click="openNovelModal">编辑信息</AppButton>
        </div>
        <div class="novel-detail__meta">
          <span v-if="novelStore.currentNovel.genre">类型：{{ novelStore.currentNovel.genre }}</span>
          <span v-if="novelStore.currentNovel.style_guide">风格指南：{{ novelStore.currentNovel.style_guide }}</span>
        </div>
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
    <AppConfirm :visible="deleteTarget !== null" title="删除章节" content="确定要删除这个章节吗？此操作不可恢复。" confirm-text="删除" :confirm-variant="'danger'" @confirm="handleDeleteChapter" @cancel="closeDeleteConfirm" @update:visible="closeDeleteConfirm" />
    <AppModal v-model:visible="showNovelModal" title="编辑小说信息" confirm-text="保存" cancel-text="取消" @confirm="handleUpdateNovel" @cancel="showNovelModal = false">
      <AppInput v-model="editTitle" placeholder="小说标题" />
      <div style="height:12px" />
      <AppTextarea v-model="editDescription" placeholder="小说简介" :rows="3" />
      <div style="height:12px" />
      <AppInput v-model="editGenre" placeholder="小说类型" />
      <div style="height:12px" />
      <AppTextarea v-model="editStyleGuide" placeholder="风格指南" :rows="4" />
    </AppModal>
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
  &__content-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: $spacing-sm; }
  &__section-title { font-size: $font-size-lg; font-weight: 700; }
  &__meta { display: flex; gap: $spacing-md; margin-bottom: $spacing-md; font-size: $font-size-sm; color: $color-text-secondary; }
  &__preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-md; }
  &__preview-title { font-size: $font-size-lg; font-weight: 700; }
  &__preview-text { white-space: pre-wrap; line-height: 1.8; }
  &__no-selection { display: flex; align-items: center; justify-content: center; height: 100%; } }
</style>
