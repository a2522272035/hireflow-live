import { ref } from 'vue'

export function useAudioRecorder() {
  const micStatus = ref('未授权')
  const sendingAudio = ref(false)
  let audioContext = null
  let source = null
  let processor = null
  let mediaStream = null
  let onAudioChunk = null
  let isSending = false

  function downsampleTo16k(buffer, inputRate) {
    const outputRate = 16000
    if (inputRate === outputRate) return buffer
    const ratio = inputRate / outputRate
    const length = Math.floor(buffer.length / ratio)
    const result = new Float32Array(length)
    for (let index = 0; index < length; index += 1) {
      result[index] = buffer[Math.floor(index * ratio)] || 0
    }
    return result
  }

  function floatTo16BitPCM(float32) {
    const pcm = new Int16Array(float32.length)
    for (let index = 0; index < float32.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, float32[index]))
      pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }
    return pcm.buffer
  }

  async function start(callback) {
    onAudioChunk = callback
    isSending = true
    sendingAudio.value = true
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      }
    })
    micStatus.value = '已授权'
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
    source = audioContext.createMediaStreamSource(mediaStream)
    processor = audioContext.createScriptProcessor(4096, 1, 1)
    processor.onaudioprocess = (event) => {
      if (!isSending) return
      const input = event.inputBuffer.getChannelData(0)
      const pcm = floatTo16BitPCM(downsampleTo16k(input, audioContext.sampleRate))
      if (onAudioChunk) onAudioChunk(pcm)
    }
    source.connect(processor)
    processor.connect(audioContext.destination)
  }

  async function stop() {
    isSending = false
    sendingAudio.value = false
    onAudioChunk = null
    if (processor) processor.disconnect()
    if (source) source.disconnect()
    if (audioContext) await audioContext.close().catch(() => {})
    if (mediaStream) mediaStream.getTracks().forEach((track) => track.stop())
    processor = null
    source = null
    audioContext = null
    mediaStream = null
    micStatus.value = '未授权'
  }

  return { micStatus, sendingAudio, start, stop }
}
