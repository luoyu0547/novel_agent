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
  if (selectedChapterId.value) router.push({ name: 'studio', query: { chapter_id: String(selectedChapterId.value) } })
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