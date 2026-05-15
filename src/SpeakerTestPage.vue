<template>
  <main class="speaker-test-page">
    <header class="test-topbar">
      <div>
        <p class="eyebrow">语音测试模式</p>
        <h1>实时说话人分离测试</h1>
        <span>原始说话人 ID 会映射为“说话人 1”到“说话人 N”，用于测试模型能否稳定区分多人。</span>
      </div>
      <button
        type="button"
        class="record-button"
        :class="{ active: recording }"
        :disabled="busy"
        @click="toggleRecording"
      >
        {{ recording ? '停止采集' : busy ? '准备中...' : '开始采集' }}
      </button>
    </header>

    <section class="test-status-grid">
      <div class="status-card">
        <span>采集状态</span>
        <strong>{{ recording ? '实时采集中' : busy ? '正在准备' : '未开始' }}</strong>
      </div>
      <div class="status-card">
        <span>麦克风</span>
        <strong>{{ micStatus }}</strong>
      </div>
      <div class="status-card">
        <span>ASR</span>
        <strong>{{ asrStatus }}</strong>
      </div>
      <div class="status-card">
        <span>识别到说话人</span>
        <strong>{{ speakerList.length }} 个</strong>
      </div>
    </section>

    <section class="meter-panel">
      <div>
        <span>输入音量</span>
        <strong>{{ Math.round(volumeLevel * 100) }}%</strong>
      </div>
      <div class="meter-track">
        <i :style="{ width: `${Math.round(volumeLevel * 100)}%` }"></i>
      </div>
    </section>

    <section class="test-workspace">
      <section class="live-panel">
        <header>
          <div>
            <p class="eyebrow">实时转写</p>
            <h2>采集结果</h2>
          </div>
          <button type="button" class="secondary-button" :disabled="recording" @click="clearResults">
            清空
          </button>
        </header>

        <div ref="transcriptRef" class="transcript-list">
          <article
            v-for="item in finals"
            :key="item.id"
            class="transcript-item"
            :style="{ '--speaker-color': item.color }"
          >
            <time>{{ item.time }}</time>
            <div>
              <span class="speaker-pill">{{ item.label }}</span>
              <small v-if="item.rawSpeaker">原始ID：{{ item.rawSpeaker }}</small>
              <p>{{ item.text }}</p>
            </div>
          </article>

          <div v-if="!finals.length" class="empty-board">
            点击开始采集后，让两个人交替说话，观察右侧是否能稳定拆成不同说话人。
          </div>
        </div>

        <div class="partial-strip" :class="{ active: partialText }">
          <span>{{ partialLabel || '实时片段' }}</span>
          <strong>{{ partialText || '等待声音输入...' }}</strong>
        </div>
      </section>

      <aside class="speaker-panel">
        <header>
          <p class="eyebrow">说话人统计</p>
          <h2>分辨能力观察</h2>
        </header>

        <div v-if="speakerList.length" class="speaker-list">
          <article
            v-for="speaker in speakerList"
            :key="speaker.raw"
            class="speaker-card"
            :style="{ '--speaker-color': speaker.color }"
          >
            <div>
              <strong>{{ speaker.label }}</strong>
              <small>{{ speaker.raw ? `原始ID：${speaker.raw}` : '原始ID：未返回' }}</small>
            </div>
            <dl>
              <div>
                <dt>句数</dt>
                <dd>{{ speaker.count }}</dd>
              </div>
              <div>
                <dt>字数</dt>
                <dd>{{ speaker.chars }}</dd>
              </div>
            </dl>
          </article>
        </div>

        <div v-else class="empty-board compact">
          暂未识别到说话人
        </div>

        <section class="test-notes">
          <strong>测试建议</strong>
          <p>两个人交替说 3 到 5 轮，尽量保持正常面试距离。重点看同一个人是否始终落在同一个“说话人 N”下。</p>
          <p>如果两个人被混成同一个编号，说明当前麦克风、距离、环境噪声或模型分离能力不适合直接做身份区分。</p>
        </section>
      </aside>
    </section>

    <p v-if="errorText" class="error-banner">{{ errorText }}</p>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAudioRecorder } from './composables/useAudioRecorder.js'

const speakerColors = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2', '#be185d', '#475569']

const { micStatus, volumeLevel, start: startMic, stop: stopMic } = useAudioRecorder()

const recording = ref(false)
const busy = ref(false)
const asrStatus = ref('未连接')
const partialText = ref('')
const partialLabel = ref('')
const finals = ref([])
const speakerRecords = ref([])
const errorText = ref('')
const transcriptRef = ref(null)

let socket = null
let upstreamStarted = false
let speakerIndex = 0
const speakerMap = new Map()
const seenFinals = new Set()

const speakerList = computed(() => speakerRecords.value)

onMounted(() => {
  document.title = '说话人分离测试 - HireFlow'
})

onBeforeUnmount(() => {
  stopRecording()
})

function wsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const isLocalHost = ['127.0.0.1', 'localhost'].includes(window.location.hostname)
  return isLocalHost
    ? `${protocol}//${window.location.hostname}:8771`
    : `${protocol}//${window.location.host}/ws`
}

function formatTime() {
  const now = new Date()
  return [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((item) => String(item).padStart(2, '0'))
    .join(':')
}

function rawSpeakerFromEvent(event) {
  return String(event.rawSpeaker || event.speakerId || event.speaker_id || event.raw_speaker || '').trim()
}

function ensureSpeaker(rawValue) {
  const raw = String(rawValue || '').trim()
  if (!raw) return null
  if (speakerMap.has(raw)) return speakerMap.get(raw)

  speakerIndex += 1
  const record = {
    raw,
    label: `说话人 ${speakerIndex}`,
    color: speakerColors[(speakerIndex - 1) % speakerColors.length],
    count: 0,
    chars: 0
  }
  speakerMap.set(raw, record)
  speakerRecords.value = [...speakerRecords.value, record]
  return record
}

function updateSpeakerStats(raw, text) {
  const record = ensureSpeaker(raw)
  if (!record) return null
  record.count += 1
  record.chars += String(text || '').replace(/\s+/g, '').length
  speakerRecords.value = speakerRecords.value.map((item) => item.raw === raw ? { ...record } : item)
  return record
}

function connectEvents() {
  if (socket && socket.readyState === WebSocket.OPEN) return Promise.resolve()
  if (socket) {
    socket.close()
    socket = null
  }

  return new Promise((resolve, reject) => {
    const current = new WebSocket(wsUrl())
    socket = current
    let opened = false
    const timer = window.setTimeout(() => {
      if (socket === current && current.readyState !== WebSocket.OPEN) {
        current.close()
        reject(new Error('WebSocket 连接超时'))
      }
    }, 5000)

    current.onopen = () => {
      opened = true
      window.clearTimeout(timer)
      asrStatus.value = '已连接'
      resolve()
    }
    current.onmessage = (message) => {
      try {
        handleAsrEvent(JSON.parse(message.data))
      } catch (error) {
        console.error('[SpeakerTest] event parse failed:', error)
      }
    }
    current.onerror = () => {
      asrStatus.value = '连接错误'
      if (!opened) reject(new Error('WebSocket 连接错误'))
    }
    current.onclose = () => {
      window.clearTimeout(timer)
      if (socket === current) {
        socket = null
        asrStatus.value = recording.value ? '连接已断开' : '已停止'
      }
      if (!opened) reject(new Error('WebSocket 连接已关闭'))
    }
  })
}

function sendAudio(arrayBuffer) {
  if (!upstreamStarted) return
  if (!socket || socket.readyState !== WebSocket.OPEN) return
  if (!arrayBuffer || arrayBuffer.byteLength === 0) return
  socket.send(arrayBuffer)
}

async function toggleRecording() {
  if (recording.value) {
    await stopRecording()
  } else {
    await startRecording()
  }
}

async function startRecording() {
  if (busy.value || recording.value) return
  busy.value = true
  errorText.value = ''
  asrStatus.value = '正在准备'
  partialText.value = ''
  partialLabel.value = ''
  upstreamStarted = false

  try {
    await connectEvents()
    await startMic((pcm) => sendAudio(pcm))
    const response = await fetch('/start', { method: 'POST' })
    if (!response.ok) throw new Error(await response.text())
    upstreamStarted = true
    recording.value = true
    asrStatus.value = '采集中'
  } catch (error) {
    errorText.value = `启动失败：${error.message}`
    await stopRecording()
  } finally {
    busy.value = false
  }
}

async function stopRecording() {
  const wasActive = recording.value || upstreamStarted
  recording.value = false
  upstreamStarted = false
  partialText.value = ''
  partialLabel.value = ''
  await stopMic().catch(() => {})
  if (wasActive) {
    await fetch('/stop', { method: 'POST' }).catch(() => {})
  }
  if (socket) {
    const current = socket
    socket = null
    current.close()
  }
  asrStatus.value = '已停止'
}

function handleAsrEvent(event) {
  if (event.type === 'status') {
    asrStatus.value = event.message || asrStatus.value
    return
  }
  if (event.type === 'error') {
    errorText.value = `ASR 错误：${event.message || '未知错误'}`
    asrStatus.value = '错误'
    return
  }
  if (event.type === 'partial') {
    const speaker = ensureSpeaker(rawSpeakerFromEvent(event))
    partialLabel.value = speaker?.label || '待识别说话人'
    partialText.value = event.text || ''
    return
  }
  if (event.type !== 'sentence_done') return

  const text = String(event.text || '').trim()
  if (!text) return
  const rawSpeaker = rawSpeakerFromEvent(event)
  const key = `${event.sourceId || event.sentenceId || ''}-${rawSpeaker}-${text}`
  if (seenFinals.has(key)) return
  seenFinals.add(key)

  const speaker = updateSpeakerStats(rawSpeaker, text)
  finals.value.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    sourceId: event.sourceId || event.sentenceId || '',
    text,
    rawSpeaker,
    label: speaker?.label || '未返回说话人ID',
    color: speaker?.color || '#64748b',
    time: formatTime()
  })
  partialText.value = ''
  partialLabel.value = ''
  scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  if (transcriptRef.value) {
    transcriptRef.value.scrollTop = transcriptRef.value.scrollHeight
  }
}

function clearResults() {
  if (recording.value) return
  finals.value = []
  speakerRecords.value = []
  partialText.value = ''
  partialLabel.value = ''
  speakerMap.clear()
  seenFinals.clear()
  speakerIndex = 0
}
</script>

<style scoped>
.speaker-test-page {
  background: #f4f7fb;
  color: #172033;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100vh;
  padding: 14px;
}

.test-topbar,
.live-panel,
.speaker-panel,
.meter-panel,
.status-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(31, 41, 55, 0.08);
}

.test-topbar {
  align-items: center;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 16px 18px;
}

.test-topbar h1,
.live-panel h2,
.speaker-panel h2 {
  color: #172033;
  font-size: 20px;
  line-height: 1.25;
  margin: 0;
}

.test-topbar span {
  color: #647086;
  display: block;
  font-size: 13px;
  line-height: 1.5;
  margin-top: 5px;
}

.eyebrow {
  color: #4f46e5;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
  margin: 0 0 5px;
}

.record-button,
.secondary-button {
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 900;
  padding: 10px 14px;
}

.record-button {
  background: #2563eb;
  border: 1px solid #2563eb;
  color: #ffffff;
  min-width: 116px;
}

.record-button.active {
  background: #dc2626;
  border-color: #dc2626;
}

.record-button:disabled,
.secondary-button:disabled {
  cursor: default;
  opacity: 0.62;
}

.secondary-button {
  background: #f8fafc;
  border: 1px solid #d7deeb;
  color: #334155;
}

.test-status-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.status-card {
  padding: 12px 14px;
}

.status-card span,
.meter-panel span {
  color: #647086;
  display: block;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 5px;
}

.status-card strong,
.meter-panel strong {
  color: #172033;
  display: block;
  font-size: 16px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.meter-panel {
  padding: 12px 14px;
}

.meter-panel > div:first-child {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.meter-track {
  background: #e2e8f0;
  border-radius: 999px;
  height: 8px;
  margin-top: 8px;
  overflow: hidden;
}

.meter-track i {
  background: linear-gradient(90deg, #2563eb, #22c55e);
  border-radius: inherit;
  display: block;
  height: 100%;
  transition: width 0.18s ease;
}

.test-workspace {
  display: grid;
  flex: 1;
  gap: 12px;
  grid-template-columns: minmax(520px, 1fr) minmax(300px, 360px);
  min-height: 0;
}

.live-panel,
.speaker-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 14px;
}

.live-panel > header,
.speaker-panel > header {
  align-items: center;
  border-bottom: 1px solid #edf0f6;
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 12px;
}

.transcript-list {
  border-bottom: 1px solid #edf0f6;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 4px 2px 12px;
}

.transcript-item {
  display: grid;
  gap: 12px;
  grid-template-columns: 72px 1fr;
  padding: 12px 4px;
}

.transcript-item time {
  color: #7f8aa3;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.speaker-pill {
  background: color-mix(in srgb, var(--speaker-color) 13%, white);
  border: 1px solid color-mix(in srgb, var(--speaker-color) 32%, white);
  border-radius: 999px;
  color: var(--speaker-color);
  display: inline-flex;
  font-size: 12px;
  font-weight: 900;
  margin-right: 8px;
  padding: 3px 8px;
}

.transcript-item small {
  color: #94a3b8;
  font-size: 12px;
}

.transcript-item p {
  color: #111827;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.7;
  margin: 8px 0 0;
  overflow-wrap: anywhere;
}

.partial-strip {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-top: 12px;
  padding: 12px 14px;
}

.partial-strip.active {
  background: #eef6ff;
  border-color: #cfe5ff;
}

.partial-strip span {
  color: #3977c7;
  display: block;
  font-size: 12px;
  font-weight: 900;
  margin-bottom: 6px;
}

.partial-strip strong {
  color: #1155d9;
  display: block;
  font-size: 16px;
  line-height: 1.6;
  min-height: 26px;
  overflow-wrap: anywhere;
}

.speaker-list {
  display: grid;
  gap: 10px;
  overflow: auto;
  padding-right: 2px;
}

.speaker-card {
  border: 1px solid color-mix(in srgb, var(--speaker-color) 24%, #e5eaf2);
  border-left: 4px solid var(--speaker-color);
  border-radius: 8px;
  padding: 12px;
}

.speaker-card strong {
  color: var(--speaker-color);
  display: block;
  font-size: 15px;
}

.speaker-card small {
  color: #64748b;
  display: block;
  font-size: 12px;
  line-height: 1.45;
  margin-top: 3px;
  overflow-wrap: anywhere;
}

.speaker-card dl {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, 1fr);
  margin: 12px 0 0;
}

.speaker-card dl div {
  background: #f8fafc;
  border-radius: 8px;
  padding: 8px;
}

.speaker-card dt {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.speaker-card dd {
  color: #172033;
  font-size: 18px;
  font-weight: 900;
  margin: 3px 0 0;
}

.test-notes {
  background: #fffdf8;
  border: 1px solid #eadfcb;
  border-radius: 8px;
  color: #7c6a4d;
  font-size: 13px;
  line-height: 1.6;
  margin-top: 12px;
  padding: 12px;
}

.test-notes strong {
  color: #92400e;
  display: block;
  font-size: 13px;
  margin-bottom: 6px;
}

.test-notes p {
  margin: 0 0 8px;
}

.test-notes p:last-child {
  margin-bottom: 0;
}

.empty-board {
  align-items: center;
  background: #f8fafc;
  border: 1px dashed #d7deeb;
  border-radius: 8px;
  color: #7b8497;
  display: flex;
  font-size: 14px;
  font-weight: 700;
  justify-content: center;
  line-height: 1.6;
  min-height: 260px;
  padding: 24px;
  text-align: center;
}

.empty-board.compact {
  min-height: 120px;
}

.error-banner {
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  color: #be123c;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.5;
  margin: 0;
  padding: 10px 12px;
}

@media (max-width: 900px) {
  .test-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .test-status-grid,
  .test-workspace {
    grid-template-columns: 1fr;
  }

  .transcript-item {
    grid-template-columns: 1fr;
  }
}
</style>
