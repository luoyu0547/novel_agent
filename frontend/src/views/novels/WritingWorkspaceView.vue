<script setup lang="ts">
import { useWritingStore } from '@/stores/writing'
import { usePlotPlanningStore } from '@/stores/plotPlanning'
import { usePendingMemoryStore } from '@/stores/pendingMemory'
import NovelWorkspaceTabs from '@/components/novels/NovelWorkspaceTabs.vue'
import PlotUnitPanel from '@/components/writing/PlotUnitPanel.vue'
import AuthorFoundationPanel from '@/components/writing/AuthorFoundationPanel.vue'
import DecisionCard from '@/components/writing/DecisionCard.vue'
import DraftRevisionDiff from '@/components/writing/DraftRevisionDiff.vue'
import type { WritingRun } from '@/types/writing'
import type { PlotUnitCreate, PlotUnit } from '@/types/plotPlanning'
import * as writingApi from '@/api/writing'

const route = useRoute()
const store = useWritingStore()
const ppStore = usePlotPlanningStore()
const pendingMemoryStore = usePendingMemoryStore()
const novelId = Number(route.params.id)

const authorInput = ref('')
const showBlueprintEditor = ref(false)
const blueprintText = ref('')
const activeSection = ref<'blueprint' | 'plan' | 'brief' | 'context' | 'draft' | 'decision' | 'revision'>('blueprint')

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
  try {
    const result = await store.acceptRun(novelId, runId)
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
      ppStore.pendingDecisions.push(result.decision as any)
      activeSection.value = 'decision'
      ElMessage.info('审查发现需要处理的问题')
    } else {
      ElMessage.success('审查通过，无问题')
    }
  } catch {
    ElMessage.error('审查失败')
  }
}

watch(() => ppStore.foundation, (f) => {
  if (f) {
    foundationOutline.value = f.outline
    foundationIntent.value = f.current_intent
    foundationStageGoal.value = f.stage_goal
  }
}, { immediate: true })

function editBlueprint(bp: any) {
  blueprintText.value = JSON.stringify(bp.content_json, null, 2)
  showBlueprintEditor.value = true
}

async function saveBlueprint(bpId: number) {
  try {
    const parsed = JSON.parse(blueprintText.value)
    await store.updateBlueprint(novelId, bpId, { content_json: parsed })
    ElMessage.success('蓝图已保存')
    showBlueprintEditor.value = false
  } catch {
    ElMessage.error('JSON 格式错误')
  }
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
          <el-button size="small" @click="editBlueprint(store.activeBlueprint)">编辑蓝图</el-button>
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
          <p><strong>角色数：</strong>{{ (store.latestContext.package_json as any).characters?.length || 0 }}</p>
          <p><strong>设定数：</strong>{{ (store.latestContext.package_json as any).world_settings?.length || 0 }}</p>
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
          <pre class="writing__draft">{{ activeRun.draft_content.slice(0, 500) }}...</pre>
          <div class="writing__actions">
            <el-button type="primary" @click="handleAcceptRun(activeRun.id)">接受到章节</el-button>
            <el-button @click="handleDiscardRun(activeRun.id)">废弃</el-button>
            <el-button @click="handleReviewRun(activeRun.id)">审查</el-button>
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
</style>
