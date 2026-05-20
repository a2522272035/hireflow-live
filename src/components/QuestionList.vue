<template>
  <section class="question-list">
    <div class="question-head">
      <span>快速追问建议</span>
      <small v-if="loading">生成中...</small>
      <small v-else>{{ questions.length }} 条</small>
    </div>

    <div v-if="questions.length" ref="questionTimelineRef" class="question-timeline">
      <article
        v-for="question in questions"
        :key="question.id"
        class="question-card"
      >
        <time v-if="question.time">{{ question.time }}</time>
        <p>{{ question.text }}</p>
      </article>
    </div>
    <div v-else class="empty-board">等待追问建议</div>
  </section>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  questions: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const questionTimelineRef = ref(null)

function scrollQuestionsToBottom() {
  const el = questionTimelineRef.value
  if (!el) return

  if (typeof el.scrollTo === 'function') {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    return
  }

  el.scrollTop = el.scrollHeight
}

watch(
  () => props.questions.map((item) => `${item.id ?? ''}:${item.time ?? ''}:${item.text ?? ''}`).join('|'),
  async () => {
    await nextTick()
    scrollQuestionsToBottom()
  },
  { flush: 'post', immediate: true }
)

</script>

<style scoped>
.question-list {
  background: #f7fdf9;
  border: 1px solid #cfeedd;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  padding: 10px;
}

.question-head {
  align-items: center;
  color: #4653ff;
  display: flex;
  font-size: 13px;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 8px;
}

.question-head small {
  color: #8c96aa;
  font-weight: 600;
}

.question-timeline {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.question-card {
  background: #ffffff;
  border: 1px solid #bdebd0;
  border-radius: 8px;
  color: #15734a;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.35;
  min-width: 0;
  overflow-wrap: anywhere;
  padding: 9px 10px;
  text-align: left;
}

.question-card time {
  color: #16a34a;
  display: block;
  font-size: 11px;
  font-weight: 900;
  margin-bottom: 5px;
}

.question-card p {
  margin: 0;
}

.empty-board {
  align-items: center;
  border: 1px dashed #bdebd0;
  border-radius: 8px;
  color: #7b8f84;
  display: flex;
  flex: 1;
  font-size: 13px;
  font-weight: 700;
  justify-content: center;
  min-height: 140px;
}
</style>
