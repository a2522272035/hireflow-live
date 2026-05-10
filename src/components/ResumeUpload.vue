<template>
  <section class="resume-upload">
    <button
      class="upload-btn"
      type="button"
      :class="{ imported: resumeInfo }"
      :disabled="uploading"
      @click="resumeInfo ? emit('view-resume') : triggerUpload()"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <span class="upload-text">{{ buttonText }}</span>
    </button>

    <button
      v-if="resumeInfo"
      class="mini-btn"
      type="button"
      title="更换简历"
      :disabled="uploading"
      @click="triggerUpload"
    >
      换
    </button>

    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.doc,.docx,.txt,.html,.htm,.rtf"
      style="display: none"
      @change="handleFileSelect"
    />

    <button
      v-if="resumeInfo"
      class="clear-btn"
      type="button"
      title="清除简历"
      @click="clearResume"
    >
      ×
    </button>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  resume: {
    default: null
  }
})

const emit = defineEmits(['resume-loaded', 'resume-cleared', 'view-resume'])

const fileInput = ref(null)
const uploading = ref(false)
const resumeInfo = ref(null)
const maxFileSize = 30 * 1024 * 1024
const uploadElapsedSeconds = ref(0)
let uploadTimer = null

const buttonText = computed(() => {
  if (uploading.value) return uploadElapsedSeconds.value ? `解析中 ${uploadElapsedSeconds.value}s` : '解析中'
  if (resumeInfo.value) return resumeInfo.value.name ? `查看：${resumeInfo.value.name}` : '查看简历'
  return '导入简历'
})

watch(
  () => props.resume,
  (value) => {
    resumeInfo.value = value || null
  },
  { immediate: true }
)

function triggerUpload() {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

async function handleFileSelect(event) {
  const file = event.target.files[0]
  if (!file) return
  const suffix = file.name.split('.').pop()?.toLowerCase()
  const allowed = ['pdf', 'doc', 'docx', 'txt', 'html', 'htm', 'rtf']
  if (!allowed.includes(suffix)) {
    alert('仅支持 PDF / DOC / DOCX / TXT / HTML / RTF 格式')
    event.target.value = ''
    return
  }
  if (file.size > maxFileSize) {
    alert('简历文件不能超过 30MB')
    event.target.value = ''
    return
  }

  uploading.value = true
  uploadElapsedSeconds.value = 0
  uploadTimer = window.setInterval(() => {
    uploadElapsedSeconds.value += 1
  }, 1000)

  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('filename', file.name)
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), 70000)

    let response
    try {
      response = await fetch('/api/upload-resume', {
        method: 'POST',
        body: formData,
        signal: controller.signal
      })
    } finally {
      window.clearTimeout(timeoutId)
    }

    if (!response.ok) {
      const error = await response.text()
      throw new Error(error)
    }

    const data = await response.json()
    resumeInfo.value = data.resume
    emit('resume-loaded', data.resume)
  } catch (error) {
    console.error('简历解析失败:', error)
    const message = error.name === 'AbortError'
      ? '简历解析超过 70 秒未返回，请换一个更小的文件或稍后重试'
      : error.message
    alert('简历解析失败：' + message)
  } finally {
    uploading.value = false
    if (uploadTimer) {
      window.clearInterval(uploadTimer)
      uploadTimer = null
    }
    uploadElapsedSeconds.value = 0
    event.target.value = ''
  }
}

function clearResume() {
  resumeInfo.value = null
  emit('resume-cleared')
}

onBeforeUnmount(() => {
  if (uploadTimer) {
    window.clearInterval(uploadTimer)
  }
})
</script>

<style scoped>
.resume-upload {
  align-items: center;
  display: flex;
  flex-direction: row;
  gap: 6px;
  min-width: 0;
}

.upload-btn {
  align-items: center;
  background: #4653ff;
  border: none;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  font-size: 14px;
  font-weight: 600;
  gap: 8px;
  height: 38px;
  max-width: 176px;
  padding: 10px 16px;
  transition: background 0.2s ease;
  white-space: nowrap;
}

.upload-btn:hover {
  background: #3a45e6;
}

.upload-btn.imported {
  background: #0f766e;
}

.upload-btn.imported:hover {
  background: #0d665f;
}

.upload-btn:disabled {
  background: #b0b8d4;
  cursor: not-allowed;
}

.upload-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.clear-btn {
  align-items: center;
  background: #fff;
  border: 1px solid #d7deeb;
  border-radius: 50%;
  color: #647086;
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 18px;
  height: 24px;
  justify-content: center;
  line-height: 1;
  padding: 0;
  width: 24px;
}

.clear-btn:hover {
  background: #f2f5fa;
}

.mini-btn {
  align-items: center;
  background: #fff;
  border: 1px solid #d7deeb;
  border-radius: 6px;
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 800;
  height: 28px;
  justify-content: center;
  padding: 0;
  width: 30px;
}

.mini-btn:hover {
  background: #f2f5fa;
}

.mini-btn:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
