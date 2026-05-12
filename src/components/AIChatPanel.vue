<template>
  <section class="panel ai-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">AI面试辅助</p>
        <h2>分析与追问</h2>
      </div>
      <span class="ai-status" :class="{ loading }">
        <span class="status-dot"></span>
        {{ loading ? 'AI分析中' : '待命' }}
      </span>
    </header>

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

    <div ref="messageListRef" class="message-list">
      <article
        v-for="message in messages"
        :key="message.id"
        class="chat-message"
        :class="message.type"
      >
        <div class="message-meta">
          <span>{{ message.type === 'ai' ? 'AI' : message.type === 'system' ? '系统' : '面试官' }}</span>
          <time>{{ message.time }}</time>
        </div>
        <p class="message-content">{{ message.content }}</p>
      </article>

      <div v-if="messages.length === 0" class="empty-state">
        等待面试片段。收到完整语句后会自动生成分析和追问。
      </div>
    </div>

    <div class="decision-board">
      <DoubtsList :doubts="doubts" />
      <QuestionList :questions="questions" :loading="loading" />
    </div>
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
  () => props.messages.length,
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
  gap: 10px;
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

.message-list {
  background: #fbfdff;
  border: 1px solid #edf2f7;
  border-radius: 10px;
  display: flex;
  flex: 0 1 32%;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: auto;
  padding: 8px;
}

.chat-message {
  border: 1px solid #e7ebf2;
  border-radius: 8px;
  padding: 9px 10px;
}

.chat-message.ai {
  background: #f6fffa;
  border-color: #cdeedc;
}

.chat-message.interviewer {
  background: #f7f5ff;
  border-color: #ddd7ff;
}

.message-meta {
  align-items: center;
  color: #7b8497;
  display: flex;
  font-size: 11px;
  font-weight: 700;
  justify-content: space-between;
  margin-bottom: 6px;
}

.chat-message p {
  color: #1f2937;
  font-size: 13px;
  line-height: 1.55;
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.empty-state {
  align-items: center;
  background: #f8fafc;
  border: 1px dashed #d7deeb;
  border-radius: 8px;
  color: #8c96aa;
  display: flex;
  flex: 1;
  font-size: 14px;
  justify-content: center;
  min-height: 180px;
  padding: 24px;
  text-align: center;
}

.decision-board {
  display: grid;
  flex: 1 1 360px;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-height: 0;
}

@media (max-width: 720px) {
  .analysis-stats,
  .decision-board {
    grid-template-columns: 1fr;
  }
}
</style>
