import { describe, it, expect } from 'vitest'
import { pcmToWav } from '../utils/recorder.js'

describe('pcmToWav', () => {
  it('builds a mono 16k 16bit WAV with correct header', async () => {
    const chunks = [new Float32Array([0, 0.5, -0.5, 1, -1])]
    const blob = pcmToWav(chunks)

    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(44 + chunks[0].length * 2)

    const ab = await blob.arrayBuffer()
    const view = new DataView(ab)
    const text = (off, len) => String.fromCharCode(...new Uint8Array(ab, off, len))

    expect(text(0, 4)).toBe('RIFF')
    expect(text(8, 4)).toBe('WAVE')
    expect(text(12, 4)).toBe('fmt ')
    expect(text(36, 4)).toBe('data')
    expect(view.getUint16(20, true)).toBe(1)
    expect(view.getUint16(22, true)).toBe(1)
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint16(34, true)).toBe(16)
  })

  it('handles empty chunks', async () => {
    const blob = pcmToWav([])
    expect(blob.size).toBe(44)
    const ab = await blob.arrayBuffer()
    const view = new DataView(ab)
    expect(view.getUint32(40, true)).toBe(0)
  })
})
