export function pcmToWav(float32Chunks) {
  const totalSamples = float32Chunks.reduce((sum, c) => sum + c.length, 0)
  const buffer = new ArrayBuffer(44 + totalSamples * 2)
  const view = new DataView(buffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + totalSamples * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true)
  view.setUint32(28, 16000 * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, totalSamples * 2, true)

  let offset = 44
  for (const chunk of float32Chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const s = Math.max(-1, Math.min(1, chunk[i]))
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
      offset += 2
    }
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

export async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('当前浏览器不支持麦克风录音')
  }

  let stream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (e) {
    if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
      throw new Error('麦克风权限被拒绝，请在浏览器设置中允许使用麦克风')
    }
    if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
      throw new Error('未找到麦克风设备')
    }
    throw new Error(`无法启动麦克风：${e.message}`)
  }

  const AudioContextCtor = window.AudioContext || window.webkitAudioContext
  const ctx = new AudioContextCtor({ sampleRate: 16000 })
  const source = ctx.createMediaStreamSource(stream)
  const processor = ctx.createScriptProcessor(4096, 1, 1)
  const zeroGain = ctx.createGain()
  zeroGain.gain.value = 0

  const chunks = []
  processor.onaudioprocess = (e) => {
    chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
  }

  source.connect(processor)
  processor.connect(zeroGain)
  zeroGain.connect(ctx.destination)

  return {
    stop() {
      return new Promise((resolve) => {
        processor.onaudioprocess = null
        processor.disconnect()
        source.disconnect()
        zeroGain.disconnect()
        stream.getTracks().forEach((t) => t.stop())

        const wav = pcmToWav(chunks)
        ctx.close().then(() => resolve(wav))
      })
    },
  }
}
