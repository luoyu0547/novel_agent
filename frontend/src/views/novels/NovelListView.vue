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
