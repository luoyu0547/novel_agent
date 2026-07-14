<script setup lang="ts">
import { useWritingStore } from '@/stores/writing'
import { usePlotPlanningStore } from '@/stores/plotPlanning'
import { usePendingMemoryStore } from '@/stores/pendingMemory'
import { useRevisionsStore } from '@/stores/revisions'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import PlotUnitPanel from '@/components/writing/PlotUnitPanel.vue'
import AuthorFoundationPanel from '@/components/writing/AuthorFoundationPanel.vue'
import DecisionCard from '@/components/writing/DecisionCard.vue'
import DraftRevisionDiff from '@/components/writing/DraftRevisionDiff.vue'
import ReviewIssuePanel from '@/components/writing/ReviewIssuePanel.vue'
import RevisionCandidatePanel from '@/components/writing/RevisionCandidatePanel.vue'
import DraftVersionTimeline from '@/components/writing/DraftVersionTimeline.vue'
import RevisionHistoryPanel from '@/components/writing/RevisionHistoryPanel.vue'
import type { NovelBlueprint, WritingRun } from '@/types/writing'
import type { PlotUnitCreate, PlotUnit } from '@/types/plotPlanning'
import * as writingApi from '@/api/writing'

const route = useRoute()
const store = useWritingStore()
const ppStore = usePlotPlanningStore()
const pendingMemoryStore = usePendingMemoryStore()
const revisionsStore = useRevisionsStore()
const novelId = Number(route.params.id)

const authorInput = ref('')
const showBlueprintEditor = ref(false)
const editingBlueprintId = ref<number | null>(null)
const blueprintText = ref('')
const activeSection = ref<'blueprint' | 'plan' | 'brief' | 'context' | 'draft' | 'decision' | 'revision'>('blueprint')

// Phase 4: editor buffer tracks current version content
const editorContent = ref('')
const editorChangeReason = ref('')
const ignoreReason = ref('')
const showIgnoreDialog = ref(false)
const ignoreIssueId = ref<number | null>(null)
const forceAcceptReason = ref('')
const showForceAcceptDialog = ref(false)

const latestDraftBlueprint = computed(() =>
  store.blueprints.find(b => b.status === 'draft') || null,
)

const editingTargetWords = ref(3000)
const editingMinWords = ref(2000)
const editingMaxWords = ref(5000)

const pendingCountAfterAccept = ref(0)
const extractionError = ref<string | null>(null)

const activeRun = computed<WritingRun | null>(() =>
  store.writingRuns.find(r => r.status === 'completed' || r.status === 'failed' || r.status === 'decision_required') || null,
)

const decisionRequiredRun = computed<WritingRun | null>(() =>
  store.writingRuns.find(r => r.status === 'decision_required') || null,
)

// Phase 4: determine if workspace is read-only
const isReadOnly = computed(() => {
  if (!activeRun.value) return false
  return ['accepted', 'discarded', 'locked'].includes(activeRun.value.status)
})

// Phase 4: internal revisions for the timeline (applied revisions on current version)
const internalRevisions = computed(() =>
  revisionsStore.revisions.filter(r => r.status === 'applied'),
)

// Phase 4: open blocking issues
const blockingIssues = computed(() =>
  revisionsStore.reviewIssues.filter(i => i.status === 'open' && i.severity === 'blocking'),
)

// Phase 4: pending candidates
const pendingCandidates = computed(() =>
  revisionsStore.revisions.filter(r => r.status === 'candidate'),
)

// Watch currentVersion to sync editor buffer
watch(() => revisionsStore.currentVersion, (v) => {
  if (v) {
    editorContent.value = v.content
  }
}, { immediate: true })

onMounted(async () => {
  await store.fetchBlueprints(novelId)
  if (store.activeBlueprint) {
    activeSection.value = 'plan'
    blueprintText.value = JSON.stringify(store.activeBlueprint.content_json, null, 2)
  } else if (store.blueprints.length > 0) {
    blueprintText.value = JSON.stringify(store.blueprints[0]!.content_json, null, 2)
  }
  await ppStore.fetchFoundation(novelId)
  await ppStore.fetchPlotUnits(novelId)
  await ppStore.fetchPendingDecisions(novelId)
})

// Phase 4: Load Phase 4 data when an active run exists
watch(activeRun, async (run) => {
  if (run && (run.status === 'completed' || run.status === 'decision_required')) {
    await revisionsStore.loadWorkspace(novelId, run.id)
    if (revisionsStore.currentVersion) {
      editorContent.value = revisionsStore.currentVersion.content
    }
  }
}, { immediate: true })

async function handleGenerateBlueprint() {
  if (!authorInput.value.trim()) {
    ElMessage.warning('请输入小说构思')
    return
  }
  const bp = await store.generateBlueprint(novelId, authorInput.value)
  blueprintText.value = JSON.stringify(bp.content_json, null, 2)
  ElMessage.success('蓝图已生成')
  activeSection.value = 'plan'
}

async function handleActivate(bpId: number) {
  await store.activateBlueprint(novelId, bpId)
  ElMessage.success('蓝图已激活')
}

async function handleGeneratePlan() {
  await store.generateChapterPlan(novelId)
  ElMessage.success('章节计划已生成')
  activeSection.value = 'brief'
}

async function handleGenerateBrief() {
  if (!store.latestPlan) return
  await store.generateChapterBrief(
    novelId,
    store.latestPlan.id,
    ppStore.activePlan?.id,
    authorInput.value || undefined,
  )
  ElMessage.success('任务书已生成')
  activeSection.value = 'context'
}

async function handleGenerateContext() {
  if (!store.latestBrief) return
  await store.generateContextPackage(
    novelId,
    store.latestBrief.id,
    ppStore.activePlan?.id,
    authorInput.value || undefined,
  )
  ElMessage.success('上下文包已生成')
  activeSection.value = 'draft'
}

async function handleGenerateDraft() {
  if (!store.latestBrief) return
  try {
    await store.createWritingRun(
      novelId,
      store.latestBrief.id,
      ppStore.activePlan?.id,
      authorInput.value || undefined,
    )
    ElMessage.success('草稿已生成')
  } catch {
    ElMessage.error('生成草稿失败')
  }
}

async function handleAcceptRun(runId: number) {
  // Phase 4: Check for blocking issues
  if (blockingIssues.value.length > 0) {
    forceAcceptReason.value = ''
    showForceAcceptDialog.value = true
    return
  }

  // Phase 4: Check for pending candidates
  if (pendingCandidates.value.length > 0) {
    ElMessage.warning('存在待处理的候选修订，请先处理')
    activeSection.value = 'revision'
    return
  }

  await doAcceptRun(runId)
}

async function doAcceptRun(runId: number, forceReason?: string) {
  try {
    const acceptOptions = forceReason ? { force_accept: true, force_reason: forceReason } : undefined
    const result = await store.acceptRun(novelId, runId, acceptOptions)
    pendingCountAfterAccept.value = result.extraction.pending_count
    extractionError.value = result.extraction.error
    ElMessage.success('草稿已接受并写入章节')
    if (result.extraction.pending_count > 0) {
      await pendingMemoryStore.fetchMemories(novelId)
    }
  } catch {
    ElMessage.error('接受失败')
  }
}

async function handleForceAccept() {
  if (!forceAcceptReason.value.trim() || !activeRun.value) return
  showForceAcceptDialog.value = false
  await doAcceptRun(activeRun.value.id, forceAcceptReason.value.trim())
}

async function handleDiscardRun(runId: number) {
  await store.discardRun(novelId, runId)
  ElMessage.success('草稿已废弃')
}

// --- Phase 3 handlers ---
const foundationOutline = ref('')
const foundationIntent = ref('')
const foundationStageGoal = ref('')

async function handleSaveFoundation(data: { outline?: string; current_intent?: string; stage_goal?: string }) {
  await ppStore.updateFoundation(novelId, data)
  ElMessage.success('作者资料已保存')
}

async function handleCreatePlotUnit(data: PlotUnitCreate) {
  await ppStore.createPlotUnit(novelId, data)
  ElMessage.success('剧情单元已创建')
}

async function handlePlotUnitSelect(unit: PlotUnit) {
  await ppStore.selectPlotUnit(novelId, unit)
}

async function handleGeneratePlotPlan(plotUnitId: number, authorInput: string) {
  const plan = await ppStore.generatePlan(novelId, plotUnitId, authorInput)
  if (plan) {
    ElMessage.success('计划已生成')
  }
}

async function handleConfirmPlan(plotUnitId: number, revisionId: number) {
  await ppStore.confirmPlan(novelId, plotUnitId, revisionId)
  ElMessage.success('计划已确认')
}

async function handleDecisionChoose(payload: { decisionId: number; optionIndex?: number; customIntent?: string }) {
  await ppStore.chooseDecision(novelId, payload.decisionId, {
    option_index: payload.optionIndex,
    custom_intent: payload.customIntent,
  })
  ElMessage.success('决策已应用')
  activeSection.value = 'revision'
}

async function handleApplyDraft(revisionId: number) {
  await ppStore.applyDraftRevision(novelId, revisionId)
  ElMessage.success('草稿修订已应用')
  await store.fetchWritingRuns(novelId)
}

async function handleReviewRun(runId: number) {
  try {
    const result = await writingApi.reviewWritingRun(novelId, runId)
    if (result.decision) {
      ppStore.pendingDecisions.push(result.decision)
      activeSection.value = 'decision'
      ElMessage.info('审查发现需要处理的问题')
    } else {
      ElMessage.success('审查通过，无问题')
    }
  } catch {
    ElMessage.error('审查失败')
  }
}

// --- Phase 4 handlers ---

async function handleGenerateOptions(issueId: number) {
  revisionsStore.selectedIssueId = issueId
  await revisionsStore.generateOptions(novelId, issueId)
}

async function handleCreateCandidate(issueId: number) {
  revisionsStore.selectedIssueId = issueId
  try {
    await revisionsStore.createCandidate(novelId, issueId)
    ElMessage.success('候选修订已创建')
  } catch {
    ElMessage.error('创建候选修订失败')
  }
}

function handleIgnoreIssue(issueId: number) {
  ignoreIssueId.value = issueId
  ignoreReason.value = ''
  showIgnoreDialog.value = true
}

async function confirmIgnoreIssue() {
  if (!ignoreIssueId.value || !ignoreReason.value.trim()) return
  try {
    await revisionsStore.ignoreIssue(novelId, ignoreIssueId.value, { reason: ignoreReason.value.trim() })
    ElMessage.success('问题已忽略')
  } catch {
    ElMessage.error('忽略问题失败')
  }
  showIgnoreDialog.value = false
  ignoreIssueId.value = null
}

async function handleApplyCandidate(revisionId: number) {
  const candidate = revisionsStore.candidate
  const confirmExpanded = candidate?.expanded_scope ?? false
  try {
    await revisionsStore.applyRevision(novelId, revisionId, confirmExpanded)
    // Sync editor content after apply
    if (revisionsStore.currentVersion) {
      editorContent.value = revisionsStore.currentVersion.content
    }
    ElMessage.success('修订已应用')
  } catch {
    ElMessage.error('应用修订失败')
  }
}

async function handleRejectCandidate(revisionId: number) {
  try {
    await revisionsStore.rejectRevision(novelId, revisionId)
    ElMessage.info('修订已拒绝')
  } catch {
    ElMessage.error('拒绝修订失败')
  }
}

async function handleSaveManualRevision() {
  if (!activeRun.value || !editorChangeReason.value.trim()) return
  try {
    await revisionsStore.saveManualRevision(novelId, activeRun.value.id, {
      content: editorContent.value,
      change_reason: editorChangeReason.value.trim(),
      base_revision_sequence: revisionsStore.currentVersion?.revision_sequence ?? 0,
    })
    // Sync editor content with server-returned version
    if (revisionsStore.currentVersion) {
      editorContent.value = revisionsStore.currentVersion.content
    }
    editorChangeReason.value = ''
    ElMessage.success('手动编辑已保存')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleCreateVersion(payload: { basedOnVersionId: number; changeReason: string }) {
  if (!activeRun.value) return
  try {
    await revisionsStore.createVersion(novelId, activeRun.value.id, {
      based_on_version_id: payload.basedOnVersionId,
      change_reason: payload.changeReason,
    })
    if (revisionsStore.currentVersion) {
      editorContent.value = revisionsStore.currentVersion.content
    }
    ElMessage.success('新版本已创建')
  } catch {
    ElMessage.error('创建版本失败')
  }
}

async function handleRestoreVersion(payload: { versionId: number; changeReason: string }) {
  try {
    await revisionsStore.restoreVersion(novelId, payload.versionId, {
      base_revision_sequence: revisionsStore.currentVersion?.revision_sequence ?? 0,
      change_reason: payload.changeReason,
    })
    if (revisionsStore.currentVersion) {
      editorContent.value = revisionsStore.currentVersion.content
    }
    ElMessage.success('版本已恢复')
  } catch {
    ElMessage.error('恢复失败')
  }
}

function handleSelectVersion(versionId: number) {
  const version = revisionsStore.versions.find(v => v.id === versionId)
  if (version) {
    editorContent.value = version.content
  }
}

watch(() => ppStore.foundation, (f) => {
  if (f) {
    foundationOutline.value = f.outline
    foundationIntent.value = f.current_intent
    foundationStageGoal.value = f.stage_goal
  }
}, { immediate: true })

function editBlueprint(bp: NovelBlueprint) {
  editingBlueprintId.value = bp.id
  blueprintText.value = JSON.stringify(bp.content_json, null, 2)
  showBlueprintEditor.value = true
}

function editActiveBlueprint() {
  if (store.activeBlueprint) editBlueprint(store.activeBlueprint)
}

async function handleSaveBlueprint() {
  if (editingBlueprintId.value === null) return
  await saveBlueprint(editingBlueprintId.value)
}

async function saveBlueprint(bpId: number) {
  try {
    const parsed = JSON.parse(blueprintText.value)
    await store.updateBlueprint(novelId, bpId, { content_json: parsed })
    ElMessage.success('蓝图已保存')
    showBlueprintEditor.value = false
    editingBlueprintId.value = null
  } catch {
    ElMessage.error('JSON 格式错误')
  }
}

function getContextListLength(key: string) {
  const value = store.latestContext?.package_json[key]
  return Array.isArray(value) ? value.length : 0
}

// Source type label helper for internal revisions in timeline
const sourceTypeLabel: Record<string, string> = {
  planning_decision: '规划决策',
  review_issue: '审查问题',
  author_request: '作者请求',
  manual_edit: '手动编辑',
  restore: '恢复',
}
</script>

<template>
  <div class="writing">
    <NovelWorkspaceTabs :novel-id="novelId" />

    <div class="writing__steps">
      <!-- 1. Blueprint -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>1. 小说蓝图</span>
        </template>
        <div v-if="!store.activeBlueprint && !store.blueprints.length">
          <el-input
            v-model="authorInput"
            type="textarea"
            :rows="3"
            placeholder="输入小说构思，例如：一个关于权力与背叛的故事..."
          />
          <el-button type="primary" class="writing__btn" :loading="store.loading" @click="handleGenerateBlueprint">
            生成蓝图
          </el-button>
        </div>
        <div v-else-if="!store.activeBlueprint && latestDraftBlueprint">
          <el-alert type="info" :closable="false" title="蓝图已生成，请激活" />
          <pre class="writing__json">{{ blueprintText }}</pre>
          <el-button type="primary" size="small" @click="handleActivate(latestDraftBlueprint.id)">激活蓝图</el-button>
          <el-button size="small" @click="editBlueprint(latestDraftBlueprint)">编辑蓝图</el-button>
        </div>
        <div v-else>
          <el-alert type="success" :closable="false" title="蓝图已激活" />
          <pre class="writing__json">{{ blueprintText }}</pre>
          <el-button size="small" @click="editActiveBlueprint">编辑蓝图</el-button>
        </div>
        <div v-if="showBlueprintEditor" class="writing__blueprint-editor">
          <el-input v-model="blueprintText" type="textarea" :rows="12" />
          <div class="writing__actions">
            <el-button type="primary" size="small" @click="handleSaveBlueprint">保存蓝图</el-button>
            <el-button size="small" @click="showBlueprintEditor = false">取消</el-button>
          </div>
        </div>
      </el-card>

      <!-- 1.5. Author Foundation (Phase 3) -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>作者基础设定</span>
        </template>
        <AuthorFoundationPanel
          :foundation="ppStore.foundation"
          :loading="ppStore.loading"
          @save="handleSaveFoundation"
        />
      </el-card>

      <!-- 2. Chapter Plan -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>2. 下一章计划</span>
        </template>
        <div v-if="store.latestPlan">
          <p><strong>标题：</strong>{{ store.latestPlan.content_json.chapter_title }}</p>
          <p><strong>剧情任务：</strong>{{ store.latestPlan.content_json.plot_task }}</p>
          <p><strong>角色任务：</strong>{{ store.latestPlan.content_json.character_task }}</p>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.activeBlueprint"
          :loading="store.loading"
          @click="handleGeneratePlan"
        >
          生成下一章计划
        </el-button>
      </el-card>

      <!-- 2.5. Plot Unit Panel (Phase 3) -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>剧情单元规划</span>
        </template>
        <PlotUnitPanel
          :plot-units="ppStore.plotUnits"
          :active-plan="ppStore.activePlan"
          :loading="ppStore.loading"
          @create="handleCreatePlotUnit"
          @generate-plan="handleGeneratePlotPlan"
          @confirm-plan="handleConfirmPlan"
          @select-unit="handlePlotUnitSelect"
        />
      </el-card>

      <!-- 3. Chapter Brief -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>3. 章节任务书</span>
        </template>
        <div v-if="store.latestBrief">
          <p><strong>写作目标：</strong>{{ store.latestBrief.brief_json.writing_goal }}</p>
          <p><strong>场景数：</strong>{{ store.latestBrief.brief_json.scenes?.length || 0 }}</p>
          <p><strong>篇幅契约：</strong>{{ store.latestBrief.length_contract_json.target_words }} / {{ store.latestBrief.length_contract_json.min_words }} / {{ store.latestBrief.length_contract_json.max_words }} 字</p>
          <el-divider />
          <el-form label-width="80px" size="small">
            <el-form-item label="目标字数">
              <el-input-number v-model="editingTargetWords" :min="1000" :max="10000" />
            </el-form-item>
            <el-form-item label="最低字数">
              <el-input-number v-model="editingMinWords" :min="500" :max="5000" />
            </el-form-item>
            <el-form-item label="最高字数">
              <el-input-number v-model="editingMaxWords" :min="2000" :max="20000" />
            </el-form-item>
          </el-form>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestPlan || !ppStore.activePlan"
          :loading="store.loading"
          @click="handleGenerateBrief"
        >
          生成任务书
        </el-button>
      </el-card>

      <!-- 4. Context Package -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>4. 上下文包</span>
        </template>
        <div v-if="store.latestContext">
          <p><strong>角色数：</strong>{{ getContextListLength('characters') }}</p>
          <p><strong>设定数：</strong>{{ getContextListLength('world_settings') }}</p>
          <p><strong>蓝图摘要：</strong>已包含</p>
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestBrief || !ppStore.activePlan"
          :loading="store.loading"
          @click="handleGenerateContext"
        >
          生成上下文包
        </el-button>
      </el-card>

      <!-- 5. Draft -->
      <el-card class="writing__section" shadow="never">
        <template #header>
          <span>5. 生成草稿</span>
        </template>
        <div v-if="decisionRequiredRun" class="writing__decision-blocked">
          <el-alert type="warning" :closable="false" title="草稿需要决策" description="AI 检测到冲突，请先处理决策卡" />
          <el-button size="small" @click="activeSection = 'decision'">查看决策卡</el-button>
        </div>
        <div v-else-if="activeRun && activeRun.status === 'completed'">
          <div class="writing__stats">
            <span>字数：{{ activeRun.word_count }}</span>
            <span>目标：{{ activeRun.gate_result_json.target_words }}</span>
            <el-tag v-if="activeRun.gate_result_json.passed" type="success">通过</el-tag>
            <el-tag v-else type="danger">未通过</el-tag>
          </div>
          <div v-if="activeRun.gate_result_json.reasons.length" class="writing__reasons">
            <p v-for="r in activeRun.gate_result_json.reasons" :key="r" class="writing__reason">{{ r }}</p>
          </div>

          <!-- Phase 4: Editor buffer for current version content -->
          <div class="writing__editor-area">
            <el-input
              v-model="editorContent"
              type="textarea"
              :rows="10"
              :readonly="isReadOnly"
              data-testid="draft-editor"
            />
            <div v-if="!isReadOnly" class="writing__editor-actions">
              <el-input
                v-model="editorChangeReason"
                placeholder="编辑原因"
                size="small"
                class="writing__editor-reason"
                data-testid="change-reason-input"
              />
              <el-button
                type="primary"
                size="small"
                :disabled="!editorChangeReason.trim()"
                :loading="revisionsStore.loading"
                data-testid="save-manual-revision"
                @click="handleSaveManualRevision"
              >
                保存
              </el-button>
            </div>
          </div>

          <div class="writing__actions">
            <el-button type="primary" :disabled="isReadOnly" @click="handleAcceptRun(activeRun.id)">接受到章节</el-button>
            <el-button :disabled="isReadOnly" @click="handleDiscardRun(activeRun.id)">废弃</el-button>
            <el-button :disabled="isReadOnly" @click="handleReviewRun(activeRun.id)">审查</el-button>
          </div>
          <div v-if="pendingCountAfterAccept > 0" class="writing__extraction-info">
            <el-tag type="warning" class="writing__pending-tag">
              已提取 {{ pendingCountAfterAccept }} 条待确认记忆
            </el-tag>
            <el-button size="small" @click="$router.push(`/novels/${novelId}/pending`)">
              查看并确认
            </el-button>
          </div>
          <div v-else-if="extractionError" class="writing__extraction-info">
            <el-tag type="danger">记忆提取失败：{{ extractionError }}</el-tag>
          </div>
        </div>
        <div v-else-if="activeRun && activeRun.status === 'failed'">
          <el-alert type="error" :closable="false" title="生成失败" :description="activeRun.error_message || '字数未达标或内容为大纲体'" />
        </div>
        <el-button
          type="primary"
          class="writing__btn"
          :disabled="!store.latestContext || !!decisionRequiredRun || !ppStore.activePlan"
          :loading="store.loading"
          @click="handleGenerateDraft"
        >
          {{ store.writingRuns.length ? '重新生成草稿' : '生成草稿' }}
        </el-button>
      </el-card>

      <!-- 6. Decision Card (Phase 3) -->
      <el-card v-if="ppStore.pendingDecisions.length" class="writing__section" shadow="never">
        <template #header>
          <span>6. 决策卡</span>
        </template>
        <DecisionCard
          v-for="d in ppStore.pendingDecisions"
          :key="d.id"
          :decision="d"
          @choose="handleDecisionChoose"
        />
      </el-card>

      <!-- 7. Draft Revision Diff (Phase 3) -->
      <el-card v-if="ppStore.currentDraftRevision" class="writing__section" shadow="never">
        <template #header>
          <span>7. 草稿修订</span>
        </template>
        <DraftRevisionDiff
          :revision="ppStore.currentDraftRevision"
          :selected="true"
          @apply="handleApplyDraft"
        />
      </el-card>

      <!-- Phase 4: Version Timeline & Revision panels -->
      <el-card v-if="activeRun && (activeRun.status === 'completed' || activeRun.status === 'decision_required')" class="writing__section" shadow="never">
        <template #header>
          <span>版本与修订</span>
        </template>
        <div class="writing__phase4-grid">
          <!-- Left: Timeline + History -->
          <div class="writing__phase4-left">
            <DraftVersionTimeline
              :versions="revisionsStore.versions"
              :current-version="revisionsStore.currentVersion"
              @create-version="handleCreateVersion"
              @restore="handleRestoreVersion"
              @select-version="handleSelectVersion"
            >
              <template #internal-revisions>
                <div
                  v-for="rev in internalRevisions"
                  :key="rev.id"
                  class="writing__internal-rev"
                >
                  <span class="writing__internal-rev-seq">R{{ rev.sequence }}</span>
                  <span class="writing__internal-rev-source">{{ sourceTypeLabel[rev.source_type] || rev.source_type }}</span>
                  <span class="writing__internal-rev-reason">：{{ rev.reason }}</span>
                </div>
              </template>
            </DraftVersionTimeline>

            <el-divider />

            <RevisionHistoryPanel :revisions="revisionsStore.revisions" />
          </div>

          <!-- Right: Issue panel + Candidate panel -->
          <div class="writing__phase4-right">
            <ReviewIssuePanel
              :issues="revisionsStore.reviewIssues"
              :selected-issue-id="revisionsStore.selectedIssueId"
              :disabled="isReadOnly"
              @generate-options="handleGenerateOptions"
              @create-candidate="handleCreateCandidate"
              @ignore="handleIgnoreIssue"
            />

            <el-divider v-if="revisionsStore.candidate" />

            <RevisionCandidatePanel
              v-if="revisionsStore.candidate"
              :candidate="revisionsStore.candidate"
              @apply="handleApplyCandidate"
              @reject="handleRejectCandidate"
            />
          </div>
        </div>
      </el-card>

      <!-- Force accept dialog -->
      <el-dialog
        v-model="showForceAcceptDialog"
        title="强制接受"
        width="400px"
        :close-on-click-modal="false"
      >
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>
            存在阻断问题
          </template>
          仍有 {{ blockingIssues.length }} 个阻断问题未解决，强制接受需要说明原因。
        </el-alert>
        <el-input
          v-model="forceAcceptReason"
          type="textarea"
          :rows="2"
          placeholder="请说明强制接受的原因"
          class="writing__force-reason"
        />
        <template #footer>
          <el-button @click="showForceAcceptDialog = false">取消</el-button>
          <el-button
            type="danger"
            :disabled="!forceAcceptReason.trim()"
            @click="handleForceAccept"
          >
            强制接受
          </el-button>
        </template>
      </el-dialog>

      <!-- Ignore issue dialog -->
      <el-dialog
        v-model="showIgnoreDialog"
        title="忽略问题"
        width="400px"
        :close-on-click-modal="false"
      >
        <el-input
          v-model="ignoreReason"
          type="textarea"
          :rows="2"
          placeholder="请说明忽略此问题的原因"
        />
        <template #footer>
          <el-button @click="showIgnoreDialog = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="!ignoreReason.trim()"
            @click="confirmIgnoreIssue"
          >
            确认忽略
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.writing {
  max-width: 900px;
  margin: 0 auto;
}

.writing__steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.writing__section {
  .el-card__body {
    padding: 16px;
  }
}

.writing__btn {
  margin-top: 12px;
}

.writing__json {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}

.writing__stats {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}

.writing__editor-area {
  margin: 8px 0;
}

.writing__editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  align-items: center;
}

.writing__editor-reason {
  flex: 1;
}

.writing__draft {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  max-height: 400px;
  overflow: auto;
  margin: 8px 0;
}

.writing__actions {
  display: flex;
  gap: 8px;
}

.writing__reasons {
  margin: 4px 0;
}

.writing__reason {
  color: #e6a23c;
  font-size: 13px;
}

.writing__extraction-info {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.writing__pending-tag {
  cursor: default;
}

.writing__phase4-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.writing__phase4-left,
.writing__phase4-right {
  min-width: 0;
}

.writing__internal-rev {
  font-size: 12px;
  color: #606266;
  padding: 2px 0;
}

.writing__internal-rev-seq {
  font-weight: 500;
}

.writing__internal-rev-source {
  color: #909399;
}

.writing__internal-rev-reason {
  color: #909399;
}

.writing__force-reason {
  margin-top: 12px;
}
</style>
