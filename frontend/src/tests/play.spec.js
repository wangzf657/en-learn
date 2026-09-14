import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Play from '../views/Play.vue'
import { mountWithRouter, mockFetch, restoreFetch, dispatchTimeUpdate } from './helpers.js'

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

describe('Play.vue core interactions', () => {
  beforeEach(() => {
    mockFetch((url) => {
      if (url === '/api/day/2026-09-14') return { body: sampleDay }
      if (url.endsWith('/checkin')) return { body: { ok: true } }
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
})
