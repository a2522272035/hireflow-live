import { ref } from 'vue'
import { appPath, appWsUrl } from '../utils/appPaths'

const QUESTION_MERGE_WINDOW_MS = 18 * 1000

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
  const interviewerQuestions = ref([])
  const interviewTurns = ref([])
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
    const wsUrl = appWsUrl('/ws')
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
    interviewerQuestions.value = []
    interviewTurns.value = []
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

  function sameText(a, b) {
    return String(a || '').replace(/\s+/g, '') === String(b || '').replace(/\s+/g, '')
  }

  function upsertInterviewerQuestion(turn) {
    if (!turn?.id || !turn.question) return
    const item = {
      id: turn.id,
      text: turn.question,
      speakerId: turn.speakerId || '',
      time: turn.time || formatTime(),
      updatedAt: turn.updatedAt || Date.now(),
      partCount: turn.questionParts?.length || 1,
      status: turn.status || 'awaiting_answer'
    }
    const index = interviewerQuestions.value.findIndex((question) => question.id === item.id)
    if (index >= 0) {
      interviewerQuestions.value[index] = {
        ...interviewerQuestions.value[index],
        ...item
      }
    } else {
      interviewerQuestions.value = [...interviewerQuestions.value, item].slice(-40)
    }
  }

  function upsertInterviewerMessage(turn) {
    if (!turn?.id || !turn.question) return
    const messageId = `interviewer-message-${turn.id}`
    const payload = {
      id: messageId,
      type: 'interviewer',
      turnId: turn.id,
      content: turn.question,
      time: turn.time || formatTime()
    }
    const index = messages.value.findIndex((message) => message.id === messageId)
    if (index >= 0) {
      messages.value[index] = {
        ...messages.value[index],
        ...payload
      }
    } else {
      messages.value.push(payload)
    }
  }

  function shouldMergeInterviewerEntry(entry, turn) {
    if (!turn) return false
    if (turn.answers?.length) return false
    const text = String(entry?.text || '').trim()
    if (!text) return false
    if ((turn.questionParts || []).some((part) => sameText(part.text, text))) return true
    const now = entry?.createdAt || Date.now()
    const lastUpdated = turn.updatedAt || turn.createdAt || now
    return now - lastUpdated <= QUESTION_MERGE_WINDOW_MS
  }

  function rebuildQuestionText(parts) {
    return parts
      .map((part) => String(part.text || '').trim())
      .filter(Boolean)
      .join('\n')
  }

  function addOrMergeInterviewerQuestion(entry) {
    const text = String(entry?.text || '').trim()
    if (!text) return null
    const now = entry?.createdAt || Date.now()
    const lastTurn = interviewTurns.value.at(-1)
    let turn = null

    if (shouldMergeInterviewerEntry(entry, lastTurn)) {
      const nextParts = (lastTurn.questionParts || []).some((part) => sameText(part.text, text))
        ? lastTurn.questionParts
        : [
            ...(lastTurn.questionParts || []),
            {
              id: entry.id,
              sourceId: entry.sourceId || '',
              text,
              time: entry.time || formatTime(),
              createdAt: now
            }
          ]
      turn = {
        ...lastTurn,
        questionParts: nextParts,
        question: rebuildQuestionText(nextParts),
        updatedAt: now,
        rawEntryIds: [...new Set([...(lastTurn.rawEntryIds || []), entry.id])]
      }
      interviewTurns.value[interviewTurns.value.length - 1] = turn
    } else {
      const id = `turn-${entry?.sourceId || entry?.id || makeId()}`
      const part = {
        id: entry.id,
        sourceId: entry.sourceId || '',
        text,
        time: entry.time || formatTime(),
        createdAt: now
      }
      turn = {
        id,
        question: text,
        questionParts: [part],
        speakerId: entry?.rawSpeaker || '',
        time: entry?.time || formatTime(),
        createdAt: now,
        updatedAt: now,
        answers: [],
        rawEntryIds: [entry.id],
        status: 'awaiting_answer'
      }
      interviewTurns.value.push(turn)
    }

    upsertInterviewerQuestion(turn)
    upsertInterviewerMessage(turn)
    return turn
  }

  function ensureAnswerTurn(entry) {
    const lastTurn = interviewTurns.value.at(-1)
    if (lastTurn) return lastTurn
    const now = entry?.createdAt || Date.now()
    const turn = {
      id: `turn-unmatched-${entry?.sourceId || entry?.id || makeId()}`,
      question: '未匹配到面试官题目',
      questionParts: [],
      speakerId: '',
      time: entry?.time || formatTime(),
      createdAt: now,
      updatedAt: now,
      answers: [],
      rawEntryIds: [],
      status: 'answering'
    }
    interviewTurns.value.push(turn)
    upsertInterviewerQuestion(turn)
    return turn
  }

  function attachCandidateAnswer(entry) {
    const text = String(entry?.text || '').trim()
    if (!text) return null
    const now = entry?.createdAt || Date.now()
    const lastTurn = ensureAnswerTurn(entry)
    const answers = lastTurn.answers || []
    const answerId = entry.id || `answer-${makeId()}`
    const existingIndex = answers.findIndex((answer) => answer.id === answerId || answer.sourceId === entry.sourceId)
    const answer = {
      id: answerId,
      sourceId: entry.sourceId || '',
      text,
      time: entry.time || formatTime(),
      createdAt: now
    }
    const nextAnswers = existingIndex >= 0
      ? answers.map((item, index) => index === existingIndex ? { ...item, ...answer } : item)
      : [...answers, answer]
    const nextTurn = {
      ...lastTurn,
      answers: nextAnswers,
      status: 'answering',
      updatedAt: now,
      answeredAt: now
    }
    interviewTurns.value[interviewTurns.value.length - 1] = nextTurn
    return { turn: nextTurn, answer }
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

  function buildAnalysisTextForEntry(entry, turn = null) {
    const recentTranscript = finals.value
      .filter((item) => item.text && !item.pending)
      .slice(-6)
      .map((item) => `${item.time || ''} ${item.speakerLabel || (item.speaker === 'interviewer' ? '面试官' : '候选人')}：${item.text}`)
      .join('\n')
    const recentQuestions = interviewerQuestions.value
      .slice(-8)
      .map((item, index) => `${index + 1}. ${item.text}`)
      .join('\n')
    return [
      turn?.question ? `当前面试官题目：\n${turn.question}` : '',
      recentQuestions ? `面试官已提出的问题/追问：\n${recentQuestions}` : '',
      `最近面试转写：\n${recentTranscript}`,
      `重点候选人回答：\n${entry.text}`,
      '请只分析候选人的回答；面试官问题仅作为上下文，不要当作候选人回答评分。'
    ].filter(Boolean).join('\n\n')
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

  async function triggerAiAnalysis(text, triggerType = 'unknown', sourceId = '', meta = {}) {
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
      const response = await fetch(appPath('/api/analyze'), {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          text: text,
          history: finals.value.map((item) => item.text),
          interviewerQuestions: interviewerQuestions.value.map((item) => item.text),
          activeQuestion: meta.questionText || '',
          turnId: meta.turnId || '',
          answerId: meta.answerId || ''
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
                turnId: meta.turnId || '',
                answerId: meta.answerId || sourceId,
                questionText: meta.questionText || '',
                answerText: meta.answerText || '',
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
      const label = event.speakerLabel || ''
      partialText.value = label ? `${label}：${event.text || ''}` : (event.text || '')
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
      const sourceId = event.sourceId || event.sentenceId || makeId()
      const createdAt = Date.now()
      const entry = {
        id: makeId(),
        sourceId,
        text: text,
        speaker: event.speaker || 'unknown',
        speakerLabel: event.speakerLabel || '待识别',
        rawSpeaker: event.rawSpeaker || '',
        roleStatus: event.roleStatus || 'pending',
        roleSource: event.roleSource || 'tencent_speaker_id',
        roleConfidence: event.roleConfidence || 0,
        time: formatTime(),
        createdAt,
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
        const sourceId = event.sourceId || event.sentenceId || ''
        const matchedIdx = sourceId
          ? finals.value.findIndex((item) => item.pending && item.sourceId === sourceId)
          : -1
        const lastIdx = matchedIdx >= 0 ? matchedIdx : finals.value.length - 1
        if (lastIdx >= 0 && finals.value[lastIdx].pending) {
          finals.value[lastIdx] = {
            ...finals.value[lastIdx],
            text: text,
            speaker: event.speaker || finals.value[lastIdx].speaker || 'unknown',
            speakerLabel: event.speakerLabel || finals.value[lastIdx].speakerLabel || '待识别',
            rawSpeaker: event.rawSpeaker || finals.value[lastIdx].rawSpeaker || '',
            roleStatus: event.roleStatus || finals.value[lastIdx].roleStatus || 'confirmed',
            roleSource: event.roleSource || finals.value[lastIdx].roleSource || 'tencent_speaker_id',
            roleConfidence: event.roleConfidence || finals.value[lastIdx].roleConfidence || 0,
            createdAt: finals.value[lastIdx].createdAt || Date.now(),
            confirmedAt: Date.now(),
            pending: false
          }
        }
      }
      pendingUtterances = []
      currentText.value = ''
      partialText.value = ''
      asrStatus.value = '✓ 已确认句子'
      const sourceId = event.sourceId || event.sentenceId || ''
      const entry = sourceId
        ? finals.value.find((item) => item.sourceId === sourceId)
        : finals.value[finals.value.length - 1]
      if (entry && !entry.pending) {
        if (entry.speaker === 'interviewer') {
          addOrMergeInterviewerQuestion(entry)
          return
        }
        if (entry.speaker === 'candidate' && shouldAnalyzeTranscript(entry.text)) {
          const linked = attachCandidateAnswer(entry)
          latestFinal.value = entry
          triggerAiAnalysis(
            buildAnalysisTextForEntry(entry, linked?.turn),
            'sentence_done',
            entry.id,
            {
              turnId: linked?.turn?.id || '',
              answerId: linked?.answer?.id || entry.id,
              questionText: linked?.turn?.question || '',
              answerText: entry.text
            }
          )
        } else if (entry.speaker === 'candidate') {
          attachCandidateAnswer(entry)
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
      const response = await fetch(appPath('/api/question'), {
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
      const response = await fetch(appPath('/api/mode'), {
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
    interviewerQuestions,
    interviewTurns,
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
