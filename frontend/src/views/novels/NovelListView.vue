<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novels'

import { ElMessageBox } from 'element-plus'

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
