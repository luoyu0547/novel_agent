<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DraftVersion } from '@/types/revision'

const props = defineProps<{
  versions: DraftVersion[]
  currentVersion: DraftVersion | null
}>()

const emit = defineEmits<{
  'create-version': [payload: { basedOnVersionId: number; changeReason: string }]
  'restore': [payload: { versionId: number; changeReason: string }]
  'select-version': [versionId: number]
}>()

const showCreateDialog = ref(false)
const createBaseVersionId = ref<number | null>(null)
const createReason = ref('')

const showRestoreDialog = ref(false)
const restoreVersionId = ref<number | null>(null)
const restoreReason = ref('')

// Internal revisions are provided via slot by the parent component

const currentVersionLabel = computed(() => {
  if (!props.currentVersion) return ''
  return `v${props.currentVersion.version} ${props.currentVersion.change_reason}`
})

const versionHistory = computed(() => {
  return [...props.versions].sort((a, b) => b.version - a.version)
})

function openCreateDialog() {
  if (props.currentVersion) {
    createBaseVersionId.value = props.currentVersion.id
  }
  createReason.value = ''
  showCreateDialog.value = true
}

function handleCreateVersion() {
  if (!createBaseVersionId.value || !createReason.value.trim()) return
  emit('create-version', {
    basedOnVersionId: createBaseVersionId.value,
    changeReason: createReason.value.trim(),
  })
  showCreateDialog.value = false
  createReason.value = ''
}

function openRestoreDialog(version: DraftVersion) {
  restoreVersionId.value = version.id
  restoreReason.value = ''
  showRestoreDialog.value = true
}

function handleRestore() {
  if (!restoreVersionId.value || !restoreReason.value.trim()) return
  emit('restore', {
    versionId: restoreVersionId.value,
    changeReason: restoreReason.value.trim(),
  })
  showRestoreDialog.value = false
  restoreReason.value = ''
}

function handleSelectVersion(version: DraftVersion) {
  emit('select-version', version.id)
}
</script>

<template>
  <div class="draft-version-timeline">
    <!-- Current version display -->
    <div v-if="currentVersion" class="draft-version-timeline__current">
      <span class="draft-version-timeline__current-label">当前版本：</span>
      <span class="draft-version-timeline__current-value" data-testid="current-version-label">{{ currentVersionLabel }}</span>
    </div>

    <!-- Internal revisions slot -->
    <div class="draft-version-timeline__internal">
      <p class="draft-version-timeline__section-title" data-testid="internal-revisions-title">内部修改：</p>
      <slot name="internal-revisions">
        <!-- Parent provides R1, R2 entries here -->
      </slot>
    </div>

    <!-- Version history -->
    <div class="draft-version-timeline__history">
      <p class="draft-version-timeline__section-title" data-testid="version-history-title">版本历史：</p>
      <el-timeline>
        <el-timeline-item
          v-for="v in versionHistory"
          :key="v.id"
          :timestamp="v.created_at"
          placement="top"
        >
          <div class="draft-version-timeline__version-item">
            <span class="draft-version-timeline__version-label">
              v{{ v.version }} {{ v.change_reason }}
            </span>
            <el-tag
              v-if="currentVersion && v.id === currentVersion.id"
              size="small"
              type="success"
            >
              当前
            </el-tag>
            <el-tag
              v-else-if="v.status === 'archived'"
              size="small"
              type="info"
            >
              已归档
            </el-tag>
            <el-button
              v-if="currentVersion && v.id !== currentVersion.id && v.status !== 'archived'"
              size="small"
              text
              @click="openRestoreDialog(v)"
            >
              恢复
            </el-button>
            <el-button
              v-if="currentVersion && v.id !== currentVersion.id"
              size="small"
              text
              @click="handleSelectVersion(v)"
            >
              查看
            </el-button>
          </div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <!-- Create new version button -->
    <el-button
      type="primary"
      size="small"
      class="draft-version-timeline__create-btn"
      data-testid="create-version-btn"
      @click="openCreateDialog"
    >
      创建新版本
    </el-button>

    <!-- Create version dialog -->
    <el-dialog
      v-model="showCreateDialog"
      data-testid="create-version-dialog"
      title="创建新版本"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" size="small">
        <el-form-item label="基准版本">
          <el-select v-model="createBaseVersionId" placeholder="选择基准版本">
            <el-option
              v-for="v in versions"
              :key="v.id"
              :label="`v${v.version} ${v.change_reason}`"
              :value="v.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="变更原因">
          <el-input
            v-model="createReason"
            type="textarea"
            :rows="2"
            placeholder="描述创建新版本的原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!createBaseVersionId || !createReason.trim()"
          @click="handleCreateVersion"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- Restore version dialog -->
    <el-dialog
      v-model="showRestoreDialog"
      title="恢复版本"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="draft-version-timeline__restore-notice"
      >
        <template #title>
          恢复说明
        </template>
        恢复将修改当前版本的内容，不会创建新版本。
        <span data-testid="restore-notice-text" />
      </el-alert>
      <el-form label-width="100px" size="small">
        <el-form-item label="恢复原因">
          <el-input
            v-model="restoreReason"
            type="textarea"
            :rows="2"
            placeholder="描述恢复此版本的原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRestoreDialog = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!restoreReason.trim()"
          @click="handleRestore"
        >
          恢复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.draft-version-timeline__current {
  margin-bottom: 12px;
}

.draft-version-timeline__current-label {
  font-weight: 600;
  color: #303133;
}

.draft-version-timeline__current-value {
  font-size: 14px;
  color: #409eff;
}

.draft-version-timeline__section-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin: 8px 0 4px;
}

.draft-version-timeline__internal {
  margin-bottom: 12px;
  padding-left: 12px;
}

.draft-version-timeline__history {
  margin-bottom: 12px;
}

.draft-version-timeline__version-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-version-timeline__version-label {
  font-size: 13px;
}

.draft-version-timeline__create-btn {
  margin-top: 8px;
}

.draft-version-timeline__restore-notice {
  margin-bottom: 12px;
}
</style>
