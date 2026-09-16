<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { startRecording } from '../utils/recorder.js'
import { scoringApi } from '../api.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  sentence: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close'])

const customText = ref('')
const status = ref('idle')
const result = ref(null)
const error = ref('')
const recordingController = ref(null)
const recordedUrl = ref('')
const audioEl = ref(null)
const playingRecording = ref(false)
let alive = true

const defaultText = computed(() => props.sentence?.en || '')
const reference = computed(() => customText.value.trim() || defaultText.value)

// 正在朗读的条目:'sentence' | 'words' | null
const speakingKey = ref(null)

const overallScore = computed(() => {
  if (!result.value) return 0
  const r = result.value
  return Math.round((r.accuracy_score + r.fluency_score + r.completeness_score) / 3)
})

const stars = computed(() => {
  const count = Math.min(5, Math.max(0, Math.round(overallScore.value / 20)))
  return Array.from({ length: 5 }, (_, i) => i < count)
})

function wordScoreClass(score) {
  if (score >= 80) return 'word-good'
  if (score >= 60) return 'word-ok'
  return 'word-bad'
}

function restoreSentence() {
  customText.value = defaultText.value
}

/* ---------------- 朗读(TTS) ---------------- */

function stopSpeaking() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  speakingKey.value = null
}

function makeUtterance(text, onDone) {
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'en-US'
  utter.rate = 0.9
  utter.onend = onDone
  utter.onerror = onDone
  return utter
}

function toggleSpeakSentence() {
  const key = 'sentence'
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window) || !defaultText.value) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(defaultText.value, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

// 点词块即播放该词(单条),再点一次停止
function toggleSpeakWord(w, idx) {
  const key = `w-${idx}`
  if (speakingKey.value === key) return stopSpeaking()
  if (!('speechSynthesis' in window) || !w) return
  const synth = window.speechSynthesis
  synth.cancel()
  speakingKey.value = key
  synth.speak(makeUtterance(w, () => {
    if (speakingKey.value === key) speakingKey.value = null
  }))
}

/* ---------------- 录音回放(阅后即焚) ---------------- */

function stopPlayback() {
  const a = audioEl.value
  if (a) {
    a.pause?.()
    a.currentTime = 0
  }
  playingRecording.value = false
}

function releaseRecording() {
  stopPlayback()
  if (recordedUrl.value) {
    URL.revokeObjectURL?.(recordedUrl.value)
    recordedUrl.value = ''
  }
}

function togglePlayback() {
  const a = audioEl.value
  if (!a) return
  if (playingRecording.value) {
    a.pause?.()
    playingRecording.value = false
    return
  }
  a.currentTime = 0
  playingRecording.value = true
  a.play?.()?.catch?.(() => {
    playingRecording.value = false
  })
}

function reset() {
  releaseRecording()
  customText.value = defaultText.value
  status.value = 'idle'
  result.value = null
  error.value = ''
  recordingController.value = null
}

function cleanup() {
  const controller = recordingController.value
  if (controller) {
    recordingController.value = null
    controller.stop().catch(() => {})
  }
  releaseRecording()
  stopSpeaking()
}

watch(
  () => props.open,
  (open) => {
    if (open) reset()
    else cleanup()
  },
  { immediate: true },
)

function isInput(el) {
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}

function onKeyDown(e) {
  if (!props.open) return
  if (e.key === ' ' && !e.repeat && !isInput(e.target)) {
    e.preventDefault()
    toggleRecording()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  alive = false
  window.removeEventListener('keydown', onKeyDown)
  cleanup()
})

// 切换式录音:空闲→开始,录音中→停止评分,'starting' 时再点即取消启动
function toggleRecording() {
  if (status.value === 'scoring') return
  if (status.value === 'starting') {
    status.value = 'idle'
    return
  }
  if (status.value === 'recording') return stopRecordingFlow()
  startRecordingFlow()
}

async function startRecordingFlow() {
  if (status.value === 'recording' || status.value === 'starting' || status.value === 'scoring') return
  status.value = 'starting'
  error.value = ''
  result.value = null
  try {
    const controller = await startRecording()
    // 启动期间被取消(状态已不是 starting)或组件已卸载,丢弃这次录音
    if (!alive || status.value !== 'starting') {
      try { await controller.stop() } catch {}
      return
    }
    recordingController.value = controller
    status.value = 'recording'
  } catch (e) {
    if (!alive || status.value !== 'starting') return
    recordingController.value = null
    status.value = 'error'
    error.value = e.message
  }
}

async function stopRecordingFlow() {
  const controller = recordingController.value
  if (!controller) {
    status.value = 'idle'
    return
  }
  status.value = 'scoring'
  try {
    const blob = await controller.stop()
    recordingController.value = null
    // 存下这条录音供试听;覆盖前先释放上一条
    releaseRecording()
    recordedUrl.value = URL.createObjectURL?.(blob) || ''
    const res = await scoringApi.score(blob, reference.value)
    if (!alive) return
    result.value = res
    status.value = 'result'
  } catch (e) {
    if (!alive) return
    recordingController.value = null
    status.value = 'error'
    error.value = e.detail || e.message
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <transition name='modal-fade'>
    <div v-if='open' class='repeat-modal' @click.self='close'>
      <div class='repeat-card card' role='dialog' aria-modal='true' aria-label='跟读练习'>
        <header class='repeat-header'>
          <h3><span class='header-emoji' aria-hidden='true'>🎤</span>跟读练习</h3>
          <button class='icon-btn' type='button' aria-label='关闭' @click='close'>
            <svg width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
              <path d='M18 6L6 18'/>
              <path d='M6 6l12 12'/>
            </svg>
          </button>
        </header>

        <div class='repeat-body'>
          <div class='target-section'>
            <p class='target-en'>{{ reference }}</p>
            <p v-if='sentence.zh' class='target-zh'>{{ sentence.zh }}</p>
            <div class='target-actions'>
              <button
                type='button'
                class='speak-pill'
                :class='{ speaking: speakingKey === "sentence" }'
                :title='speakingKey === "sentence" ? "停止朗读" : "朗读完整台词"'
                @click.stop='toggleSpeakSentence'
              >
                <svg v-if='speakingKey !== "sentence"' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
                  <polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'></polygon>
                  <path d='M15.54 8.46a5 5 0 0 1 0 7.07'></path>
                  <path d='M19.07 4.93a10 10 0 0 1 0 14.14'></path>
                </svg>
                <svg v-else width='14' height='14' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                  <rect x='7' y='7' width='10' height='10' rx='2'></rect>
                </svg>
                <span>{{ speakingKey === 'sentence' ? '停止' : '朗读台词' }}</span>
              </button>
            </div>
          </div>

          <div v-if='sentence.words?.length' class='word-chips'>
            <button
              v-for='(w, idx) in sentence.words'
              :key='idx'
              type='button'
              class='chip word-chip-btn'
              :class='{ speaking: speakingKey === `w-${idx}` }'
              :title='`点击播放 ${w.w}`'
              @click='toggleSpeakWord(w.w, idx)'
            >
              <span class='wc-w'>
                {{ w.w }}
                <svg class='speak-hint' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>
                  <polygon points='11 5 6 9 2 9 2 15 6 15 11 19 11 5'></polygon>
                  <path d='M15.54 8.46a5 5 0 0 1 0 7.07'></path>
                </svg>
              </span>
              <span v-if='w.phonetic' class='wc-phonetic'>/{{ w.phonetic }}/</span>
              <span v-if='w.note' class='wc-note'>{{ w.note }}</span>
            </button>
          </div>

          <div class='custom-input'>
            <div class='custom-head'>
              <label for='repeat-custom'>跟读文本</label>
              <button
                v-if='customText.trim() !== defaultText.trim()'
                type='button'
                class='restore-btn'
                @click='restoreSentence'
              >恢复台词</button>
            </div>
            <input
              id='repeat-custom'
              v-model.trim='customText'
              type='text'
              placeholder='输入想跟读的内容'
              @keydown.space.stop
            />
          </div>

          <div class='record-area'>
            <button
              class='record-btn'
              type='button'
              :class='{ recording: status === "recording", scoring: status === "scoring" }'
              :disabled='status === "scoring"'
              @click='toggleRecording'
            >
              <span v-if='status === "scoring"' class='spinner'></span>
              <span v-else-if='status === "recording"' class='rec-dot'></span>
              <svg v-else width='24' height='24' viewBox='0 0 24 24' fill='currentColor'>
                <path d='M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z'/>
                <path d='M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z'/>
              </svg>
              <span class='record-label'>
                {{ status === 'recording' ? '点击停止' : status === 'scoring' ? '评分中…' : status === 'starting' ? '准备中…' : '点击录音' }}
              </span>
            </button>
            <p class='record-hint'>按空格或点击按钮开始，再按一次结束</p>
          </div>

          <div v-if='status === "error"' class='error-detail'>{{ error }}</div>

          <div v-if='status === "result" && result' class='score-result'>
            <div class='score-stars'>
              <svg
                v-for='(filled, i) in stars'
                :key='i'
                class='star'
                :style='{ "--i": i }'
                width='26'
                height='26'
                viewBox='0 0 24 24'
                :fill='filled ? "currentColor" : "none"'
                :stroke='filled ? "none" : "currentColor"'
                stroke-width='2'
              >
                <path d='M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z'/>
              </svg>
            </div>
            <div class='score-number'>{{ overallScore }} 分</div>
            <div class='score-pills'>
              <span class='pill pill-blue'>准确度 {{ Math.round(result.accuracy_score) }}</span>
              <span class='pill pill-green'>流利度 {{ Math.round(result.fluency_score) }}</span>
              <span class='pill pill-orange'>完整度 {{ Math.round(result.completeness_score) }}</span>
            </div>
            <div class='word-scores'>
              <span
                v-for='(ws, k) in result.word_scores'
                :key='k'
                :class='["ws-word", wordScoreClass(ws.accuracy_score)]'
                :title='`分数: ${Math.round(ws.accuracy_score)}\n预期音素: ${ws.expected_phonemes || "-"}\n实际音素: ${ws.actual_phonemes || "-"}`'
              >
                {{ ws.word }}
              </span>
            </div>

            <div v-if='recordedUrl' class='playback'>
              <button
                type='button'
                class='playback-btn'
                :class='{ playing: playingRecording }'
                :title='playingRecording ? "停止回放" : "听我刚才录的音"'
                @click='togglePlayback'
              >
                <svg v-if='playingRecording' width='16' height='16' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                  <rect x='6' y='5' width='4' height='14' rx='1'></rect>
                  <rect x='14' y='5' width='4' height='14' rx='1'></rect>
                </svg>
                <svg v-else width='16' height='16' viewBox='0 0 24 24' fill='currentColor' aria-hidden='true'>
                  <path d='M8 5v14l11-7z'></path>
                </svg>
                <span>{{ playingRecording ? '停止回放' : '播放我的录音' }}</span>
              </button>
              <audio
                ref='audioEl'
                class='playback-audio'
                :src='recordedUrl'
                preload='metadata'
                @play='playingRecording = true'
                @pause='playingRecording = false'
                @ended='playingRecording = false'
                @error='playingRecording = false'
              ></audio>
            </div>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.repeat-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(43, 37, 69, 0.42);
  backdrop-filter: blur(7px);
  -webkit-backdrop-filter: blur(7px);
}

.repeat-card {
  width: 100%;
  max-width: 580px;
  max-height: calc(100svh - 48px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  border-width: 3px;
}

.repeat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: linear-gradient(120deg, var(--yellow-bg), var(--pink-bg) 55%, var(--purple-bg));
  border-bottom: 2px solid var(--border);
}

.repeat-header h3 {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
}

.header-emoji {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #fff;
  font-size: 20px;
  box-shadow: var(--shadow-sm);
  animation: wiggle 3.2s ease-in-out infinite;
}

.repeat-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.target-section {
  text-align: center;
  padding: 16px 14px;
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, var(--cyan-bg), var(--blue-bg));
  border: 2px dashed rgba(63, 140, 255, 0.35);
}

.target-en {
  font-family: var(--font-display);
  font-size: 27px;
  font-weight: 700;
  line-height: 1.4;
  margin: 0 0 8px;
  color: var(--ink);
}

.target-zh {
  font-size: 15px;
  color: var(--muted);
  margin: 0;
}

.target-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 14px;
}

.speak-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 700;
  color: var(--blue);
  background: rgba(255, 255, 255, 0.85);
  border: 2px solid rgba(63, 140, 255, 0.35);
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition), box-shadow var(--transition);
}

.speak-pill:hover {
  background: #fff;
  border-color: var(--blue);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.speak-pill:active {
  transform: translateY(1px) scale(0.96);
}

.speak-pill.speaking {
  color: #fff;
  background: var(--grad-blue);
  border-color: transparent;
  animation: speak-ring 1.1s ease-in-out infinite;
}

@keyframes speak-ring {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(63, 140, 255, 0.45);
  }
  50% {
    box-shadow: 0 0 0 7px rgba(63, 140, 255, 0);
  }
}

.word-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.word-chip-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  max-width: 100%;
  padding: 12px 16px;
  border-radius: var(--radius-xs);
  text-align: left;
  color: var(--ink);
  background: var(--purple-bg);
  border: 2px solid transparent;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition), box-shadow var(--transition);
}

.word-chip-btn:hover {
  border-color: rgba(160, 107, 255, 0.45);
  transform: translateY(-2px) rotate(-1deg);
  box-shadow: var(--shadow-sm);
}

.word-chip-btn.speaking {
  background: #fff;
  border-color: var(--purple);
  transform: translateY(-2px);
  box-shadow: 0 0 0 4px rgba(160, 107, 255, 0.18), var(--shadow-sm);
}

.wc-w {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 15px;
  font-weight: 700;
}

.speak-hint {
  flex: none;
  color: var(--purple);
  opacity: 0;
  transform: translateX(-3px);
  transition: opacity var(--transition), transform var(--transition);
}

.word-chip-btn:hover .speak-hint,
.word-chip-btn.speaking .speak-hint {
  opacity: 0.8;
  transform: none;
}

.wc-phonetic {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--purple);
}

.wc-note {
  font-size: 12px;
  line-height: 1.4;
  color: var(--muted);
}

.custom-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.custom-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.restore-btn {
  font-size: 13px;
  font-weight: 700;
  color: var(--blue);
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  transition: background var(--transition), color var(--transition);
}

.restore-btn:hover {
  background: var(--blue-bg);
}

.custom-input label {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
}

.custom-input input {
  width: 100%;
}

.record-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.record-btn {
  position: relative;
  width: 156px;
  height: 156px;
  border-radius: 50%;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  background: var(--grad-blue);
  box-shadow: var(--shadow-blue), var(--shadow-pop);
  transition: transform 180ms var(--ease-bounce), background 200ms ease, box-shadow 200ms ease;
}

/* 呼吸光环:纯装饰,不参与无障碍文本 */
.record-btn::after {
  content: '';
  position: absolute;
  inset: -12px;
  border-radius: 50%;
  border: 4px solid rgba(63, 140, 255, 0.4);
  animation: ring-pulse 2.4s ease-out infinite;
  pointer-events: none;
}

.record-btn:hover {
  transform: scale(1.04);
}

.record-btn:active {
  transform: translateY(2px) scale(0.97);
  box-shadow: var(--shadow-sm);
}

.record-btn.recording {
  background: linear-gradient(180deg, #ff8089, var(--red));
  box-shadow: 0 0 0 10px rgba(255, 95, 109, 0.16);
  animation: pulse 1.2s ease-in-out infinite;
}

.record-btn.recording::after {
  border-color: rgba(255, 95, 109, 0.5);
}

.record-btn.scoring {
  background: var(--secondary);
  box-shadow: none;
  cursor: not-allowed;
}

.record-btn.scoring::after {
  display: none;
}

.record-btn:disabled {
  cursor: not-allowed;
}

.record-btn svg {
  width: 36px;
  height: 36px;
}

.record-label {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
}

.rec-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1.2s ease-in-out infinite;
}

.record-hint {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}

.spinner {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 4px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

.score-result {
  padding: 22px 20px;
  border-radius: var(--radius-sm);
  background: linear-gradient(180deg, var(--yellow-bg), var(--orange-bg));
  border: 2px solid rgba(255, 159, 69, 0.35);
  text-align: center;
  animation: pop-in 480ms var(--ease-bounce) backwards;
}

.score-stars {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-bottom: 10px;
  color: var(--yellow);
}

.star {
  filter: drop-shadow(0 2px 3px rgba(255, 159, 69, 0.45));
  animation: star-pop 460ms var(--ease-bounce) backwards;
  animation-delay: calc(var(--i, 0) * 90ms + 120ms);
}

.score-number {
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--orange-ink);
  margin-bottom: 16px;
  animation: pop-in 460ms var(--ease-bounce) backwards;
  animation-delay: 640ms;
}

.score-pills {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}

.word-scores {
  justify-content: center;
}

/* 录音回放:藏在结果卡里的自定义播放按钮,audio 只当引擎 */
.playback {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

.playback-audio {
  display: none;
}

.playback-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 10px 20px;
  border-radius: var(--radius-pill);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(180deg, #b98bff, var(--purple));
  box-shadow: 0 14px 26px -12px rgba(160, 107, 255, 0.6), var(--shadow-pop);
  transition: transform var(--transition), box-shadow var(--transition);
}

.playback-btn:hover {
  transform: translateY(-2px);
}

.playback-btn:active {
  transform: translateY(1px) scale(0.97);
}

.playback-btn.playing {
  background: linear-gradient(180deg, #a273ff, #8a4dff);
  animation: playback-wave 1.4s ease-in-out infinite;
}

@keyframes playback-wave {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(160, 107, 255, 0.45), var(--shadow-pop);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(160, 107, 255, 0), var(--shadow-pop);
  }
}

.modal-fade-enter-active {
  transition: opacity 250ms ease;
}

.modal-fade-leave-active {
  transition: opacity 200ms ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .repeat-card {
  transition: transform 340ms var(--ease-bounce);
}

.modal-fade-leave-active .repeat-card {
  transition: transform 180ms ease;
}

.modal-fade-enter-from .repeat-card,
.modal-fade-leave-to .repeat-card {
  transform: scale(0.86) translateY(22px) rotate(-1.5deg);
}

@media (max-width: 640px) {
  .repeat-card {
    max-width: 100%;
  }
  .target-en {
    font-size: 22px;
  }
  .record-btn {
    width: 132px;
    height: 132px;
  }
  .score-number {
    font-size: 34px;
  }
}
</style>
