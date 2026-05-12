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
    const isLocalDev = ['127.0.0.1', 'localhost'].includes(window.location.hostname) && window.location.port === '5173'
    const wsUrl = isLocalDev
      ? `${protocol}//127.0.0.1:8771`
      : `${protocol}//${window.location.host}/ws`
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

  function updateFinalEntry(entryId, patch) {
    const index = finals.value.findIndex((item) => item.id === entryId)
    if (index < 0) return null
    finals.value[index] = {
      ...finals.value[index],
      ...patch
    }
    return finals.value[index]
  }

  function mergeInsightItems(existingItems, incomingItems, limit = 24) {
    const seen = new Set()
    const merged = []
    for (const item of [...existingItems, ...incomingItems]) {
      const text = String(item?.text || '').trim()
      if (!text || seen.has(text)) continue
      seen.add(text)
      merged.push(item)
      if (merged.length >= limit) break
    }
    return merged
  }

  function shouldAnalyzeTranscript(text) {
    const clean = String(text || '').replace(/\s+/g, '')
    if (clean.length < 8) return false
    if (/^(测试|test|喂|嗯|啊|呃|额|好|可以|行|是|对)[。！？!?.，,、]*$/i.test(clean)) return false
    if ((clean.match(/测试/g) || []).length >= 2 && clean.length <= 30) return false
    const lyricCues = ['一杯敬明天', '一杯敬过往', '没人记起你的模样', '固执地唱着', '当你走进']
    if (lyricCues.some((cue) => clean.includes(cue))) return false
    const candidateCues = [
      '我', '我们', '负责', '参与', '主导', '做过', '经历', '项目', '岗位',
      '工作', '数据', '指标', '客户', '税务', '会计', '运营', '成本', '发票',
      '流程', '复盘', '结果', '提升', '降低', '完成'
    ]
    const interviewerCues = ['请问', '请你', '能不能', '介绍一下', '讲一下', '为什么', '如何', '你觉得']
    const cueCount = candidateCues.filter((cue) => clean.includes(cue)).length
    const looksLikeQuestionOnly = clean.endsWith('？') || clean.endsWith('?') || interviewerCues.some((cue) => clean.startsWith(cue))
    if (looksLikeQuestionOnly && cueCount === 0) return false
    return cueCount > 0
  }

  function buildAnalysisTextForEntry(entry) {
    const recentTranscript = finals.value
      .filter((item) => item.text && !item.pending)
      .slice(-6)
      .map((item) => `${item.time || ''} 转写：${item.text}`)
      .join('\n')
    return [
      `最近面试转写：\n${recentTranscript}`,
      `重点片段：\n${entry.text}`,
      '请判断其中是否存在可评估的候选人回答；如果主要是面试官提问、寒暄、测试或无关内容，请返回无法判定。'
    ].join('\n\n')
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
              
              const newQuestions = questionsList.slice(0, 3).map((q) => ({
                id: makeId(),
                text: q,
                time: analysisRecord.time
              }))
              questions.value = mergeInsightItems(questions.value, newQuestions, 24)
              
              const newDoubts = analysisRecord.doubts.slice(0, 5).map((q) => ({
                id: makeId(),
                text: q,
              }))
              doubts.value = mergeInsightItems(doubts.value, newDoubts, 24)
                .map((item, index) => ({ ...item, index: index + 1, time: item.time || analysisRecord.time }))
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
        updateFinalEntry(entry.id, {
          speaker: 'unknown',
          speakerLabel: '转写片段',
          roleStatus: 'unclassified',
          roleSource: 'none',
          roleConfidence: 0,
          roleReason: '实时阶段不使用 DeepSeek 判断说话人'
        })
        if (shouldAnalyzeTranscript(entry.text)) {
          latestFinal.value = entry
          triggerAiAnalysis(buildAnalysisTextForEntry(entry), 'sentence_done', entry.id)
        }
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
