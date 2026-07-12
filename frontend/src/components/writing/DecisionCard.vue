<script setup lang="ts">
import { ref } from 'vue'
import type { PlanningDecision } from '@/types/plotPlanning'

const props = defineProps<{
  decision: PlanningDecision
}>()

const emit = defineEmits<{
  choose: [payload: { decisionId: number; optionIndex?: number; customIntent?: string }]
}>()

const customIntent = ref('')
const showDetails = ref(false)

function selectOption(index: number) {
  emit('choose', { decisionId: props.decision.id, optionIndex: index })
}

function submitCustom() {
  if (!customIntent.value.trim()) return
  emit('choose', { decisionId: props.decision.id, customIntent: customIntent.value.trim() })
  customIntent.value = ''
}
</script>

<template>
  <div class="decision-card">
    <div class="decision-card__header">
      <span class="decision-card__label">决策卡 #{{ decision.id }}</span>
      <el-tag size="small" type="warning">决策待处理</el-tag>
    </div>

    <div class="decision-card__conflict">
      <p class="decision-card__section-title">核心冲突</p>
      <p class="decision-card__conflict-text">{{ decision.conflict_summary }}</p>
    </div>

    <div class="decision-card__recommendation">
      <span class="decision-card__recommendation-label">AI 推荐</span>
      <el-tag size="small" type="danger">方案 {{ decision.recommended_index + 1 }}</el-tag>
    </div>

    <div class="decision-card__options">
      <p class="decision-card__section-title">可选方案</p>
      <div
        v-for="(opt, idx) in decision.options_json"
        :key="idx"
        class="decision-card__option"
        :class="{ 'decision-card__option--recommended': idx === decision.recommended_index }"
      >
        <div class="decision-card__option-header">
          <span class="decision-card__option-label">{{ opt.label }}</span>
          <el-tag v-if="idx === decision.recommended_index" size="small" type="danger">推荐</el-tag>
        </div>
        <p class="decision-card__option-action">{{ opt.action }}</p>
        <p class="decision-card__option-consequence">后果：{{ opt.consequence }}</p>
        <el-button size="small" type="primary" @click="selectOption(idx)">
          选择此方案
        </el-button>
      </div>
    </div>

    <div class="decision-card__custom">
      <p class="decision-card__section-title">补充因果</p>
      <el-input
        v-model="customIntent"
        type="textarea"
        :rows="2"
        placeholder="描述你想要的剧情走向..."
        size="small"
      />
      <el-button size="small" type="primary" :disabled="!customIntent.trim()" @click="submitCustom">
        调整未来目标
      </el-button>
    </div>

    <el-button size="small" text @click="showDetails = !showDetails">
      {{ showDetails ? '收起' : '展开' }}决策详情
    </el-button>
    <div v-if="showDetails" class="decision-card__details">
      <p><strong>推荐理由：</strong>{{ decision.recommendation_reason }}</p>
      <p><strong>影响范围：</strong>{{ JSON.stringify(decision.impact_scope_json) }}</p>
    </div>
  </div>
</template>
