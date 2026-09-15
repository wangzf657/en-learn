import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mountWithRouter, mockFetch, restoreFetch, dispatchTimeUpdate } from './helpers.js'

vi.mock('../utils/recorder.js', () => ({
  startRecording: vi.fn(),
}))

import Play from '../views/Play.vue'
import { startRecording } from '../utils/recorder.js'

const sampleDay = {
  videoId: 1,
  title: "日常问候",
  videoUrl: "/mock/empty.mp4",
  checked: false,
  subtitle: {
    sentences: [
      { start: 1.2, end: 4.5, en: "How you doing?", zh: "你好吗？", words: [{ w: "doing", phonetic: "ˈduːɪŋ", note: "美式问候" }] },
      { start: 5.0, end: 8.0, en: "I'm doing great.", zh: "我很好。" },
      { start: 8.5, end: 12.0, en: "Let's get started.", zh: "我们开始吧。" },
    ],
  },
}

function makeScoreResponse(reference) {
  const words = reference ? reference.match(/\b[\w']+\b/g) || ['hello'] : ['hello']
  return {
    accuracy_score: 82.5,
    fluency_score: 78,
    completeness_score: 90,
    word_scores: words.map((w) => ({
      word: w,
      accuracy_score: 85,
      expected_phonemes: 'h ə l oʊ',
      actual_phonemes: 'h ə l oʊ',
      phoneme_scores: [80],
    })),
  }
}

describe('Play.vue core interactions', () => {
  beforeEach(() => {
    startRecording.mockResolvedValue({
      stop: vi.fn().mockResolvedValue(new Blob(['fake wav'], { type: 'audio/wav' })),
    })

    mockFetch((url, options) => {
      if (url === '/api/day/2026-09-14') return { body: sampleDay }
      if (url.endsWith('/checkin')) return { body: { ok: true } }
      if (url === '/api/score' && options.method === 'POST') {
        const reference = options.body?.get?.('reference') || 'hello'
        return { body: makeScoreResponse(reference) }
      }
      return { status: 404, body: { detail: 'not found' } }
    })
  })

  afterEach(() => restoreFetch())

  it('renders sentences and highlights current sentence by video time', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const cards = wrapper.findAll('.sentence-card')
    expect(cards.length).toBe(3)
    expect(cards[0].find('.en').text()).toBe('How you doing?')

    const video = wrapper.find('video').element
    await dispatchTimeUpdate(video, 6.5)
    expect(wrapper.findAll('.sentence-card')[1].classes()).toContain('active')

    await dispatchTimeUpdate(video, 10)
    expect(wrapper.findAll('.sentence-card')[2].classes()).toContain('active')
  })

  it('clicking a sentence seeks video to its start and plays', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const video = wrapper.find('video').element
    let played = false
    video.play = () => { played = true; return Promise.resolve() }

    const secondCard = wrapper.findAll('.sentence-card')[1]
    await secondCard.trigger('click')

    expect(video.currentTime).toBe(5.0)
    expect(played).toBe(true)
  })

  it('records repeat and renders score result with colored words', async () => {
    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const firstCard = wrapper.findAll('.sentence-card')[0]
    const repeatBtn = firstCard.find('.repeat-btn')
    expect(repeatBtn.text()).toBe('跟读')

    await repeatBtn.trigger('click')
    expect(startRecording).toHaveBeenCalledTimes(1)
    expect(firstCard.find('.repeat-btn').text()).toBe('停止')

    await firstCard.find('.repeat-btn').trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(firstCard.text()).toContain('准确度 83')
    expect(firstCard.text()).toContain('流利度 78')
    expect(firstCard.text()).toContain('完整度 90')
    expect(firstCard.findAll('.ws-word').length).toBeGreaterThan(0)
    expect(firstCard.findAll('.word-good').length).toBeGreaterThan(0)
    expect(firstCard.find('.repeat-btn').text()).toBe('重新跟读')
  })

  it('shows repeat error inline without blocking the page', async () => {
    startRecording.mockRejectedValueOnce(new Error('麦克风权限被拒绝'))

    const { wrapper } = await mountWithRouter(Play, { props: { date: '2026-09-14' } }, '/play/2026-09-14')

    const firstCard = wrapper.findAll('.sentence-card')[0]
    await firstCard.find('.repeat-btn').trigger('click')
    await new Promise((r) => setTimeout(r, 10))

    expect(firstCard.text()).toContain('麦克风权限被拒绝')
    expect(wrapper.find('video').exists()).toBe(true)
  })
})
