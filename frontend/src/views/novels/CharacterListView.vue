<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/common/AppButton.vue'
import AppCard from '@/components/common/AppCard.vue'
import AppConfirm from '@/components/common/AppConfirm.vue'
import AppEmpty from '@/components/common/AppEmpty.vue'
import AppInput from '@/components/common/AppInput.vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppTextarea from '@/components/common/AppTextarea.vue'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import { useMemoryStore } from '@/stores/memory'
import { useNovelStore } from '@/stores/novels'
import type { CharacterProfile } from '@/types'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'

const route = useRoute()
const novelStore = useNovelStore()
const memoryStore = useMemoryStore()
const novelId = computed(() => Number(route.params.id))
const showModal = ref(false)
const editingId = ref<number | null>(null)
const deleteTarget = ref<number | null>(null)
const form = ref({ name: '', story_role: '', identity: '', personality: '', motivation: '', speech_style: '', behavior_rules_text: '', current_state: '' })

onMounted(async () => {
  await novelStore.getNovel(novelId.value)
  await memoryStore.loadCharacters(novelId.value)
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', story_role: '', identity: '', personality: '', motivation: '', speech_style: '', behavior_rules_text: '', current_state: '' }
  showModal.value = true
}

function openEdit(character: CharacterProfile) {
  editingId.value = character.id
  form.value = {
    name: character.name,
    story_role: character.story_role,
    identity: character.identity,
    personality: character.personality,
    motivation: character.motivation,
    speech_style: character.speech_style,
    behavior_rules_text: joinBehaviorRules(character.behavior_rules),
    current_state: character.current_state,
  }
  showModal.value = true
}

async function handleSave() {
  if (!form.value.name) return
  const payload = {
    name: form.value.name,
    story_role: form.value.story_role,
    identity: form.value.identity,
    personality: form.value.personality,
    motivation: form.value.motivation,
    speech_style: form.value.speech_style,
    behavior_rules: splitBehaviorRules(form.value.behavior_rules_text),
    current_state: form.value.current_state,
  }
  if (editingId.value) await memoryStore.updateCharacter(novelId.value, editingId.value, payload)
  else await memoryStore.createCharacter(novelId.value, payload)
  showModal.value = false
}

async function handleDelete() {
  if (deleteTarget.value === null) return
  await memoryStore.deleteCharacter(novelId.value, deleteTarget.value)
  deleteTarget.value = null
}
</script>

<template>
  <AppLayout>
    <div class="characters">
      <NovelWorkspaceTabs :novel-id="novelId" />
      <div class="characters__header">
        <div>
          <h2 class="characters__title">角色卡片</h2>
          <p class="characters__subtitle">{{ novelStore.currentNovel?.title }}</p>
        </div>
        <AppButton size="sm" @click="openCreate">新建角色</AppButton>
      </div>

      <AppEmpty v-if="memoryStore.characters.length === 0" text="暂无角色卡" />
      <div v-else class="characters__grid">
        <AppCard v-for="character in memoryStore.characters" :key="character.id" class="character-card">
          <div class="character-card__header">
            <h3>{{ character.name }}</h3>
            <div class="character-card__actions">
              <button @click="openEdit(character)">编辑</button>
              <button @click="deleteTarget = character.id">删除</button>
            </div>
          </div>
          <p v-if="character.story_role"><strong>叙事功能：</strong>{{ character.story_role }}</p>
          <p v-if="character.identity"><strong>身份：</strong>{{ character.identity }}</p>
          <p v-if="character.personality"><strong>性格：</strong>{{ character.personality }}</p>
          <p v-if="character.motivation"><strong>动机：</strong>{{ character.motivation }}</p>
          <p v-if="character.speech_style"><strong>说话方式：</strong>{{ character.speech_style }}</p>
          <p v-if="character.current_state"><strong>当前状态：</strong>{{ character.current_state }}</p>
          <ul v-if="character.behavior_rules.length" class="character-card__rules">
            <li v-for="rule in character.behavior_rules" :key="rule">{{ rule }}</li>
          </ul>
        </AppCard>
      </div>

      <AppModal v-model:visible="showModal" :title="editingId ? '编辑角色' : '新建角色'" confirm-text="保存" cancel-text="取消" width="720px" @confirm="handleSave" @cancel="showModal = false">
        <div class="characters__form">
          <AppInput v-model="form.name" placeholder="角色名" />
          <AppInput v-model="form.story_role" placeholder="叙事功能，如主角 / 反派 / 导师" />
          <AppInput v-model="form.identity" placeholder="世界内身份，如边境军少将军" />
          <AppTextarea v-model="form.personality" placeholder="性格特征" :rows="3" />
          <AppTextarea v-model="form.motivation" placeholder="动机和目标" :rows="3" />
          <AppTextarea v-model="form.speech_style" placeholder="说话方式约束" :rows="3" />
          <AppTextarea v-model="form.behavior_rules_text" placeholder="行为边界，每行一条" :rows="4" />
          <AppTextarea v-model="form.current_state" placeholder="当前状态" :rows="3" />
        </div>
      </AppModal>

      <AppConfirm :visible="deleteTarget !== null" title="删除角色" content="确定要删除这个角色卡吗？" confirm-text="删除" :confirm-variant="'danger'" @confirm="handleDelete" @cancel="deleteTarget = null" @update:visible="() => deleteTarget = null" />
    </div>
  </AppLayout>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;
.characters { max-width: 1100px; margin: 0 auto; }
.characters__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: $spacing-lg; }
.characters__title { font-size: $font-size-xl; font-weight: 700; }
.characters__subtitle { margin-top: $spacing-xs; color: $color-text-secondary; font-size: $font-size-sm; }
.characters__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: $spacing-md; }
.characters__form { display: flex; flex-direction: column; gap: $spacing-md; }
.character-card { display: flex; flex-direction: column; gap: $spacing-sm; }
.character-card__header { display: flex; justify-content: space-between; gap: $spacing-md; }
.character-card__actions { display: flex; gap: $spacing-sm; font-size: $font-size-sm; color: $color-primary-dark; }
.character-card p { font-size: $font-size-sm; line-height: 1.7; color: $color-text-secondary; }
.character-card__rules { padding-left: $spacing-lg; color: $color-text-secondary; font-size: $font-size-sm; line-height: 1.7; }
</style>
