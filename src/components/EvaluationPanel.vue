<template>
  <section class="evaluation-panel">
    <header class="evaluation-head">
      <div>
        <span>面试官评价</span>
        <strong>完成面试后补充人工结论</strong>
      </div>
      <em v-if="status">{{ status }}</em>
    </header>

    <div class="evaluation-grid">
      <article
        v-for="item in scores"
        :key="item.key"
        class="evaluation-item"
      >
        <div class="dimension-title">
          <span>{{ item.label }}</span>
          <small v-if="item.aiSuggestedScore">AI建议 {{ item.aiSuggestedScore }} 星</small>
        </div>
        <div
          class="star-track"
          role="slider"
          :aria-label="item.label"
          :aria-valuenow="item.score"
          aria-valuemin="1"
          aria-valuemax="5"
          tabindex="0"
          @pointerdown="startDrag($event, item.key)"
          @pointermove="dragScore($event, item.key)"
          @pointerup="stopDrag"
          @pointercancel="stopDrag"
          @mouseleave="clearHover(item.key)"
          @keydown.left.prevent="stepScore(item.key, -1)"
          @keydown.right.prevent="stepScore(item.key, 1)"
        >
          <button
            v-for="star in 5"
            :key="star"
            type="button"
            class="star-button"
            :class="{ active: star <= displayScore(item), hover: star <= (hoverScores[item.key] || 0) }"
            @mouseenter="setHover(item.key, star)"
            @click.stop="setScore(item.key, star)"
          >
            ★
          </button>
        </div>
        <input
          :value="item.note || ''"
          type="text"
          placeholder="补充一句评价依据"
          @input="updateNote(item.key, $event.target.value)"
        />
      </article>
    </div>

    <div class="evaluation-bottom">
      <label>
        综合结论
        <select :value="value.recommendation" @change="updateField('recommendation', $event.target.value)">
          <option value="推荐进入下一轮">推荐进入下一轮</option>
          <option value="待复核">待复核</option>
          <option value="谨慎考虑">谨慎考虑</option>
          <option value="暂不推荐">暂不推荐</option>
        </select>
      </label>
      <label class="comment-field">
        面试官备注
        <textarea
          :value="value.comment"
          rows="3"
          placeholder="记录人工判断、需要复核的点或下一轮建议"
          @input="updateField('comment', $event.target.value)"
        ></textarea>
      </label>
    </div>

    <div class="evaluation-actions">
      <small>平均 {{ averageScore }} 星</small>
      <button type="button" class="primary-button" :disabled="saving" @click="$emit('save')">
        {{ saving ? '保存中...' : '保存评价' }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ recommendation: '推荐进入下一轮', comment: '', scores: [] })
  },
  saving: {
    type: Boolean,
    default: false
  },
  status: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'save'])

const hoverScores = ref({})
const draggingKey = ref('')

const value = computed(() => ({
  recommendation: props.modelValue?.recommendation || '推荐进入下一轮',
  comment: props.modelValue?.comment || '',
  scores: Array.isArray(props.modelValue?.scores) ? props.modelValue.scores : []
}))

const scores = computed(() => value.value.scores)
const averageScore = computed(() => {
  if (!scores.value.length) return '0.0'
  const total = scores.value.reduce((sum, item) => sum + Number(item.score || 0), 0)
  return (total / scores.value.length).toFixed(1)
})

function emitPatch(patch) {
  emit('update:modelValue', {
    ...value.value,
    ...patch
  })
}

function updateScores(updater) {
  emitPatch({
    scores: scores.value.map((item) => updater(item))
  })
}

function setScore(key, score) {
  const nextScore = Math.max(1, Math.min(5, Number(score) || 1))
  updateScores((item) => item.key === key ? { ...item, score: nextScore } : item)
}

function stepScore(key, delta) {
  const item = scores.value.find((entry) => entry.key === key)
  setScore(key, Number(item?.score || 3) + delta)
}

function updateNote(key, note) {
  updateScores((item) => item.key === key ? { ...item, note } : item)
}

function updateField(key, fieldValue) {
  emitPatch({ [key]: fieldValue })
}

function setHover(key, score) {
  hoverScores.value = { ...hoverScores.value, [key]: score }
}

function clearHover(key) {
  if (draggingKey.value === key) return
  const next = { ...hoverScores.value }
  delete next[key]
  hoverScores.value = next
}

function displayScore(item) {
  return hoverScores.value[item.key] || Number(item.score || 0)
}

function pointerScore(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const ratio = (event.clientX - rect.left) / Math.max(1, rect.width)
  return Math.max(1, Math.min(5, Math.ceil(ratio * 5)))
}

function startDrag(event, key) {
  draggingKey.value = key
  event.currentTarget.setPointerCapture?.(event.pointerId)
  const score = pointerScore(event)
  setHover(key, score)
  setScore(key, score)
}

function dragScore(event, key) {
  if (draggingKey.value !== key) return
  const score = pointerScore(event)
  setHover(key, score)
  setScore(key, score)
}

function stopDrag() {
  draggingKey.value = ''
}
</script>

<style scoped>
.evaluation-panel {
  background: #fffaf7;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  margin-top: 14px;
  padding: 12px;
}

.evaluation-head {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.evaluation-head span {
  color: #ea580c;
  display: block;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 3px;
}

.evaluation-head strong {
  color: #172033;
  display: block;
  font-size: 15px;
  line-height: 1.3;
}

.evaluation-head em {
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  color: #15803d;
  flex: 0 0 auto;
  font-size: 12px;
  font-style: normal;
  font-weight: 900;
  padding: 4px 8px;
}

.evaluation-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 12px;
}

.evaluation-item {
  background: #ffffff;
  border: 1px solid #ffedd5;
  border-radius: 8px;
  padding: 10px;
}

.dimension-title {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.dimension-title span {
  color: #172033;
  font-size: 13px;
  font-weight: 900;
}

.dimension-title small {
  color: #9a3412;
  font-size: 11px;
  font-weight: 800;
}

.star-track {
  align-items: center;
  display: flex;
  gap: 3px;
  margin-top: 8px;
  outline: none;
  touch-action: none;
  user-select: none;
}

.star-track:focus-visible {
  border-radius: 8px;
  box-shadow: 0 0 0 3px rgba(251, 146, 60, 0.2);
}

.star-button {
  background: transparent;
  border: 0;
  color: #d7dce6;
  cursor: pointer;
  font-size: 26px;
  line-height: 1;
  padding: 0 1px;
  transform: translateY(0) scale(1);
  transition: color 0.16s ease, transform 0.16s ease, filter 0.16s ease;
}

.star-button.active {
  color: #f59e0b;
  filter: drop-shadow(0 3px 7px rgba(245, 158, 11, 0.22));
}

.star-button.hover {
  transform: translateY(-2px) scale(1.12);
}

.evaluation-item input,
.evaluation-bottom select,
.evaluation-bottom textarea {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: #172033;
  margin-top: 8px;
  outline: none;
  padding: 8px 9px;
  width: 100%;
}

.evaluation-item input:focus,
.evaluation-bottom select:focus,
.evaluation-bottom textarea:focus {
  border-color: #f97316;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.12);
}

.evaluation-bottom {
  display: grid;
  gap: 10px;
  grid-template-columns: 170px 1fr;
  margin-top: 10px;
}

.evaluation-bottom label {
  color: #334155;
  display: flex;
  flex-direction: column;
  font-size: 12px;
  font-weight: 900;
}

.comment-field textarea {
  min-height: 74px;
  resize: vertical;
}

.evaluation-actions {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 10px;
}

.evaluation-actions small {
  color: #9a3412;
  font-size: 12px;
  font-weight: 900;
}

@media (max-width: 720px) {
  .evaluation-grid,
  .evaluation-bottom {
    grid-template-columns: 1fr;
  }
}
</style>
