import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SubtitlePanel from '../components/SubtitlePanel.vue'

const sentences = [
  { start: 1.2, end: 4.5, en: 'Hello there', zh: '你好', words: [{ w: 'hello', phonetic: 'həˈloʊ', note: '打招呼' }] },
  { start: 5.0, end: 8.0, en: 'How are you?', zh: '你好吗？' },
]

describe('SubtitlePanel 台词面板', () => {
  const mountPanel = (props = {}) =>
    mount(SubtitlePanel, { props: { title: '台词', sentences, ...props } })

  it('默认点击卡片触发 seek 并跳转,不触发 repeat', async () => {
    const wrapper = mountPanel()
    const cards = wrapper.findAll('.sentence-card')
    await cards[1].trigger('click')

    expect(wrapper.emitted('seek')).toHaveLength(1)
    expect(wrapper.emitted('seek')[0][0]).toMatchObject({ start: 5 })
    expect(wrapper.emitted('repeat')).toBeUndefined()
  })

  it('card-action=repeat 时点击卡片触发 repeat,不触发 seek', async () => {
    const wrapper = mountPanel({ cardAction: 'repeat' })
    const cards = wrapper.findAll('.sentence-card')
    await cards[0].trigger('click')

    expect(wrapper.emitted('repeat')).toHaveLength(1)
    expect(wrapper.emitted('repeat')[0][0]).toMatchObject({ start: 1.2 })
    expect(wrapper.emitted('seek')).toBeUndefined()
  })

  it('时间戳按钮点击触发 seek,且不冒泡到卡片', async () => {
    const wrapper = mountPanel({ cardAction: 'repeat' })
    const btn = wrapper.findAll('.seek-btn')[1]

    await btn.trigger('click')

    expect(wrapper.emitted('seek')).toHaveLength(1)
    expect(wrapper.emitted('seek')[0][0]).toMatchObject({ start: 5 })
    // repeat 不应被触发
    expect(wrapper.emitted('repeat')).toBeUndefined()
  })

  it('时间戳按钮显示该句起始时间', () => {
    const wrapper = mountPanel()
    const btns = wrapper.findAll('.seek-btn')
    expect(btns[0].text()).toContain('0:01')
    expect(btns[1].text()).toContain('0:05')
  })

  it('不再渲染词块(详情收敛到练习弹窗)', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('.word-chip').exists()).toBe(false)
  })
})
