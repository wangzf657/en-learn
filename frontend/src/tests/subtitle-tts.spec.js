import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SubtitlePanel from '../components/SubtitlePanel.vue'

const sentences = [
  { en: 'Hello there', zh: '你好', words: [{ w: 'hello', phonetic: 'həˈloʊ', note: '打招呼' }] },
]

describe('SubtitlePanel 朗读(TTS)', () => {
  let synth
  let utterances

  beforeEach(() => {
    utterances = []
    synth = { speak: vi.fn((u) => utterances.push(u)), cancel: vi.fn(), resume: vi.fn() }
    window.speechSynthesis = synth
    window.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text
      }
    }
  })

  afterEach(() => {
    delete window.speechSynthesis
    delete window.SpeechSynthesisUtterance
  })

  const mountPanel = () => mount(SubtitlePanel, { props: { title: '台词', sentences } })

  it('点击朗读按钮朗读整句,语速 0.9 且 lang=en-US,不触发 seek', async () => {
    const wrapper = mountPanel()
    await wrapper.find('.speak-btn').trigger('click')

    expect(synth.speak).toHaveBeenCalledTimes(1)
    expect(utterances[0].text).toBe('Hello there')
    expect(utterances[0].rate).toBe(0.9)
    expect(utterances[0].lang).toBe('en-US')
    expect(wrapper.emitted('seek')).toBeUndefined()
  })

  it('朗读中再点一次 = cancel 且状态归位', async () => {
    const wrapper = mountPanel()
    const btn = wrapper.find('.speak-btn')

    await btn.trigger('click')
    expect(btn.classes()).toContain('speaking')

    await btn.trigger('click')
    expect(synth.cancel).toHaveBeenCalled()
    expect(wrapper.find('.speak-btn').classes()).not.toContain('speaking')
  })

  it('不再渲染词块(详情收敛到练习弹窗)', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('.word-chip').exists()).toBe(false)
  })

  it('无 speechSynthesis 时点击不报错', async () => {
    delete window.speechSynthesis
    const wrapper = mountPanel()
    await wrapper.find('.speak-btn').trigger('click')
    expect(wrapper.find('.speak-btn').exists()).toBe(true)
  })

  it('卸载时 cancel 清理', async () => {
    const wrapper = mountPanel()
    await wrapper.find('.speak-btn').trigger('click')
    wrapper.unmount()
    expect(synth.cancel).toHaveBeenCalled()
  })
})
