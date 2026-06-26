<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novels'
import { useMemoryStore } from '@/stores/memory'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'
import type { CharacterProfile } from '@/types'
import { ElMessageBox } from 'element-plus'

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
