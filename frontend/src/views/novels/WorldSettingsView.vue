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
