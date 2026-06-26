<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { useMemoryStore } from '@/stores/memory'
import { useNovelStore } from '@/stores/novels'
import type { WorldSetting, WorldSettingCategory } from '@/types'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const deleteTarget = ref<number | null>(null)
const selectedCategory = ref<WorldSettingCategory | 'all'>('all')
const form = ref<{ title: string; category: WorldSettingCategory; content: string }>({ title: '', category: 'other', content: '' })

const categories: { value: WorldSettingCategory | 'all'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'geography', label: '地理' },
  { value: 'faction', label: '势力' },
  { value: 'rule', label: '规则' },
  { value: 'history', label: '历史' },
  { value: 'culture', label: '文化' },
  { value: 'other', label: '其他' },
]

const filteredSettings = computed(() => selectedCategory.value === 'all'
  ? memoryStore.worldSettings
  : memoryStore.worldSettings.filter((item) => item.category === selectedCategory.value))

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadWorldSettings(novelId.value)
})

function categoryLabel(category: string) {
  return categories.find((item) => item.value === category)?.label || category
}

function openCreate() {
  editingId.value = null
  form.value = { title: '', category: 'other', content: '' }
  showModal.value = true
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

async function handleDelete() {
  if (deleteTarget.value === null) return
  await memoryStore.deleteWorldSetting(novelId.value, deleteTarget.value)
  deleteTarget.value = null
}
</script>

<template>
    <div class="settings">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <div class="settings__header">
        <div>
          <h2 class="settings__title">世界观设定</h2>
          <p class="settings__subtitle">{{ novelStore.currentNovel?.title }}</p>
        </div>
        <AppButton size="sm" @click="openCreate">新建设定</AppButton>
      </div>

      <div class="settings__filters">
        <button v-for="category in categories" :key="category.value" class="settings__filter" :class="{ 'settings__filter--active': selectedCategory === category.value }" @click="selectedCategory = category.value">
          {{ category.label }}
        </button>
      </div>

      <AppEmpty v-if="filteredSettings.length === 0" text="暂无世界观设定" />
      <div v-else class="settings__grid">
        <AppCard v-for="setting in filteredSettings" :key="setting.id" class="setting-card">
          <div class="setting-card__header">
            <div>
              <h3>{{ setting.title }}</h3>
              <span>{{ categoryLabel(setting.category) }}</span>
            </div>
            <div class="setting-card__actions">
              <button @click="openEdit(setting)">编辑</button>
              <button @click="deleteTarget = setting.id">删除</button>
            </div>
          </div>
          <p>{{ setting.content }}</p>
        </AppCard>
      </div>

      <AppModal v-model:visible="showModal" :title="editingId ? '编辑设定' : '新建设定'" confirm-text="保存" cancel-text="取消" width="640px" @confirm="handleSave" @cancel="showModal = false">
        <div class="settings__form">
          <AppInput v-model="form.title" placeholder="设定标题" />
          <select v-model="form.category" class="settings__select">
            <option value="geography">地理</option>
            <option value="faction">势力</option>
            <option value="rule">规则</option>
            <option value="history">历史</option>
            <option value="culture">文化</option>
            <option value="other">其他</option>
          </select>
          <AppTextarea v-model="form.content" placeholder="设定内容" :rows="8" />
        </div>
      </AppModal>

      <AppConfirm :visible="deleteTarget !== null" title="删除设定" content="确定要删除这条世界观设定吗？" confirm-text="删除" confirm-variant="danger" @update:visible="deleteTarget = null" @confirm="handleDelete" @cancel="deleteTarget = null" />
    </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.settings { max-width: 1100px; margin: 0 auto; }
.settings__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.settings__title { font-size: $font-size-xl; font-weight: 700; }
.settings__subtitle { margin-top: $spacing-xs; color: $color-text-secondary; font-size: $font-size-sm; }
.settings__filters { display: flex; flex-wrap: wrap; gap: $spacing-sm; margin-bottom: $spacing-lg; }
.settings__filter { padding: 4px 12px; border-radius: $radius-md; background: $color-bg-card; color: $color-text-secondary; border: 1px solid $color-border; }
.settings__filter--active { background: $color-primary; color: #fff; border-color: $color-primary; }
.settings__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: $spacing-md; }
.settings__form { display: flex; flex-direction: column; gap: $spacing-md; }
.settings__select { border: 1px solid $color-border; border-radius: $radius-md; padding: 8px 16px; background: $color-bg-card; color: $color-text; }
.setting-card { display: flex; flex-direction: column; gap: $spacing-sm; }
.setting-card__header { display: flex; justify-content: space-between; gap: $spacing-md; }
.setting-card__header span { display: inline-block; margin-top: 4px; color: $color-primary-dark; font-size: $font-size-xs; }
.setting-card__actions { display: flex; gap: $spacing-sm; font-size: $font-size-sm; color: $color-primary-dark; }
.setting-card p { font-size: $font-size-sm; line-height: 1.8; white-space: pre-wrap; color: $color-text-secondary; }
</style>
