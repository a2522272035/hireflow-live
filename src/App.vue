<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark"></span>
        <div>
          <h1>HireFlow AI面试助手</h1>
          <p>{{ sessionSubtitle }} · 岗位：{{ displayJobTitle }}</p>
        </div>
      </div>

      <div class="session-meta">
        <ResumeUpload
          :key="sessionId"
          :resume="loadedResume"
          @resume-loaded="handleResumeLoaded"
          @resume-cleared="handleResumeCleared"
          @view-resume="resumeViewerOpen = true"
        />
        <span>面试官：李明</span>
        <strong>{{ elapsedTime }}</strong>
        <button
          type="button"
          class="test-button"
          :disabled="finishingInterview || recordingStatus === 'finalizing' || (!testModeRunning && recordingStatus === 'recording')"
          @click="toggleDemoInterview"
        >
          {{ demoButtonText }}
        </button>
        <button
          type="button"
          class="secondary-button"
          :disabled="finishingInterview || testModeRunning || recordingStatus === 'recording' || recordingStatus === 'finalizing'"
          @click="generateInstantDemoReport"
        >
          生成演示报告
        </button>
        <button type="button" class="danger-button" :disabled="!canFinishInterview" @click="finishInterview">
          {{ finishButtonText }}
        </button>
      </div>
    </header>

    <section v-if="workflowProgress.visible" class="progress-banner" aria-live="polite">
      <div class="progress-header">
        <div>
          <span>{{ workflowProgress.title }}</span>
          <p>{{ workflowProgress.detail }}</p>
        </div>
        <strong>{{ workflowProgress.percent }}%</strong>
      </div>
      <div class="progress-track">
        <span :style="{ width: `${workflowProgress.percent}%` }"></span>
      </div>
      <ol class="progress-steps">
        <li
          v-for="step in progressSteps"
          :key="step.key"
          :class="{ active: workflowProgress.step === step.key, done: step.order < workflowProgress.order }"
        >
          {{ step.label }}
        </li>
      </ol>
      <div class="progress-signal-grid">
        <span
          v-for="signal in progressSignals"
          :key="signal.key"
          :class="{ active: signal.active, done: signal.done }"
        >
          <i></i>{{ signal.label }}
        </span>
      </div>
    </section>

    <section class="workspace">
      <TranscriptPanel
        :recording-status="recordingStatus"
        :mic-status="micStatus"
        :asr-status="asrStatus"
        :vad-status="vadStatus"
        :semantic-status="semanticStatus"
        :partial-text="partialText"
        :current-text="currentText"
        :finals="finals"
        :mode="asrMode"
        @toggle-recording="toggleRecording"
        @set-mode="setMode"
      />

      <AIChatPanel
        :messages="messages"
        :analyses="analyses"
        :questions="questions"
        :doubts="doubts"
        :resume="loadedResume"
        :loading="aiLoading"
        @ask-question="sendQuestion"
      />
    </section>

    <ResumeViewerModal
      :open="resumeViewerOpen"
      :resume="loadedResume"
      @close="resumeViewerOpen = false"
    />
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AIChatPanel from './components/AIChatPanel.vue'
import TranscriptPanel from './components/TranscriptPanel.vue'
import ResumeUpload from './components/ResumeUpload.vue'
import ResumeViewerModal from './components/ResumeViewerModal.vue'
import { useAudioRecorder } from './composables/useAudioRecorder.js'
import { useAsrEvents } from './composables/useAsrEvents.js'
import mockInterviewScenario from './mockInterview.js'

const recordingStatus = ref('idle')
const startedAt = ref(Date.now())
const now = ref(Date.now())
const sessionId = ref(`interview-${Date.now()}`)
const finishingInterview = ref(false)
let clockTimer = null
let loadedResume = ref(null)
const resumeViewerOpen = ref(false)
const hasStartedInterview = ref(false)
const testModeRunning = ref(false)
const currentSessionDemo = ref(false)
const reportProgress = ref({
  visible: false,
  step: 'transcript',
  percent: 0,
  title: '',
  detail: ''
})
let suppressPersist = false
let demoTimers = []
const STORAGE_KEY = 'hireflow-live-current-session'
const progressSteps = [
  { key: 'transcript', label: '转写记录', order: 1 },
  { key: 'analysis', label: 'AI分析', order: 2 },
  { key: 'report', label: '报告归档', order: 3 },
  { key: 'done', label: '完成', order: 4 }
]
const progressStepOrder = Object.fromEntries(progressSteps.map((step) => [step.key, step.order]))
const pipelineSignals = [
  { key: 'audio', label: '音频缓冲' },
  { key: 'vad', label: '端点检测' },
  { key: 'asr', label: '语音转写' },
  { key: 'speaker', label: '角色判断' },
  { key: 'resume', label: '简历上下文' },
  { key: 'ai', label: 'AI片段评价' },
  { key: 'summary', label: '总评汇总' },
  { key: 'archive', label: 'PDF归档' }
]

const elapsedTime = computed(() => {
  if (!hasStartedInterview.value) return '00:00:00'
  const seconds = Math.floor((now.value - startedAt.value) / 1000)
  const hh = String(Math.floor(seconds / 3600)).padStart(2, '0')
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
})
const finishButtonText = computed(() => {
  if (finishingInterview.value || recordingStatus.value === 'finalizing') return '生成报告中...'
  if (!hasStartedInterview.value) return '等待开始'
  if (recordingStatus.value === 'recording') return '结束面试'
  return '生成报告'
})
const canFinishInterview = computed(() => {
  if (finishingInterview.value || recordingStatus.value === 'finalizing' || testModeRunning.value) return false
  return hasStartedInterview.value && ['idle', 'recording', 'stopped'].includes(recordingStatus.value)
})
const sessionSubtitle = computed(() => {
  if (testModeRunning.value) return '测试演示中'
  if (recordingStatus.value === 'recording') return '实时面试中'
  if (recordingStatus.value === 'finalizing') return '报告生成中'
  return '等待开始'
})
const displayJobTitle = computed(() => {
  const profile = buildResumeProfile(loadedResume.value)
  return profile.hasResume
    ? profile.targetRole || profile.position || '目标岗位'
    : '运营专员（平台运营方向）'
})
const demoButtonText = computed(() => testModeRunning.value ? '停止演示' : '演示测试')
const workflowProgress = computed(() => {
  if (reportProgress.value.visible) return normalizeProgress(reportProgress.value)
  if (aiLoading.value) {
    return normalizeProgress({
      visible: true,
      step: 'analysis',
      percent: 48,
      title: 'AI分析中',
      detail: '正在生成阶段评价、存疑点和追问建议，录音和转写不会被中断。'
    })
  }
  if (recordingStatus.value === 'recording') {
    const hasSpeech = Boolean(partialText.value || currentText.value)
    return normalizeProgress({
      visible: true,
      step: 'transcript',
      percent: hasSpeech ? 30 : 18,
      title: testModeRunning.value ? '模拟转写中' : hasSpeech ? '实时转写中' : '录音监听中',
      detail: hasSpeech
        ? '正在把当前语音片段写入左侧转写记录。'
        : '正在保持全程收音，等待下一段有效语音。'
    })
  }
  return normalizeProgress({ visible: false, step: 'transcript', percent: 0, title: '', detail: '' })
})
const progressSignals = computed(() => {
  if (!workflowProgress.value.visible) return []
  const activeIndex = Math.floor(now.value / 1000) % pipelineSignals.length
  const doneKeys = new Set()
  if (finals.value.length > 0) {
    doneKeys.add('audio')
    doneKeys.add('vad')
    doneKeys.add('asr')
  }
  if (finals.value.some((item) => item.speaker && item.speaker !== 'unknown')) doneKeys.add('speaker')
  if (loadedResume.value) doneKeys.add('resume')
  if (analyses.value.length > 0) doneKeys.add('ai')
  if (workflowProgress.value.order >= progressStepOrder.report) doneKeys.add('summary')
  if (workflowProgress.value.step === 'done') {
    pipelineSignals.forEach((item) => doneKeys.add(item.key))
  }
  return pipelineSignals.map((signal, index) => ({
    ...signal,
    active: index === activeIndex || (
      workflowProgress.value.step === 'analysis' && signal.key === 'ai'
    ) || (
      workflowProgress.value.step === 'report' && ['summary', 'archive'].includes(signal.key)
    ),
    done: doneKeys.has(signal.key)
  }))
})

const { micStatus, sendingAudio, start: startMic, stop: stopMic } = useAudioRecorder()

const {
  asrStatus, vadStatus, semanticStatus,
  partialText, currentText, finals,
  messages, analyses, questions, doubts, aiLoading,
  connect: connectEvents, disconnect: disconnectEvents,
  sendAudio, sendQuestion, switchMode, resetAsrState
} = useAsrEvents()

const asrMode = ref('fast')

function handleResumeLoaded(resume) {
  loadedResume.value = resume
  resumeViewerOpen.value = true
}

async function handleResumeCleared() {
  loadedResume.value = null
  resumeViewerOpen.value = false
  await fetch('/api/resume', { method: 'DELETE' }).catch(() => {})
}

async function setMode(mode) {
  asrMode.value = mode
  await switchMode(mode)
}

onMounted(() => {
  restoreSavedSession()
  clockTimer = window.setInterval(() => { now.value = Date.now() }, 1000)
})

onBeforeUnmount(() => {
  stopDemoInterview()
  stopRecording({ finalize: false })
  if (clockTimer) window.clearInterval(clockTimer)
})

watch(
  [finals, messages, analyses, loadedResume, recordingStatus],
  () => persistSession(),
  { deep: true }
)

async function toggleRecording() {
  if (recordingStatus.value === 'recording') {
    return
  } else {
    await startRecording()
  }
}

async function startRecording() {
  if (recordingStatus.value === 'finalizing' || recordingStatus.value === 'finished') return
  clearReportProgress()
  stopDemoInterview()
  currentSessionDemo.value = false
  let asrStarted = false
  asrStatus.value = '正在准备麦克风'
  try {
    if (!hasStartedInterview.value) {
      startedAt.value = Date.now()
      now.value = Date.now()
      hasStartedInterview.value = true
      persistSession()
    }
    await connectEvents()
    await startMic((pcm) => {
      if (asrStarted) sendAudio(pcm)
    })
    const response = await fetch('/start', { method: 'POST' })
    if (!response.ok) throw new Error(await response.text())
    asrStarted = true
    recordingStatus.value = 'recording'
    asrStatus.value = '录音中'
  } catch (error) {
    disconnectEvents()
    await stopMic()
    recordingStatus.value = 'idle'
    if (finals.value.length === 0 && messages.value.length === 0) {
      hasStartedInterview.value = false
    }
    asrStatus.value = `启动失败：${error.message}`
    console.error('[ASR] 启动失败:', error)
  }
}

async function stopRecording({ finalize = true } = {}) {
  if (currentSessionDemo.value && testModeRunning.value) {
    stopDemoInterview()
    if (finalize) persistSession({ endedAt: Date.now() })
    return
  }
  await stopMic()
  if (recordingStatus.value === 'recording') {
    await fetch('/stop', { method: 'POST' }).catch(() => {})
    await wait(900)
    recordingStatus.value = 'stopped'
    asrStatus.value = '已停止'
    vadStatus.value = '等待录音'
    semanticStatus.value = '等待触发'
  }
  disconnectEvents()
  if (finalize) persistSession({ endedAt: Date.now() })
}

async function finishInterview() {
  if (!canFinishInterview.value) return
  if (finishingInterview.value) return
  finishingInterview.value = true
  try {
    setReportProgress('transcript', 24, '整理转写记录', '正在停止录音并保存最后一段实时转写。')
    await stopRecording({ finalize: false })
    setReportProgress('analysis', aiLoading.value ? 46 : 62, '等待AI分析收尾', aiLoading.value ? '右侧仍有阶段分析在生成，完成后会进入报告汇总。' : '阶段分析已完成，准备汇总报告材料。')
    recordingStatus.value = 'finalizing'
    asrStatus.value = '正在生成报告'
    vadStatus.value = '面试已结束'
    semanticStatus.value = '整理报告中'
    await waitForAiSettled()
    setReportProgress('report', 74, '汇总最终评价', '正在汇总既有AI评价、简历信息和转写上下文。')
    const snapshot = currentSessionDemo.value
      ? buildInstantDemoSession(loadedResume.value, {
          sessionId: sessionId.value,
          startedAt: startedAt.value || Date.now()
        }).snapshot
      : buildSessionSnapshot({ endedAt: Date.now() })
    persistSession({ ...snapshot, recordingStatus: 'finalizing' })
    setReportProgress('report', 86, '报告归档中', '正在生成PDF、TXT并保存到面试时间戳文件夹。')
    const report = await saveFinalReport(snapshot)
    setReportProgress('done', 100, '报告已生成', '面试资料已归档完成。')
    persistCompletedSession(snapshot, report)
    const savedFiles = [
      report.folder_path ? `保存目录：${report.folder_path}` : '',
      `PDF报告：${report.pdf_path}`,
      report.audio_path ? `录音文件：${report.audio_path}` : '',
      report.transcript_path ? `角色转写文本：${report.transcript_path}` : '',
      report.realtime_transcript_path ? `实时原始转写：${report.realtime_transcript_path}` : '',
      report.diarization_path ? `豆包说话人识别结果：${report.diarization_path}` : '',
      report.diarization_error_path ? `说话人分离错误说明：${report.diarization_error_path}` : '',
      `说话人分离：${report.diarization_status === 'running' ? '后台处理中，完成后会在同一文件夹生成角色转写文件' : report.speaker_calibrated ? '已完成' : '未完成，已保存实时原始转写和错误说明'}`
    ].filter(Boolean).join('\n')
    window.alert(`面试文件已保存：\n${savedFiles}`)
    resetInterview()
  } catch (error) {
    recordingStatus.value = 'stopped'
    setReportProgress('report', 100, '报告生成失败', error.message || '请稍后重试。')
    asrStatus.value = `报告生成失败：${error.message}`
    console.error('[Report] 生成失败:', error)
  } finally {
    finishingInterview.value = false
  }
}

async function generateInstantDemoReport() {
  if (finishingInterview.value || testModeRunning.value || recordingStatus.value === 'recording') return
  finishingInterview.value = true
  const previousResume = loadedResume.value
  try {
    stopDemoInterview()
    setReportProgress('transcript', 35, '生成模拟转写', '正在基于真实简历生成演示问答和候选人回答。')
    const demoSession = buildInstantDemoSession(previousResume)
    loadDemoSessionToUi(demoSession)
    setReportProgress('analysis', 64, '生成模拟AI评价', '正在整理演示用阶段评价、存疑点和追问建议。')
    await wait(500)
    setReportProgress('report', 84, '演示报告归档中', '正在生成演示模式 PDF 和 TXT 文件。')
    const report = await saveFinalReport(demoSession.snapshot)
    setReportProgress('done', 100, '演示报告已生成', '测试报告已保存，可用于后续企业微信推送演示。')
    persistCompletedSession(demoSession.snapshot, report)
    const savedFiles = [
      '报告类型：演示模式',
      report.folder_path ? `保存目录：${report.folder_path}` : '',
      `PDF报告：${report.pdf_path}`,
      report.transcript_path ? `角色转写文本：${report.transcript_path}` : '',
      report.realtime_transcript_path ? `实时原始转写：${report.realtime_transcript_path}` : ''
    ].filter(Boolean).join('\n')
    window.alert(`演示报告已生成：\n${savedFiles}`)
  } catch (error) {
    recordingStatus.value = 'stopped'
    setReportProgress('report', 100, '演示报告生成失败', error.message || '请稍后重试。')
    asrStatus.value = `演示报告生成失败：${error.message}`
    console.error('[DemoReport] 生成失败:', error)
  } finally {
    finishingInterview.value = false
    loadedResume.value = previousResume
  }
}

function resetInterview() {
  stopDemoInterview()
  clearReportProgress()
  suppressPersist = true
  sessionId.value = `interview-${Date.now()}`
  startedAt.value = Date.now()
  now.value = Date.now()
  loadedResume.value = null
  resumeViewerOpen.value = false
  resetAsrState()
  hasStartedInterview.value = false
  testModeRunning.value = false
  currentSessionDemo.value = false
  recordingStatus.value = 'idle'
  window.localStorage.removeItem(STORAGE_KEY)
  window.setTimeout(() => {
    suppressPersist = false
    window.localStorage.removeItem(STORAGE_KEY)
  }, 0)
}

function persistCompletedSession(snapshot, report) {
  try {
    const completed = JSON.parse(window.localStorage.getItem('hireflow-live-completed-sessions') || '[]')
    completed.unshift({
      ...snapshot,
      recordingStatus: 'finished',
      report,
      completedAt: Date.now()
    })
    window.localStorage.setItem('hireflow-live-completed-sessions', JSON.stringify(completed.slice(0, 10)))
  } catch (error) {
    console.warn('[Session] 完成记录保存失败:', error)
  }
}

async function saveFinalReport(snapshot) {
  const response = await fetch('/api/final-report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot)
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function normalizeProgress(progress) {
  const percent = Math.max(0, Math.min(100, Math.round(Number(progress.percent) || 0)))
  const step = progress.step || 'transcript'
  return {
    ...progress,
    step,
    percent,
    order: progressStepOrder[step] || 0
  }
}

function setReportProgress(step, percent, title, detail) {
  reportProgress.value = {
    visible: true,
    step,
    percent,
    title,
    detail
  }
}

function clearReportProgress() {
  reportProgress.value = {
    visible: false,
    step: 'transcript',
    percent: 0,
    title: '',
    detail: ''
  }
}

function makeDemoId(prefix = 'demo') {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function scheduleDemo(delay, action) {
  const timer = window.setTimeout(() => {
    demoTimers = demoTimers.filter((item) => item !== timer)
    if (testModeRunning.value) action()
  }, delay)
  demoTimers.push(timer)
}

function stopDemoInterview() {
  demoTimers.forEach((timer) => window.clearTimeout(timer))
  demoTimers = []
  if (testModeRunning.value) {
    testModeRunning.value = false
    aiLoading.value = false
    partialText.value = ''
    currentText.value = ''
    if (recordingStatus.value === 'recording') {
      recordingStatus.value = finals.value.length > 0 ? 'stopped' : 'idle'
      asrStatus.value = finals.value.length > 0 ? '已停止' : '未开始'
      vadStatus.value = '等待录音'
      semanticStatus.value = '等待触发'
    }
  }
}

function toggleDemoInterview() {
  if (testModeRunning.value) {
    stopDemoInterview()
    persistSession({ endedAt: Date.now() })
    return
  }
  startDemoInterview()
}

function startDemoInterview() {
  if (recordingStatus.value === 'recording' || recordingStatus.value === 'finalizing' || finishingInterview.value) return
  stopDemoInterview()
  resetAsrState()
  sessionId.value = `demo-${Date.now()}`
  startedAt.value = Date.now()
  now.value = Date.now()
  hasStartedInterview.value = true
  currentSessionDemo.value = true
  testModeRunning.value = true
  recordingStatus.value = 'recording'
  asrStatus.value = '测试模式：模拟音频输入'
  vadStatus.value = '等待说话'
  semanticStatus.value = '等待触发'
  messages.value.push({
    id: makeDemoId('system'),
    type: 'system',
    content: '测试模式已启动：当前不会调用麦克风，会模拟面试官和候选人的实时语音转写、AI分析与追问。',
    time: formatClock()
  })
  persistSession()
  runDemoScript()
}

function runDemoScript() {
  const turns = buildDemoTurns().slice(0, 4)
  let delay = 900
  turns.forEach((item, index) => {
    delay = scheduleDemoSpeech({
      delay,
      speaker: 'interviewer',
      label: '面试官',
      text: item.question
    })
    delay = scheduleDemoSpeech({
      delay,
      speaker: 'candidate',
      label: '候选人',
      text: item.sampleAnswers.join(''),
      onDone: (entry) => addDemoAnalysis(item, entry, index)
    })
    delay += 950
  })
  scheduleDemo(delay + 1000, () => {
    testModeRunning.value = false
    recordingStatus.value = 'stopped'
    asrStatus.value = '已停止'
    vadStatus.value = '等待录音'
    semanticStatus.value = '等待触发'
    partialText.value = ''
    currentText.value = ''
    messages.value.push({
      id: makeDemoId('system'),
      type: 'system',
      content: '测试演示已完成，可以点击“生成报告”查看完整报告流程。',
      time: formatClock()
    })
    persistSession({ endedAt: Date.now() })
  })
}

function buildInstantDemoSession(resume = loadedResume.value, options = {}) {
  const profile = buildResumeProfile(resume)
  const turns = buildFullDemoTurns(resume)
  const createdAt = options.startedAt || Date.now()
  const demoSessionId = options.sessionId || `demo-report-${createdAt}`
  const demoFinals = []
  const demoAnalyses = []
  const demoMessages = [{
    id: makeDemoId('system'),
    type: 'system',
    content: '演示模式：本报告基于真实简历和模拟面试问答生成，用于流程演示。',
    time: formatClock(createdAt)
  }]

  turns.forEach((turn, index) => {
    const questionTime = formatClock(createdAt + index * 90000)
    const answerTime = formatClock(createdAt + index * 90000 + 18000)
    const questionEntry = createDemoFinalEntry({
      id: makeDemoId('line'),
      text: turn.question,
      speaker: 'interviewer',
      label: '面试官',
      time: questionTime
    })
    const answerEntry = createDemoFinalEntry({
      id: makeDemoId('line'),
      text: turn.sampleAnswers.join(''),
      speaker: 'candidate',
      label: '候选人',
      time: answerTime
    })
    const analysisRecord = createDemoAnalysisRecord(turn, answerEntry, index, formatClock(createdAt + index * 90000 + 30000))
    demoFinals.push(questionEntry, answerEntry)
    demoAnalyses.push(analysisRecord)
    demoMessages.push({
      id: makeDemoId('ai'),
      type: 'ai',
      content: buildDemoAnalysisMessage(analysisRecord),
      time: analysisRecord.time
    })
  })

  const endedAt = createdAt + Math.max(1, turns.length) * 90000
  const snapshot = {
    sessionId: demoSessionId,
    interviewer: '李明',
    jobTitle: profile.hasResume ? profile.targetRole : '运营专员（平台运营方向）',
    startedAt: createdAt,
    startedAtText: formatDateTime(createdAt),
    endedAt,
    endedAtText: formatDateTime(endedAt),
    elapsedTime: formatElapsed(endedAt - createdAt),
    demoMode: true,
    fullDemoReport: true,
    demoTurns: turns.length,
    resume,
    finals: demoFinals.map(normalizeTranscriptEntry),
    messages: demoMessages,
    analyses: demoAnalyses,
    recordingStatus: 'stopped',
    updatedAt: Date.now(),
    reportType: '演示模式'
  }
  return {
    snapshot,
    questions: (demoAnalyses.at(-1)?.questions || []).slice(0, 3).map((text) => ({ id: makeDemoId('question'), text })),
    doubts: (demoAnalyses.at(-1)?.doubts || []).slice(0, 5).map((text, index) => ({ id: makeDemoId('doubt'), text, index: index + 1 }))
  }
}

function loadDemoSessionToUi(demoSession) {
  const snapshot = demoSession.snapshot
  sessionId.value = snapshot.sessionId
  startedAt.value = snapshot.startedAt
  now.value = snapshot.endedAt
  currentSessionDemo.value = true
  hasStartedInterview.value = true
  recordingStatus.value = 'stopped'
  asrStatus.value = '演示报告已生成'
  vadStatus.value = '测试模式'
  semanticStatus.value = '模拟问答完成'
  partialText.value = ''
  currentText.value = ''
  finals.value = snapshot.finals
  messages.value = snapshot.messages
  analyses.value = snapshot.analyses
  questions.value = demoSession.questions
  doubts.value = demoSession.doubts
  aiLoading.value = false
  persistSession({ ...snapshot, recordingStatus: 'stopped' })
}

function createDemoFinalEntry({ id, text, speaker, label, time }) {
  return {
    id,
    text,
    speaker,
    speakerLabel: label,
    roleStatus: 'classified',
    roleSource: 'demo',
    roleConfidence: 1,
    roleReason: '测试模式预置角色',
    time,
    pending: false
  }
}

function buildFullDemoTurns(resume = loadedResume.value) {
  const profile = buildResumeProfile(resume)
  const turns = buildDemoTurns(resume)
  const jobName = profile.targetRole || profile.position || '目标岗位'
  const company = profile.company || '上一家公司'
  const skillsText = profile.skills.slice(0, 4).join('、') || '岗位相关技能'

  const extraTurns = [
    {
      id: 'demo-work-detail',
      question: `请再展开说一个你在${company}最能体现个人贡献的具体案例。`,
      expectedKeywords: [company, '个人贡献', '结果复盘', '协作边界'].filter(Boolean),
      sampleAnswers: [
        `我印象比较深的是在${company}处理过一次跨流程协作任务，时间比较紧，但需要保证结果准确。`,
        `我先把任务拆成资料确认、过程跟进、结果复核三个节点，再逐项确认责任人和截止时间。`,
        '最终这个事项按时完成，也沉淀了一套后续可以复用的检查清单，减少了同类问题重复沟通。'
      ]
    },
    {
      id: 'demo-pressure',
      question: '如果业务方临时调整需求，同时交付时间不变，你会怎么处理？',
      expectedKeywords: ['优先级', '沟通确认', '风险提示', '二次核验'],
      sampleAnswers: [
        '我会先确认调整后的目标是否影响关键交付，如果影响范围较大，会第一时间把风险和可选方案同步出来。',
        '接着按优先级处理必须完成的内容，对暂时无法确认的信息做标记，并保留沟通过程和判断依据。',
        '交付前我会做一次二次核验，确保关键数据和结论没有因为赶时间出现偏差。'
      ]
    },
    {
      id: 'demo-onboarding',
      question: `如果你入职这个${jobName}岗位，前三个月你会怎么开展工作？`,
      expectedKeywords: [jobName, skillsText, '熟悉流程', '稳定交付', '持续优化'].filter(Boolean),
      sampleAnswers: [
        '第一个月我会先熟悉业务流程、团队分工和历史资料，把岗位要求和交付标准对齐。',
        `第二个月会把已有经验和${skillsText}结合起来，稳定完成日常工作，并主动记录可优化的问题。`,
        '第三个月希望能在稳定交付的基础上承担一部分流程优化或专项任务，让团队看到更明确的结果。'
      ]
    }
  ]

  return [...turns, ...extraTurns]
}

function buildDemoTurns(resume = loadedResume.value) {
  const profile = buildResumeProfile(resume)
  if (!profile.hasResume) return mockInterviewScenario.questions

  const jobName = profile.targetRole || profile.position || '目标岗位'
  const skillsText = profile.skills.slice(0, 6).join('、') || '岗位相关技能'
  const latestExperience = profile.experiences[0] || {}
  const latestCompany = latestExperience.company || profile.company || '上一家公司'
  const latestPosition = latestExperience.position || profile.position || jobName
  const latestDescription = latestExperience.description || `${latestCompany}${latestPosition}相关工作`

  return [
    {
      id: 'resume-intro',
      question: `请结合你的简历，做一个简短自我介绍，并说明你为什么适合${jobName}。`,
      expectedKeywords: [profile.position, profile.workYear, profile.degree, profile.major].filter(Boolean),
      sampleAnswers: [
        `${profile.name ? `我叫${profile.name}，` : ''}${profile.workYear ? `有${profile.workYear}工作经验，` : ''}主要从事${profile.position || jobName}相关工作。`,
        profile.education ? `教育背景是${profile.education}，专业方向是${profile.major || '与岗位相关'}。` : '',
        `我比较熟悉${skillsText}，希望继续在${jobName}方向发挥经验。`
      ].filter(Boolean)
    },
    {
      id: 'resume-latest-job',
      question: `你在${latestCompany}做${latestPosition}时，最核心的工作内容是什么？`,
      expectedKeywords: [latestCompany, latestPosition, '职责边界', '结果'].filter(Boolean),
      sampleAnswers: [
        `这段经历里我主要负责${latestDescription}。`,
        `日常会跟进关键数据、流程规范和跨部门协作，确保工作按节点完成。`,
        '其中我个人承担了执行落地和问题复盘的部分，遇到异常会及时整理原因和改进方案。'
      ]
    },
    {
      id: 'resume-skill-depth',
      question: `简历里提到你熟悉${skillsText}，能不能举一个最能体现这些能力的项目或场景？`,
      expectedKeywords: profile.skills.slice(0, 4).length ? profile.skills.slice(0, 4) : ['项目背景', '执行过程', '结果数据'],
      sampleAnswers: [
        `可以。我之前在${latestCompany}处理过一个比较典型的场景，需要同时兼顾准确性、时效性和沟通成本。`,
        `我先梳理了流程和关键节点，再把${skillsText}这些能力用到实际处理中。`,
        '最后结果是工作交付更稳定，相关问题减少，也方便后续复盘和交接。'
      ]
    },
    {
      id: 'resume-risk-control',
      question: `如果这个岗位遇到时间紧、信息不完整的情况，你会怎么保证交付质量？`,
      expectedKeywords: ['优先级', '核验', '沟通', '复盘'],
      sampleAnswers: [
        '我会先确认目标和截止时间，把必须完成的关键事项排出来。然后对不完整的信息做标记，第一时间和相关人员确认。',
        '执行过程中会保留核验记录，重要结论会二次检查，避免因为赶时间造成错误。',
        '结束后我会复盘哪些环节可以标准化，减少下次同类问题的处理成本。'
      ]
    },
    {
      id: 'resume-career-plan',
      question: `你对自己接下来在${jobName}方向的发展有什么规划？`,
      expectedKeywords: ['岗位理解', '能力提升', '稳定性'],
      sampleAnswers: [
        `我希望继续在${jobName}方向深入，把已有经验沉淀成更稳定的方法。`,
        '短期先快速熟悉公司业务和流程，中长期希望能承担更复杂的项目和协作职责。'
      ]
    }
  ]
}

function buildResumeProfile(resume) {
  const source = resume && typeof resume === 'object' ? resume : {}
  const raw = source.raw_result || source.raw || {}
  const getText = (...keys) => {
    for (const key of keys) {
      const value = source[key] ?? raw[key]
      const text = stringifyResumeValue(value)
      if (text) return text
    }
    return ''
  }
  const experiences = normalizeResumeExperiences(source.experiences || source.work_experience || raw.job_exp_objs)
  const educationText = [getText('college'), getText('degree')].filter(Boolean).join(' · ')
  return {
    hasResume: Object.keys(source).length > 0,
    name: getText('name'),
    position: getText('work_position', 'current_position', 'expect_job') || '目标岗位',
    targetRole: getText('expect_job', 'work_position', 'current_position') || '目标岗位',
    company: getText('work_company', 'current_company'),
    workYear: getText('work_year_norm', 'work_year'),
    degree: getText('degree'),
    college: getText('college'),
    major: getText('major'),
    education: educationText,
    skills: normalizeResumeSkills(source.skills || source.skills_objs || raw.skills_objs),
    experiences
  }
}

function stringifyResumeValue(value) {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.map(stringifyResumeValue).filter(Boolean).join('、')
  if (typeof value === 'object') return stringifyResumeValue(value.text || value.name || value.value || '')
  return String(value).trim()
}

function normalizeResumeSkills(value) {
  if (!Array.isArray(value)) return []
  return [...new Set(value.map((item) => {
    if (typeof item === 'string') return item
    return item?.skills_name || item?.name || item?.text || ''
  }).map((item) => String(item).trim()).filter(Boolean))].slice(0, 12)
}

function normalizeResumeExperiences(value) {
  if (!Array.isArray(value)) return []
  return value.map((item) => ({
    company: stringifyResumeValue(item?.company || item?.company_name || item?.work_company),
    position: stringifyResumeValue(item?.title || item?.position || item?.job_name || item?.work_position),
    description: stringifyResumeValue(item?.description || item?.job_content || item?.work_content)
  })).filter((item) => item.company || item.position || item.description).slice(0, 4)
}

function scheduleDemoSpeech({ delay, speaker, label, text, onDone }) {
  const speechDuration = Math.min(3600, Math.max(1300, Math.floor(text.length * 28)))
  scheduleDemo(delay, () => {
    vadStatus.value = 'VAD 检测中'
    semanticStatus.value = '正在判断语义完整性...'
    asrStatus.value = '录音中'
    partialText.value = text.slice(0, Math.min(text.length, 20))
    currentText.value = partialText.value
  })
  scheduleDemo(delay + Math.floor(speechDuration * 0.45), () => {
    partialText.value = text.slice(0, Math.min(text.length, 58))
    currentText.value = partialText.value
  })
  scheduleDemo(delay + Math.floor(speechDuration * 0.72), () => {
    partialText.value = text.slice(0, Math.min(text.length, 92))
    currentText.value = partialText.value
  })
  scheduleDemo(delay + speechDuration, () => {
    const entry = {
      id: makeDemoId('line'),
      text,
      speaker,
      speakerLabel: label,
      roleStatus: 'classified',
      roleSource: 'demo',
      roleConfidence: 1,
      roleReason: '测试模式预置角色',
      time: formatClock(),
      pending: false
    }
    finals.value.push(entry)
    partialText.value = ''
    currentText.value = ''
    semanticStatus.value = '✓ 语义完整'
    vadStatus.value = '等待下一个语句'
    asrStatus.value = '✓ 已确认句子'
    if (onDone) onDone(entry)
  })
  return delay + speechDuration + 1200
}

function addDemoAnalysis(question, entry, index) {
  aiLoading.value = true
  messages.value.push({
    id: makeDemoId('ai-loading'),
    type: 'ai',
    content: '正在分析面试片段...',
    time: formatClock()
  })
  scheduleDemo(950, () => {
    const analysisRecord = createDemoAnalysisRecord(question, entry, index)
    const questionList = analysisRecord.questions || []
    const doubtsList = analysisRecord.doubts || []
    analyses.value.push(analysisRecord)
    messages.value[messages.value.length - 1] = {
      id: makeDemoId('ai'),
      type: 'ai',
      content: buildDemoAnalysisMessage(analysisRecord),
      time: formatClock()
    }
    questions.value = questionList.slice(0, 3).map((text) => ({
      id: makeDemoId('question'),
      text
    }))
    doubts.value = doubtsList.slice(0, 5).map((text, itemIndex) => ({
      id: makeDemoId('doubt'),
      text,
      index: itemIndex + 1
    }))
    aiLoading.value = false
    persistSession()
  })
}

function createDemoAnalysisRecord(question, entry, index, time = formatClock()) {
  const doubtsList = buildDemoDoubts(question, index)
  const questionList = buildDemoFollowUps(question, index)
  return {
    id: makeDemoId('analysis'),
    sourceId: entry.id,
    triggerType: 'demo_candidate_sentence_done',
    transcript: `面试官：${question.question}\n候选人：${entry.text}`,
    analysis: buildDemoAnalysisText(question, index),
    is_correct: true,
    doubts: doubtsList,
    questions: questionList,
    time
  }
}

function buildDemoAnalysisText(question, index) {
  const keywordText = question.expectedKeywords.join('、')
  const profile = buildResumeProfile(loadedResume.value)
  const resumeHint = profile.hasResume
    ? `本轮回答与简历中的${profile.position || profile.targetRole}经历有关，后续可继续核验其在${profile.company || '相关公司'}的个人贡献。`
    : '建议结合简历中的项目经历继续核实数据来源、协作角色和复盘能力。'
  const comments = [
    `回答覆盖了${keywordText}等关键点，信息结构比较清楚。`,
    '候选人能给出具体动作和结果数据，适合继续追问其个人贡献边界。',
    resumeHint
  ]
  return comments.slice(0, index === 0 ? 2 : 3).join('\n')
}

function buildDemoDoubts(question, index) {
  if (index === 0) return ['自我介绍中的项目规模和个人职责还需要进一步确认。']
  return [
    `需要核实“${question.expectedKeywords[0]}”相关经历是否由候选人主导。`,
    '数据结果较完整，但需要确认统计周期和口径。'
  ]
}

function buildDemoFollowUps(question, index) {
  const profile = buildResumeProfile(loadedResume.value)
  const firstKeyword = question.expectedKeywords[0] || '这段经历'
  const secondKeyword = question.expectedKeywords[1] || '结果'
  return [
    `你刚才提到${firstKeyword}，其中你个人最核心的贡献是什么？`,
    `这个项目里${secondKeyword}是如何衡量和复盘的？`,
    profile.hasResume && profile.company ? `你在${profile.company}的类似经历里，遇到过最大的风险点是什么？` : '如果重新做一次，你会优先优化哪个环节？'
  ].slice(0, index === 0 ? 2 : 3)
}

function buildDemoAnalysisMessage(result) {
  let content = '✅ 回答正确\n\n' + result.analysis
  if (result.doubts?.length) {
    content += '\n\n存疑点：\n' + result.doubts.map((item, index) => `${index + 1}. ${item}`).join('\n')
  }
  return content
}

function formatClock(value = Date.now()) {
  const date = new Date(value)
  return [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((item) => String(item).padStart(2, '0'))
    .join(':')
}

async function waitForAiSettled(timeout = 10000) {
  const started = Date.now()
  while (aiLoading.value && Date.now() - started < timeout) {
    const elapsed = Date.now() - started
    const percent = 46 + Math.min(18, Math.floor((elapsed / timeout) * 18))
    setReportProgress('analysis', percent, '等待AI分析收尾', `右侧仍有阶段分析在生成，最多等待 ${Math.ceil((timeout - elapsed) / 1000)} 秒。`)
    await wait(250)
  }
}

function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`
}

function formatElapsed(milliseconds) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000))
  const hh = String(Math.floor(seconds / 3600)).padStart(2, '0')
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

function buildSessionSnapshot(extra = {}) {
  const endedAt = extra.endedAt || null
  const resumeProfile = buildResumeProfile(loadedResume.value)
  return {
    sessionId: sessionId.value,
    interviewer: '李明',
    jobTitle: resumeProfile.hasResume
      ? resumeProfile.targetRole || resumeProfile.position || '目标岗位'
      : '运营专员（平台运营方向）',
    startedAt: startedAt.value,
    startedAtText: formatDateTime(startedAt.value),
    endedAt,
    endedAtText: formatDateTime(endedAt),
    elapsedTime: elapsedTime.value,
    demoMode: currentSessionDemo.value,
    resume: loadedResume.value,
    finals: finals.value.map(normalizeTranscriptEntry),
    messages: messages.value,
    analyses: analyses.value,
    recordingStatus: recordingStatus.value,
    updatedAt: Date.now()
  }
}

function persistSession(extra = {}) {
  if (suppressPersist) return
  try {
    const snapshot = extra.sessionId ? extra : buildSessionSnapshot(extra)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
  } catch (error) {
    console.warn('[Session] 保存失败:', error)
  }
}

function restoreSavedSession() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
    if (!saved) return
    sessionId.value = saved.sessionId || sessionId.value
    startedAt.value = saved.startedAt || startedAt.value
    loadedResume.value = saved.resume || null
    currentSessionDemo.value = Boolean(saved.demoMode)
    finals.value = Array.isArray(saved.finals) ? saved.finals.map(normalizeTranscriptEntry) : []
    messages.value = Array.isArray(saved.messages) ? saved.messages : []
    analyses.value = Array.isArray(saved.analyses) ? saved.analyses : []
    hasStartedInterview.value = finals.value.length > 0 || messages.value.length > 0
    if (hasStartedInterview.value) {
      const restoredStatus = saved.recordingStatus || 'stopped'
      recordingStatus.value = ['recording', 'finalizing'].includes(restoredStatus) ? 'stopped' : restoredStatus
    }
  } catch (error) {
    console.warn('[Session] 恢复失败:', error)
  }
}

function normalizeTranscriptEntry(item) {
  const hasCalibratedSpeaker = Boolean(item?.rawSpeaker)
  const hasAiSpeaker = item?.roleSource && item?.roleSource !== 'error'
  let speaker = 'unknown'
  if ((hasCalibratedSpeaker || hasAiSpeaker) && item?.speaker === 'interviewer') speaker = 'interviewer'
  if ((hasCalibratedSpeaker || hasAiSpeaker) && item?.speaker === 'candidate') speaker = 'candidate'
  return {
    ...item,
    speaker,
    speakerLabel: speaker === 'interviewer' ? '面试官' : speaker === 'candidate' ? '候选人' : '待识别',
    roleStatus: item?.roleStatus === 'classifying' ? 'failed' : item?.roleStatus
  }
}
</script>
