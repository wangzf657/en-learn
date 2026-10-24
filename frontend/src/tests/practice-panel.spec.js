import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PracticePanel from '../components/PracticePanel.vue'

// V2.0 提炼式四板样例
const practice = {
  words: [
    { w: 'fix it', zh: '修好它', note: '修东西万能短语' },
    { w: 'broken', zh: '坏掉的' },
  ],
  sentences: [
    { start: 1.2, end: 4.5, en: "It's broken.", zh: '它坏了。', note: '句型点' },
    { start: 5.0, end: 8.0, en: 'I can fix it.', zh: '我能修好它。' },
  ],
  dialogues: [
    {
      scene: '玩具坏了',
      lines: [
        { speaker: 'parent', en: "Oh no, it's broken!", zh: '哦不，它坏了！' },
        { speaker: 'child', en: 'I can fix it!', zh: '我能修好它！' },
      ],
      tip: '拿真玩具演一遍',
    },
  ],
  guide: {
    goal: '听懂并说出 broken / fix it',
    before: ['跟孩子说:你猜车会坏在哪?'],
    during: ['视频里喊 Jump 就一起跳'],
    after: ['fix it 用英语怎么说?'],
    tips: ['broken 两个音节,别吞掉 n'],
  },
}

describe('PracticePanel 带学练习面板', () => {
  const mountPanel = (props = {}) => mount(PracticePanel, { props: { practice, ...props } })

  it('默认渲染跟读练习 Tab:单词/短句/对话三区', () => {
    const wrapper = mountPanel()

    expect(wrapper.findAll('.tab').length).toBe(2)
    expect(wrapper.findAll('.tab')[0].classes()).toContain('active')

    const chips = wrapper.findAll('.word-chip')
    expect(chips.length).toBe(2)
    expect(chips[0].find('.w-en').text()).toBe('fix it')
    expect(chips[0].find('.w-zh').text()).toBe('修好它')

    const cards = wrapper.findAll('.sentence-card')
    expect(cards.length).toBe(2)
    expect(cards[0].find('.en').text()).toBe("It's broken.")
    expect(cards[0].find('.zh').text()).toBe('它坏了。')
    expect(cards[0].text()).toContain('句型点')

    expect(wrapper.findAll('.line').length).toBe(2)
    expect(wrapper.text()).toContain('【玩具坏了】')
    expect(wrapper.text()).toContain('拿真玩具演一遍')
  })

  it('点单词 chip 触发 repeat,载荷是词块本身', async () => {
    const wrapper = mountPanel()
    await wrapper.findAll('.word-chip')[0].trigger('click')

    expect(wrapper.emitted('repeat')).toHaveLength(1)
    expect(wrapper.emitted('repeat')[0][0]).toMatchObject({
      en: 'fix it',
      zh: '修好它',
      words: [{ w: 'fix it', note: '修东西万能短语' }],
    })
  })

  it('无 note 的词块不携带 words,避免弹窗渲染空讲解', async () => {
    const wrapper = mountPanel()
    await wrapper.findAll('.word-chip')[1].trigger('click')

    const payload = wrapper.emitted('repeat')[0][0]
    expect(payload.en).toBe('broken')
    expect(payload.words).toBeUndefined()
  })

  it('点短句卡触发 repeat,时间戳按钮触发 seek 且不冒泡', async () => {
    const wrapper = mountPanel()

    await wrapper.findAll('.sentence-card')[1].trigger('click')
    expect(wrapper.emitted('repeat')).toHaveLength(1)
    expect(wrapper.emitted('repeat')[0][0]).toMatchObject({ start: 5.0, en: 'I can fix it.' })

    await wrapper.findAll('.sentence-card')[1].find('.seek-btn').trigger('click')
    expect(wrapper.emitted('seek')).toHaveLength(1)
    expect(wrapper.emitted('seek')[0][0]).toMatchObject({ start: 5.0 })
    expect(wrapper.emitted('repeat')).toHaveLength(1) // 不冒泡触发 repeat
  })

  it('时间戳按钮显示该句起始时间', () => {
    const wrapper = mountPanel()
    const btns = wrapper.findAll('.seek-btn')
    expect(btns[0].text()).toContain('0:01')
    expect(btns[1].text()).toContain('0:05')
  })

  it('每段对话一个跟读按钮,点它把整轮对话带进 repeat', async () => {
    const wrapper = mountPanel()

    const minis = wrapper.findAll('.repeat-mini')
    expect(minis.length).toBe(1) // 每段一个,不再逐行一个

    await minis[0].trigger('click')
    expect(wrapper.emitted('repeat')).toHaveLength(1)
    expect(wrapper.emitted('repeat')[0][0]).toMatchObject({
      en: "Oh no, it's broken! I can fix it!",
      zh: '哦不，它坏了！ 我能修好它！',
      segments: ["Oh no, it's broken!", 'I can fix it!'], // 逐行显式断句,弹窗不再按标点切
    })
  })

  it('点对话行文本触发朗读(jsdom 无 speechSynthesis 时静默完成)', async () => {
    const wrapper = mountPanel()
    await wrapper.findAll('.line-body')[0].trigger('click')
    // 不抛错即通过:朗读能力依赖浏览器 TTS,此处只保证交互入口安全
  })

  it('切到家长带学 Tab 渲染脚本,练习内容隐藏', async () => {
    const wrapper = mountPanel()

    await wrapper.findAll('.tab')[1].trigger('click')
    expect(wrapper.findAll('.tab')[1].classes()).toContain('active')

    expect(wrapper.find('.goal-card').text()).toContain('听懂并说出 broken / fix it')
    expect(wrapper.text()).toContain('播前')
    expect(wrapper.text()).toContain('跟孩子说:你猜车会坏在哪?')
    expect(wrapper.text()).toContain('播中')
    expect(wrapper.text()).toContain('播后')
    expect(wrapper.text()).toContain('给你的提示')
    expect(wrapper.find('.sentence-card').exists()).toBe(false)

    await wrapper.findAll('.tab')[0].trigger('click')
    expect(wrapper.find('.sentence-card').exists()).toBe(true)
  })

  it('旧格式数据(只有全量 sentences)仍渲染短句板', () => {
    const wrapper = mountPanel({
      practice: {
        sentences: [
          { start: 1, end: 2, en: 'Hello.', zh: '你好。' },
          { start: 2, end: 3, en: 'Hi.', zh: '嗨。' },
        ],
      },
    })

    expect(wrapper.findAll('.sentence-card').length).toBe(2)
    expect(wrapper.findAll('.word-chip').length).toBe(0)
  })

  it('空数据走空态提示', () => {
    const wrapper = mountPanel({ practice: {} })

    expect(wrapper.text()).toContain('本集暂无练习内容')
    expect(wrapper.find('.sentence-card').exists()).toBe(false)
  })
})
