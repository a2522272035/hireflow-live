<template>
  <section class="panel transcript-panel">
    <header class="panel-header">
      <div>
        <p class="eyebrow">实时语音转写</p>
        <h2>实时转写</h2>
      </div>
      <button
        class="record-button"
        type="button"
        :class="{ active: isRecording }"
        :disabled="recordButtonDisabled"
        @click="$emit('toggle-recording')"
      >
        {{ recordButtonText }}
      </button>
    </header>

    <div class="status-strip">
      <div class="status-item">
        <span class="label">录音状态</span>
        <div class="recording-line">
          <span class="voice-icon" :class="{ active: isRecording, speaking: hasLiveSpeech }" :style="{ '--voice-fill': `${voiceFillPercent}%` }" aria-hidden="true"><i></i></span>
          <div>
            <strong :class="recordingStatus">{{ statusText }}</strong>
            <small>{{ hasLiveSpeech ? '检测到发言' : isRecording ? '等待发言' : micStatus }}</small>
          </div>
        </div>
      </div>
      <div class="status-item">
        <span class="label">VAD 检测</span>
        <strong :class="vadStatusClass">{{ vadStatus }}</strong>
      </div>
      <div class="status-item">
        <span class="label">语义判定</span>
        <strong :class="semanticStatusClass">{{ semanticStatus }}</strong>
      </div>
      <div class="status-item">
        <span class="label">ASR</span>
        <strong>{{ asrStatus }}</strong>
      </div>
    </div>

    <div class="mode-switch">
      <span class="mode-label">模式</span>
      <button
        class="mode-btn"
        :class="{ active: props.mode === 'smart' }"
        @click="$emit('set-mode', 'smart')"
      >
        智能模式
      </button>
      <button
        class="mode-btn"
        :class="{ active: props.mode === 'fast' }"
        @click="$emit('set-mode', 'fast')"
      >
        快速模式
      </button>
    </div>

    <div ref="transcriptRef" class="transcript-scroll">
      <article
        v-for="item in finals"
        :key="item.id"
        class="final-line"
        :class="{ pending: item.pending }"
      >
        <time>{{ item.time }}</time>
        <div>
          <span class="speaker-tag" :class="[item.speaker || 'unknown', item.roleStatus]">
            {{ item.speakerLabel || speakerLabel(item.speaker) }}
          </span>
          <span v-if="showConfidence(item)" class="confidence-meter">
            <i :style="{ width: `${confidencePercent(item)}%` }"></i>
            <b>置信度 {{ confidencePercent(item) }}%</b>
          </span>
          <p>{{ item.text }}</p>
        </div>
      </article>

      <p v-if="partialText" class="partial-line">{{ partialText }}</p>
      <div v-if="finals.length === 0 && !partialText" class="empty-state">
        点击开始录音后，实时转写会显示在这里。
      </div>
    </div>

    <footer class="current-speech">
      <span>当前语音</span>
      <strong>{{ currentText || '等待输入...' }}</strong>
    </footer>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  recordingStatus: {
    type: String,
    default: 'idle'
  },
  micStatus: {
    type: String,
    default: '未授权'
  },
  volumeLevel: {
    type: Number,
    default: 0
  },
  asrStatus: {
    type: String,
    default: '未连接'
  },
  vadStatus: {
    type: String,
    default: '等待录音'
  },
  semanticStatus: {
    type: String,
    default: '等待触发'
  },
  partialText: {
    type: String,
    default: ''
  },
  currentText: {
    type: String,
    default: ''
  },
  finals: {
    type: Array,
    default: () => []
  },
  mode: {
    type: String,
    default: 'smart'
  }
})

defineEmits(['toggle-recording', 'set-mode'])

const transcriptRef = ref(null)

const isRecording = computed(() => props.recordingStatus === 'recording')
const hasLiveSpeech = computed(() => Boolean(props.partialText || props.currentText))
const voiceFillPercent = computed(() => {
  if (!isRecording.value) return 0
  const liveLevel = Math.round(Math.max(0, Math.min(1, Number(props.volumeLevel) || 0)) * 100)
  if (liveLevel > 0) return Math.max(hasLiveSpeech.value ? 46 : 18, liveLevel)
  if (hasLiveSpeech.value) return 78
  return 24
})
const recordButtonDisabled = computed(() => ['recording', 'finalizing', 'finished'].includes(props.recordingStatus))
const recordButtonText = computed(() => {
  if (props.recordingStatus === 'recording') return '全程录音中'
  if (props.recordingStatus === 'finalizing') return '生成报告中'
  if (props.recordingStatus === 'finished') return '面试已结束'
  return '开始面试录音'
})
const statusText = computed(() => {
  if (props.recordingStatus === 'recording') return '录音中'
  if (props.recordingStatus === 'finalizing') return '生成报告中'
  if (props.recordingStatus === 'finished') return '面试已结束'
  if (props.recordingStatus === 'stopped') return '已停止'
  return '未开始'
})

function speakerLabel(speaker) {
  if (speaker === 'candidate') return '候选人'
  if (speaker === 'interviewer') return '面试官'
  return '待识别'
}

function confidencePercent(item) {
  const value = Number(item?.roleConfidence)
  if (!Number.isFinite(value) || value <= 0) return 0
  return Math.round(Math.max(0, Math.min(1, value)) * 100)
}

function showConfidence(item) {
  return item?.roleStatus === 'classified' && confidencePercent(item) > 0
}

const vadStatusClass = computed(() => {
  if (props.vadStatus.includes('聆听')) return 'listening'
  if (props.vadStatus.includes('停顿')) return 'detecting'
  if (props.vadStatus.includes('等待')) return 'waiting'
  return ''
})

const semanticStatusClass = computed(() => {
  if (props.semanticStatus.includes('判断')) return 'processing'
  if (props.semanticStatus.includes('完整')) return 'complete'
  if (props.semanticStatus.includes('未完')) return 'incomplete'
  return ''
})

watch(
  () => [props.finals.length, props.partialText],
  async () => {
    await nextTick()
    if (transcriptRef.value) {
      transcriptRef.value.scrollTop = transcriptRef.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.transcript-panel {
  min-height: 0;
}

.record-button {
  background: #4f46e5;
  border: 0;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  min-width: 104px;
  padding: 10px 15px;
}

.record-button.active {
  background: #ef4444;
}

.record-button:disabled {
  cursor: default;
  opacity: 0.88;
}

.status-strip {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(4, 1fr);
  margin-bottom: 10px;
}

.mode-switch {
  align-items: center;
  background: #f0f4ff;
  border: 1px solid #d0e0ff;
  border-radius: 10px;
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  padding: 6px 10px;
}

.mode-label {
  color: #4b6cb7;
  font-size: 13px;
  font-weight: 700;
  margin-right: 4px;
}

.mode-btn {
  background: #fff;
  border: 1px solid #c0d0e8;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 5px 10px;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: #e8f0ff;
  border-color: #8bb0ff;
}

.mode-btn.active {
  background: #4f46e5;
  border-color: #4f46e5;
  color: #fff;
}

.status-item {
  background: #f8fafc;
  border: 1px solid #e8edf5;
  border-radius: 8px;
  min-width: 0;
  padding: 8px 9px;
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.label {
  color: #8a94a8;
  display: block;
  font-size: 12px;
  margin-bottom: 5px;
}

.status-item strong {
  color: #1f2937;
  display: block;
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.recording-line {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.recording-line > div {
  min-width: 0;
}

.recording-line small {
  color: #7b8497;
  display: block;
  font-size: 11px;
  line-height: 1.2;
  margin-top: 1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-item strong.recording {
  color: #0f9f6e;
}

.status-item strong.stopped {
  color: #ef4444;
}

.status-item strong.listening {
  color: #3b82f6;
}

.status-item strong.detecting {
  color: #f59e0b;
  animation: pulse-border 1.5s infinite;
}

.status-item strong.waiting {
  color: #6b7280;
}

.status-item strong.processing {
  color: #8b5cf6;
  font-weight: 700;
  animation: pulse-border 0.8s infinite;
}

.status-item strong.complete {
  color: #10b981;
  font-weight: 700;
}

.status-item strong.incomplete {
  color: #f97316;
  font-weight: 600;
}

.voice-icon {
  background: #eef2f7;
  border: 1px solid #d7deeb;
  border-radius: 50%;
  display: inline-flex;
  flex: 0 0 auto;
  height: 28px;
  overflow: hidden;
  position: relative;
  width: 28px;
}

.voice-icon::before {
  background: linear-gradient(180deg, #93c5fd, #22c55e);
  bottom: 0;
  content: "";
  height: var(--voice-fill, 0%);
  left: 0;
  opacity: 0.9;
  position: absolute;
  transition: height 0.22s ease, opacity 0.22s ease;
  width: 100%;
}

.voice-icon i {
  background: #64748b;
  border-radius: 999px;
  height: 11px;
  left: 50%;
  position: absolute;
  top: 6px;
  transform: translateX(-50%);
  transition: background-color 0.22s ease;
  width: 7px;
  z-index: 1;
}

.voice-icon i::before {
  border: 2px solid #64748b;
  border-top: 0;
  border-radius: 0 0 999px 999px;
  content: "";
  height: 7px;
  left: 50%;
  position: absolute;
  top: 9px;
  transform: translateX(-50%);
  transition: border-color 0.22s ease;
  width: 12px;
}

.voice-icon i::after {
  background: #64748b;
  border-radius: 999px;
  content: "";
  height: 6px;
  left: 50%;
  position: absolute;
  top: 16px;
  transform: translateX(-50%);
  transition: background-color 0.22s ease;
  width: 2px;
}

.voice-icon.active {
  border-color: #c7d7f6;
}

.voice-icon.active::before {
  opacity: 0.86;
}

.voice-icon.speaking {
  border-color: #86efac;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
}

.voice-icon.speaking::before {
  opacity: 1;
}

.voice-icon.speaking i,
.voice-icon.speaking i::after {
  background: #fff;
}

.voice-icon.speaking i::before {
  border-color: #fff;
}

@keyframes pulse-border {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.02);
  }
}

.transcript-scroll {
  border-bottom: 1px solid #edf0f6;
  border-top: 1px solid #edf0f6;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px 4px;
}

.final-line {
  display: grid;
  gap: 14px;
  grid-template-columns: 76px 1fr;
  padding: 12px 4px;
}

.final-line time {
  color: #7f8aa3;
  font-size: 13px;
}

.final-line p {
  color: #111827;
  font-size: 16px;
  font-weight: 650;
  line-height: 1.65;
  margin: 0;
  overflow-wrap: anywhere;
}

.speaker-tag {
  border-radius: 999px;
  display: inline-flex;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
  padding: 2px 8px;
}

.speaker-tag.candidate {
  background: #ecfdf5;
  color: #047857;
}

.speaker-tag.interviewer {
  background: #eff6ff;
  color: #1d4ed8;
}

.speaker-tag.unknown {
  background: #f3f4f6;
  color: #4b5563;
}

.speaker-tag.classifying {
  background: #fff7ed;
  color: #c2410c;
}

.confidence-meter {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  display: inline-flex;
  height: 21px;
  margin: 0 0 6px 7px;
  min-width: 112px;
  overflow: hidden;
  position: relative;
  vertical-align: top;
}

.confidence-meter i {
  background: linear-gradient(90deg, #93c5fd, #22c55e);
  bottom: 0;
  left: 0;
  opacity: 0.85;
  position: absolute;
  top: 0;
}

.confidence-meter b {
  color: #334155;
  font-size: 11px;
  font-weight: 800;
  padding: 0 8px;
  position: relative;
  z-index: 1;
}

.final-line.pending {
  opacity: 0.75;
  border-left: 3px solid #8b5cf6;
  padding-left: 10px;
  animation: pending-flash 1.5s infinite;
}

@keyframes pending-flash {
  0%, 100% { border-left-color: #8b5cf6; }
  50% { border-left-color: #c4b5fd; }
}

.partial-line {
  color: #9aa4b6;
  font-size: 14px;
  line-height: 1.7;
  margin: 10px 0 0 90px;
}

.empty-state {
  align-items: center;
  color: #9aa4b6;
  display: flex;
  font-size: 14px;
  height: 100%;
  justify-content: center;
  min-height: 220px;
  text-align: center;
}

.current-speech {
  background: #eef6ff;
  border: 1px solid #cfe5ff;
  border-radius: 8px;
  margin-top: 16px;
  padding: 14px 16px;
}

.current-speech span {
  color: #3977c7;
  display: block;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 6px;
}

.current-speech strong {
  color: #1155d9;
  display: block;
  font-size: 16px;
  line-height: 1.6;
  min-height: 26px;
}

@media (max-width: 720px) {
  .status-strip {
    grid-template-columns: repeat(2, 1fr);
  }

  .final-line {
    grid-template-columns: 1fr;
  }

  .partial-line {
    margin-left: 0;
  }

}
</style>
