<template>
  <section class="panel ai-panel">
    <div v-if="showWorkbench" class="ai-workbench" :class="{ loading }">
      <div v-if="resumeTags.length" class="resume-hit-strip">
        <strong>简历命中</strong>
        <span v-for="tag in resumeTags" :key="tag">{{ tag }}</span>
      </div>

      <div v-if="analysisStats.length" class="analysis-stats">
        <div v-for="metric in analysisStats" :key="metric.label" class="stat-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </div>
      </div>
    </div>

    <div ref="messageListRef" class="exam-sheet" :class="{ empty: examItems.length === 0 }">
      <section v-if="examItems.length" class="exam-paper">
        <article
          v-for="(item, index) in examItems"
          :key="item.id"
          class="exam-item"
        >
          <header class="problem-head">
            <div>
              <span>第 {{ index + 1 }} 题</span>
              <time>{{ item.time }}</time>
            </div>
            <strong>{{ item.partCount > 1 ? `面试官题目 · 已合并 ${item.partCount} 句` : '面试官题目' }}</strong>
          </header>
          <p class="problem-text">{{ item.question }}</p>

          <section class="answer-block">
            <div class="answer-head">
              <span>面试者作答</span>
              <small>{{ item.answers.length }} 段回答</small>
            </div>
            <div v-if="item.answers.length" class="answer-lines">
              <p v-for="answer in item.answers" :key="answer.id">{{ answer.text }}</p>
            </div>
            <div v-else class="answer-empty">等待面试者作答...</div>
          </section>

          <section v-if="item.analysis" class="marking-block">
            <div class="marking-head">
              <span>AI 批注</span>
              <small>{{ item.analysis.time }}</small>
            </div>
            <p>{{ item.analysis.analysis }}</p>
            <ul v-if="item.analysis.doubts?.length">
              <li v-for="doubt in item.analysis.doubts" :key="doubt">{{ doubt }}</li>
            </ul>
          </section>
        </article>
      </section>

      <section v-else class="exam-empty">
        <strong>等待第一道面试题</strong>
        <p>腾讯说话人分离识别到面试官发问后，会在这里形成题目；候选人的回答会自动排在题目下面。</p>
      </section>
    </div>

    <section class="exam-side-notes">
      <div class="note-panel">
        <DoubtsList :doubts="doubts" />
      </div>
      <div class="note-panel">
        <QuestionList :questions="questions" :loading="loading" />
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import QuestionList from './QuestionList.vue'
import DoubtsList from './DoubtsList.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  analyses: {
    type: Array,
    default: () => []
  },
  questions: {
    type: Array,
    default: () => []
  },
  interviewerQuestions: {
    type: Array,
    default: () => []
  },
  interviewTurns: {
    type: Array,
    default: () => []
  },
  doubts: {
    type: Array,
    default: () => []
  },
  resume: {
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const messageListRef = ref(null)

const resumeTags = computed(() => {
  const resume = props.resume && typeof props.resume === 'object' ? props.resume : {}
  const raw = resume.raw_result || resume.raw || {}
  const tags = [
    readText(resume, raw, 'name'),
    readText(resume, raw, 'work_position', 'current_position', 'expect_job'),
    readText(resume, raw, 'work_year_norm', 'work_year'),
    readText(resume, raw, 'degree'),
    readText(resume, raw, 'college'),
    readText(resume, raw, 'major'),
    ...readSkills(resume.skills || resume.skills_objs || raw.skills_objs).slice(0, 4)
  ]
  return [...new Set(tags.map((item) => String(item || '').trim()).filter(Boolean))].slice(0, 8)
})

const showWorkbench = computed(() => resumeTags.value.length > 0 || props.analyses.length > 0 || props.questions.length > 0 || props.doubts.length > 0 || props.loading)

const interviewerMessages = computed(() => props.messages.filter((message) => message.type === 'interviewer'))
const aiAnalyses = computed(() => props.analyses)

const examItems = computed(() => {
  if (props.interviewTurns.length > 0) {
    return props.interviewTurns
      .filter((turn) => turn?.question || turn?.answers?.length)
      .map((turn, index) => {
        const answers = Array.isArray(turn.answers)
          ? turn.answers
              .map((answer) => ({
                id: answer.id || answer.sourceId || `${turn.id}-answer-${index}`,
                text: answer.text || '',
                time: answer.time || ''
              }))
              .filter((answer) => answer.text)
          : []
        const latestAnalysis = aiAnalyses.value
          .filter((analysis) => {
            if (analysis.turnId && analysis.turnId === turn.id) return true
            return answers.some((answer) => analysis.answerId === answer.id || analysis.sourceId === answer.id)
          })
          .at(-1)

        return {
          id: turn.id || `turn-${index}`,
          question: turn.question || '未匹配到面试官题目',
          time: turn.time || '',
          partCount: turn.questionParts?.length || 1,
          answers,
          analysis: latestAnalysis || null
        }
      })
  }

  const questions = props.interviewerQuestions.length
    ? props.interviewerQuestions
    : interviewerMessages.value.map((message) => ({
      id: message.id,
      text: message.content,
      time: message.time
    }))

  if (questions.length === 0) return []

  return questions.map((question, index) => {
    const nextQuestion = questions[index + 1]
    const answers = aiAnalyses.value
      .filter((analysis) => {
        const time = analysis.time || ''
        if (!question.time || !time) return index === questions.length - 1
        if (time < question.time) return false
        if (nextQuestion?.time && time >= nextQuestion.time) return false
        return true
      })
      .map((analysis) => ({
        id: analysis.id,
        text: analysis.transcript || analysis.analysis || '',
        time: analysis.time
      }))
      .filter((answer) => answer.text)

    const latestAnalysis = aiAnalyses.value
      .filter((analysis) => answers.some((answer) => answer.id === analysis.id))
      .at(-1)

    return {
      id: question.id,
      question: question.text,
      time: question.time,
      partCount: question.partCount || 1,
      answers,
      analysis: latestAnalysis || null
    }
  })
})

const analysisStats = computed(() => {
  const stats = []
  if (resumeTags.value.length) {
    stats.push({
      label: '简历上下文',
      value: `${resumeTags.value.length} 项`
    })
  }
  if (props.analyses.length > 0) {
    stats.push({
      label: '已分析片段',
      value: `${props.analyses.length} 段`
    })
  }
  if (props.doubts.length > 0) {
    stats.push({
      label: '存疑条目',
      value: `${props.doubts.length} 条`
    })
  }
  if (props.questions.length > 0) {
    stats.push({
      label: '追问建议',
      value: `${props.questions.length} 条`
    })
  }
  return stats
})

function readText(source, raw, ...keys) {
  for (const key of keys) {
    const value = source[key] ?? raw[key]
    const text = stringifyValue(value)
    if (text) return text
  }
  return ''
}

function stringifyValue(value) {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(stringifyValue).filter(Boolean).join('、')
  if (typeof value === 'object') return stringifyValue(value.text || value.name || value.value || value.skills_name || '')
  return String(value).trim()
}

function readSkills(value) {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return item
    return item?.skills_name || item?.name || item?.text || ''
  }).map((item) => String(item).trim()).filter(Boolean)
}

watch(
  () => [props.messages.length, props.analyses.length, props.interviewerQuestions.length, props.interviewTurns.length],
  async () => {
    await nextTick()
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.ai-panel {
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

.ai-status {
  align-items: center;
  background: #f2f5fa;
  border-radius: 999px;
  color: #647086;
  display: inline-flex;
  font-size: 13px;
  font-weight: 700;
  gap: 8px;
  padding: 8px 12px;
}

.panel-actions {
  align-items: center;
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.speaker-test-button {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  color: #1d4ed8;
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
  padding: 8px 11px;
}

.speaker-test-button:hover {
  background: #dbeafe;
}

.ai-status.loading {
  background: #fff7e6;
  color: #b06500;
}

.status-dot {
  background: #8c96aa;
  border-radius: 50%;
  height: 8px;
  width: 8px;
}

.ai-status.loading .status-dot {
  background: #f5a524;
}

.ai-workbench {
  background: #f8fafc;
  border: 1px solid #dce8f8;
  border-radius: 10px;
  flex: 0 0 auto;
  padding: 8px;
}

.resume-hit-strip,
.analysis-stats {
  position: relative;
}

.resume-hit-strip {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  max-height: 26px;
  overflow: hidden;
}

.resume-hit-strip strong {
  color: #475569;
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 900;
}

.resume-hit-strip span {
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  color: #047857;
  font-size: 11px;
  font-weight: 800;
  max-width: 130px;
  overflow: hidden;
  padding: 3px 7px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.analysis-stats {
  display: grid;
  gap: 6px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 8px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  min-width: 0;
  padding: 7px 8px;
}

.stat-card span {
  color: #64748b;
  display: block;
  font-size: 11px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-card strong {
  color: #1d4ed8;
  display: block;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.25;
  margin-top: 3px;
}

.exam-sheet {
  background: #fffdf8;
  border: 1px solid #eadfcb;
  border-radius: 8px;
  flex: 1 1 180px;
  min-height: 0;
  overflow: auto;
  padding: 14px;
}

.exam-sheet.empty {
  flex: 0 0 auto;
  overflow: hidden;
  padding: 10px 12px;
}

.exam-paper {
  display: grid;
  gap: 14px;
}

.exam-item {
  background:
    linear-gradient(#fffaf0 31px, rgba(148, 163, 184, 0.18) 32px),
    #fffaf0;
  background-size: 100% 32px;
  border: 1px solid #ead7b8;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  box-shadow: 0 8px 22px rgba(120, 80, 20, 0.06);
  padding: 14px 16px 16px;
}

.problem-head,
.answer-head,
.marking-head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.problem-head {
  border-bottom: 1px solid #ead7b8;
  margin-bottom: 10px;
  padding-bottom: 8px;
}

.problem-head div {
  align-items: center;
  display: flex;
  gap: 8px;
}

.problem-head span {
  background: #1d4ed8;
  border-radius: 6px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 900;
  padding: 3px 8px;
}

.problem-head strong {
  color: #92400e;
  font-size: 12px;
  font-weight: 900;
}

.problem-head time,
.answer-head small,
.marking-head small {
  color: #8a6a3d;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.problem-text {
  color: #111827;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.65;
  margin: 0 0 12px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.answer-block {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #e8dcc5;
  border-radius: 8px;
  padding: 10px 12px;
}

.answer-head span,
.marking-head span {
  color: #334155;
  font-size: 12px;
  font-weight: 900;
}

.answer-lines {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.answer-lines p {
  color: #172033;
  font-size: 14px;
  line-height: 1.75;
  margin: 0;
  overflow-wrap: anywhere;
  padding-left: 16px;
  position: relative;
}

.answer-lines p::before {
  background: #22c55e;
  border-radius: 50%;
  content: "";
  height: 6px;
  left: 0;
  position: absolute;
  top: 10px;
  width: 6px;
}

.answer-empty {
  align-items: center;
  background: #ffffff;
  border: 1px dashed #d8c8aa;
  border-radius: 8px;
  color: #9a7a4c;
  display: flex;
  font-size: 13px;
  justify-content: center;
  margin-top: 8px;
  min-height: 54px;
}

.marking-block {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  margin-top: 10px;
  padding: 10px 12px;
}

.marking-block p {
  color: #14532d;
  font-size: 13px;
  line-height: 1.65;
  margin: 8px 0 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.marking-block ul {
  color: #166534;
  font-size: 13px;
  line-height: 1.55;
  margin: 8px 0 0;
  padding-left: 18px;
}

.exam-empty {
  align-items: center;
  background: #fffaf0;
  border: 1px dashed #d8c8aa;
  border-radius: 8px;
  color: #7c6a4d;
  display: flex;
  gap: 10px;
  justify-content: flex-start;
  min-height: 0;
  padding: 11px 12px;
  text-align: left;
}

.exam-empty strong {
  color: #334155;
  flex: 0 0 auto;
  font-size: 15px;
  white-space: nowrap;
}

.exam-empty p {
  font-size: 13px;
  line-height: 1.45;
  margin: 0;
  max-width: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.exam-side-notes {
  display: grid;
  flex: 1 1 clamp(420px, 46vh, 560px);
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-height: 360px;
}

.note-panel {
  height: 100%;
  min-height: 0;
}

.note-panel > * {
  height: 100%;
}

@media (max-width: 720px) {
  .analysis-stats,
  .exam-side-notes {
    grid-template-columns: 1fr;
  }
}
</style>
