<script setup lang="ts">
import { ref } from 'vue'
import type { PlotUnit, PlotUnitCreate, PlotPlanRevision } from '@/types/plotPlanning'

defineProps<{
  plotUnits: PlotUnit[]
  activePlan: PlotPlanRevision | null
  loading: boolean
}>()

const emit = defineEmits<{
  create: [data: PlotUnitCreate]
  generatePlan: [plotUnitId: number, authorInput: string]
  confirmPlan: [plotUnitId: number, revisionId: number]
  selectUnit: [plotUnit: PlotUnit]
}>()

const newUnit = ref<PlotUnitCreate>({
  title: '',
  scope_type: 'chapter',
  start_position: 1,
  end_position: 1,
  author_goal: '',
  start_state: '',
  end_state: '',
})
const showCreateForm = ref(false)
const planInput = ref('')
const generatingFor = ref<number | null>(null)
const selectedUnitId = ref<number | null>(null)

function handleCreate() {
  emit('create', { ...newUnit.value })
  newUnit.value = {
    title: '',
    scope_type: 'chapter',
    start_position: 1,
    end_position: 1,
    author_goal: '',
    start_state: '',
    end_state: '',
  }
  showCreateForm.value = false
}

function handleGenerate(unitId: number) {
  if (!planInput.value.trim()) return
  generatingFor.value = unitId
  emit('generatePlan', unitId, planInput.value)
  planInput.value = ''
}

function handleConfirm(unitId: number, revisionId: number) {
  emit('confirmPlan', unitId, revisionId)
}
</script>

<template>
  <div class="plot-unit-panel">
    <el-button size="small" @click="showCreateForm = !showCreateForm">
      {{ showCreateForm ? '取消' : '新建剧情单元' }}
    </el-button>

    <div v-if="showCreateForm" class="plot-unit-panel__form">
      <el-input v-model="newUnit.title" placeholder="剧情单元标题" size="small" />
      <el-input v-model="newUnit.author_goal" placeholder="作者目标" size="small" />
      <el-input v-model="newUnit.start_state" placeholder="起始状态" size="small" />
      <el-input v-model="newUnit.end_state" placeholder="目标状态" size="small" />
      <el-button type="primary" size="small" :loading="loading" @click="handleCreate">创建</el-button>
    </div>

    <div v-for="unit in plotUnits" :key="unit.id" class="plot-unit-panel__item">
      <div class="plot-unit-panel__item-header" @click="emit('selectUnit', unit)">
        <strong>{{ unit.title }}</strong>
        <el-tag size="small" :type="unit.status === 'active' ? 'success' : 'info'">
          {{ unit.status }}
        </el-tag>
      </div>
      <div class="plot-unit-panel__item-detail">
        <p>范围: {{ unit.scope_type }} ({{ unit.start_position }}-{{ unit.end_position }})</p>
        <p>目标: {{ unit.author_goal }}</p>
      </div>
      <div v-if="unit.id === selectedUnitId" class="plot-unit-panel__plan-section">
        <el-input
          v-model="planInput"
          type="textarea"
          :rows="2"
          placeholder="输入创作意图（可选）"
          size="small"
        />
        <el-button
          size="small"
          type="primary"
          :loading="loading && generatingFor === unit.id"
          @click="handleGenerate(unit.id)"
        >
          生成计划
        </el-button>
        <div v-if="activePlan && activePlan.plot_unit_id === unit.id && activePlan.status === 'draft'" class="plot-unit-panel__plan-actions">
          <el-button size="small" type="success" @click="handleConfirm(unit.id, activePlan.id)">
            确认计划
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>
