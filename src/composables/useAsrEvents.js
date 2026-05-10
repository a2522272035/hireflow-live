import { ref } from 'vue'

export function useAsrEvents() {
  const asrStatus = ref('未开始')
  const vadStatus = ref('等待录音')
  const semanticStatus = ref('等待触发')
  const partialText = ref('')
  const currentText = ref('')
  const finals = ref([])
  const messages = ref([])
  const analyses = ref([])
  const questions = ref([])
  const doubts = ref([])
  const aiLoading = ref(false)
  const latestFinal = ref(null)

  let eventSocket = null
  let pendingUtterances = []
  let pendingAnalysisCount = 0
  let stateVersion = 0

  function makeId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
  }

  function formatTime() {
    const now = new Date()
    return [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map((n) => String(n).padStart(2, '0'))
      .join(':')
  }

  function connect() {
    if (eventSocket && eventSocket.readyState === WebSocket.OPEN) {
      return Promise.resolve()
    }
    if (eventSocket) {
      eventSocket.close()
      eventSocket = null
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(wsUrl)
      eventSocket = socket
      let opened = false
      const timer = window.setTimeout(() => {
        if (eventSocket === socket && socket.readyState !== WebSocket.OPEN) {
          socket.close()
          reject(new Error('WebSocket 连接超时'))
        }
      }, 5000)

      socket.onopen = () => {
        opened = true
        window.clearTimeout(timer)
        asrStatus.value = '已连接'
        resolve()
      }
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleEvent(data)
        } catch (err) {
          console.error('[Event] parse error:', err)
        }
      }
      socket.onclose = () => {
        window.clearTimeout(timer)
        if (eventSocket === socket) {
          eventSocket = null
          asrStatus.value = '已断开'
        }
        if (!opened) reject(new Error('WebSocket 连接已关闭'))
      }
      socket.onerror = () => {
        asrStatus.value = '连接错误'
        if (!opened) reject(new Error('WebSocket 连接错误'))
      }
    })
  }

  function disconnect() {
    if (eventSocket) {
      const socket = eventSocket
      eventSocket = null
      socket.close()
    }
  }

  function sendAudio(arrayBuffer) {
    if (!eventSocket || eventSocket.readyState !== WebSocket.OPEN) return
    if (!arrayBuffer || arrayBuffer.byteLength === 0) return
    eventSocket.send(arrayBuffer)
  }

  function updateAiLoading(delta) {
    pendingAnalysisCount = Math.max(0, pendingAnalysisCount + delta)
    aiLoading.value = pendingAnalysisCount > 0
  }

  function isCurrentVersion(version) {
    return version === stateVersion
  }

  function resetAsrState() {
    stateVersion += 1
    pendingUtterances = []
    pendingAnalysisCount = 0
    asrStatus.value = '未开始'
    vadStatus.value = '等待录音'
    semanticStatus.value = '等待触发'
    partialText.value = ''
    currentText.value = ''
    finals.value = []
    messages.value = []
    analyses.value = []
    questions.value = []
    doubts.value = []
    aiLoading.value = false
    latestFinal.value = null
  }

  function speakerLabelForRole(role) {
    if (role === 'candidate') return '候选人'
    if (role === 'interviewer') return '面试官'
    return '待识别'
  }

  function normalizeRole(role) {
    return ['candidate', 'interviewer', 'unknown'].includes(role) ? role : 'unknown'
  }

  function updateFinalEntry(entryId, patch) {
    const index = finals.value.findIndex((item) => item.id === entryId)
    if (index < 0) return null
    finals.value[index] = {
      ...finals.value[index],
      ...patch
    }
    return finals.value[index]
  }

  function buildRoleHistory(entryId) {
    return finals.value
      .filter((item) => item.id !== entryId && item.text && !item.pending)
      .slice(-8)
      .map((item) => ({
        speaker: item.speaker || 'unknown',
        speakerLabel: item.speakerLabel || speakerLabelForRole(item.speaker),
        text: item.text
      }))
  }

  function buildCandidateAnalysisText() {
    const interviewerContext = finals.value
      .filter((item) => item.speaker === 'interviewer' && item.text && !item.pending)
      .slice(-3)
      .map((item) => `${item.time || ''} 面试官：${item.text}`)
      .join('\n')
    const candidateText = finals.value
      .filter((item) => item.speaker === 'candidate' && item.text && !item.pending)
      .slice(-8)
      .map((item) => item.text)
      .join('')

    if (!candidateText) return ''
    return [
      interviewerContext ? `面试官上下文：\n${interviewerContext}` : '',
      `候选人回答：\n${candidateText}`
    ].filter(Boolean).join('\n\n')
  }

  async function classifyEntrySpeaker(entry) {
    if (!entry?.id || !entry.text) return

    const version = stateVersion
    updateFinalEntry(entry.id, {
      speaker: 'unknown',
      speakerLabel: '识别中',
      roleStatus: 'classifying'
    })
    updateAiLoading(1)

    try {
      const response = await fetch('/api/classify-speaker-role', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: entry.text,
          history: buildRoleHistory(entry.id)
        })
      })
      if (!response.ok) throw new Error(await response.text())

      const data = await response.json()
      if (!isCurrentVersion(version)) return
      const role = normalizeRole(data.role)
      const updatedEntry = updateFinalEntry(entry.id, {
        speaker: role,
        speakerLabel: data.speakerLabel || speakerLabelForRole(role),
        roleStatus: 'classified',
        roleSource: data.source || 'ai',
        roleConfidence: Number(data.confidence) || 0,
        roleReason: data.reason || ''
      })

      if (role === 'candidate' && updatedEntry) {
        latestFinal.value = updatedEntry
        const analysisText = buildCandidateAnalysisText()
        if (analysisText) {
          triggerAiAnalysis(analysisText, 'candidate_sentence_done', entry.id)
        }
      }
    } catch (error) {
      if (!isCurrentVersion(version)) return
      console.warn('[AI] 角色判断失败:', error)
      updateFinalEntry(entry.id, {
        speaker: 'unknown',
        speakerLabel: '待识别',
        roleStatus: 'failed',
        roleSource: 'error',
        roleConfidence: 0,
        roleReason: error.message
      })
    } finally {
      updateAiLoading(-1)
    }
  }

  function buildAnalysisMessage(result) {
    const isCorrect = result.is_correct
    const doubtsList = result.doubts || []
    const finalAnalysis = result.analysis || ''

    let displayContent = ''
    if (isCorrect === true) {
      displayContent = '✅ 回答正确\n\n' + finalAnalysis
    } else if (isCorrect === false) {
      displayContent = '❌ 回答存在错误\n\n' + finalAnalysis
    } else {
      displayContent = '⚠️ 无法判定\n\n' + finalAnalysis
    }

    if (doubtsList.length > 0) {
      displayContent += '\n\n存疑点：\n' + doubtsList.map((d, i) => `${i + 1}. ${d}`).join('\n')
    }

    return displayContent
  }

  async function triggerAiAnalysis(text, triggerType = 'unknown', sourceId = '') {
    if (!text) return
    
    console.log(`[AI] 触发类型: ${triggerType}, 传递文本:`, text)

    const version = stateVersion
    updateAiLoading(1)
    
    const aiMessageId = 'ai-analysis-' + makeId()
    const startedTime = formatTime()
    messages.value.push({
      id: aiMessageId,
      type: 'ai',
      content: '正在分析面试片段...',
      time: startedTime
    })
    
    let rawContent = ''
    
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          text: text,
          history: finals.value.map((item) => item.text)
        })
      })
      
      if (!response.ok) throw new Error(await response.text())
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6).trim()
          if (dataStr === '[DONE]') continue
          
          try {
            const data = JSON.parse(dataStr)
            if (!isCurrentVersion(version)) continue
            
            if (data.text) {
              rawContent += data.text
              const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
              if (msgIndex >= 0) {
                messages.value[msgIndex] = {
                  ...messages.value[msgIndex],
                  content: rawContent
                }
              }
            } else if (data.done) {
              const questionsList = data.questions || []
              const analysisRecord = {
                id: 'analysis-' + makeId(),
                sourceId,
                triggerType,
                transcript: text,
                analysis: data.analysis || '',
                is_correct: data.is_correct ?? null,
                doubts: data.doubts || [],
                questions: questionsList,
                time: formatTime()
              }
              analyses.value.push(analysisRecord)
              const displayContent = buildAnalysisMessage(analysisRecord)
              
              const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
              if (msgIndex >= 0) {
                messages.value[msgIndex] = {
                  ...messages.value[msgIndex],
                  content: displayContent
                }
              }
              
              questions.value = questionsList.slice(0, 3).map((q) => ({
                id: makeId(),
                text: q
              }))
              
              doubts.value = analysisRecord.doubts.slice(0, 5).map((q, index) => ({
                id: makeId(),
                text: q,
                index: index + 1
              }))
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    } catch (error) {
      if (!isCurrentVersion(version)) return
      console.error('[AI] 分析失败:', error)
      messages.value.push({
        id: makeId(),
        type: 'ai',
        content: `AI分析失败：${error.message}`,
        time: formatTime()
      })
    } finally {
      updateAiLoading(-1)
    }
  }

  function handleEvent(event) {
    if (event.type === 'status') {
      asrStatus.value = event.message || asrStatus.value
      return
    }
    if (event.type === 'partial') {
      vadStatus.value = 'VAD 检测中'
      partialText.value = event.text || ''
      return
    }
    if (event.type === 'merge_continue') {
      vadStatus.value = 'VAD 已检测到停顿，合并上下文'
      semanticStatus.value = '语义未完整，等待继续'
      return
    }
    if (event.type === 'utterance') {
      vadStatus.value = 'VAD 已检测到停顿'
      semanticStatus.value = '正在判断语义完整性...'
      const text = event.text || ''
      if (!text) return
      pendingUtterances.push(text)
      partialText.value = ''
      currentText.value = text
      const entry = {
        id: makeId(),
        text: text,
        speaker: 'unknown',
        speakerLabel: '待识别',
        roleStatus: 'pending',
        time: formatTime(),
        pending: true
      }
      finals.value.push(entry)
      
      return
    }
    if (event.type === 'sentence_done') {
      semanticStatus.value = '✓ 语义完整'
      vadStatus.value = '等待下一个语句'
      const text = event.text || ''
      if (pendingUtterances.length > 0) {
        const lastIdx = finals.value.length - 1
        if (lastIdx >= 0 && finals.value[lastIdx].pending) {
          finals.value[lastIdx] = {
            ...finals.value[lastIdx],
            text: text,
            pending: false
          }
        }
      }
      pendingUtterances = []
      currentText.value = ''
      partialText.value = ''
      asrStatus.value = '✓ 已确认句子'
      const entry = finals.value[finals.value.length - 1]
      if (entry && !entry.pending) {
        classifyEntrySpeaker(entry)
      }
      return
    }
    if (event.type === 'error') {
      asrStatus.value = '错误'
      vadStatus.value = '错误'
      semanticStatus.value = '错误'
      const errMsg = event.message || '未知错误'
      messages.value.push({
        id: makeId(),
        type: 'system',
        content: `ASR错误：${errMsg}`,
        time: formatTime()
      })
      return
    }
  }

  async function sendQuestion(text) {
    if (!text) return
    const version = stateVersion
    updateAiLoading(1)
    messages.value.push({
      id: makeId(),
      type: 'interviewer',
      content: text,
      time: formatTime()
    })
    try {
      const response = await fetch('/api/question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
      })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      if (!isCurrentVersion(version)) return
      messages.value.push({
        id: makeId(),
        type: 'ai',
        content: data.reply || '已发送追问。',
        time: formatTime()
      })
    } catch (error) {
      if (!isCurrentVersion(version)) return
      messages.value.push({
        id: makeId(),
        type: 'system',
        content: `发送追问失败：${error.message}`,
        time: formatTime()
      })
    } finally {
      updateAiLoading(-1)
    }
  }

  async function switchMode(mode) {
    try {
      const response = await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      })
      if (!response.ok) throw new Error(await response.text())
      const data = await response.json()
      asrStatus.value = `模式：${data.fast_mode ? '快速' : '智能'}`
    } catch (error) {
      messages.value.push({
        id: makeId(),
        type: 'system',
        content: `切换模式失败：${error.message}`,
        time: formatTime()
      })
    }
  }

  return {
    asrStatus,
    vadStatus,
    semanticStatus,
    partialText,
    currentText,
    finals,
    messages,
    analyses,
    questions,
    doubts,
    aiLoading,
    connect,
    disconnect,
    sendAudio,
    sendQuestion,
    switchMode,
    resetAsrState
  }
}
