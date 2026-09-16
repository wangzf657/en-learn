<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { startRecording } from '../utils/recorder.js'
import { scoringApi } from '../api.js'

const props = defineProps({
  open: { type: Boolean, default: false },
  sentence: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close', 'result', 'error'])

const selectedWord = ref(null)
const customText = ref('')
const status = ref('idle')
const result = ref(null)
const error = ref('')
const recordingController = ref(null)
const wantRecording = ref(false)
let alive = true

const reference = computed(() => {
  const c = customText.value.trim()
  if (c) return c
  if (selectedWord.value) return selectedWord.value
  return props.sentence?.en || ''
})

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

function selectWord(w) {
  if (selectedWord.value === w) {
    selectedWord.value = null
  } else {
    selectedWord.value = w
    customText.value = ''
  }
}

function reset() {
  selectedWord.value = null
  customText.value = ''
  status.value = 'idle'
  result.value = null
  error.value = ''
  wantRecording.value = false
  recordingController.value = null
}

function cleanup() {
  wantRecording.value = false
  const controller = recordingController.value
  if (controller) {
    recordingController.value = null
    controller.stop().catch(() => {})
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) reset()
    else cleanup()
  },
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
    startRecordingFlow()
  }
}

function onKeyUp(e) {
  if (!props.open) return
  if (e.key === ' ' && !isInput(e.target)) {
    e.preventDefault()
    stopRecordingFlow()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})

onBeforeUnmount(() => {
  alive = false
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  cleanup()
})

async function startRecordingFlow() {
  if (status.value === 'recording' || status.value === 'starting' || status.value === 'scoring') return
  wantRecording.value = true
  status.value = 'starting'
  error.value = ''
  result.value = null
  try {
    const controller = await startRecording()
    if (!alive) {
      try { await controller.stop() } catch {}
      return
    }
    recordingController.value = controller
    if (!wantRecording.value) {
      status.value = 'idle'
      recordingController.value = null
      try { await controller.stop() } catch {}
      return
    }
    status.value = 'recording'
  } catch (e) {
    if (!alive) return
    recordingController.value = null
    status.value = 'error'
    error.value = e.message
    emit('error', e.message)
    wantRecording.value = false
  }
}

async function stopRecordingFlow() {
  wantRecording.value = false
  const controller = recordingController.value
  if (!controller) {
    if (status.value === 'starting') status.value = 'idle'
    return
  }
  status.value = 'scoring'
  try {
    const blob = await controller.stop()
    recordingController.value = null
    const res = await scoringApi.score(blob, reference.value)
    if (!alive) return
    result.value = res
    status.value = 'result'
    emit('result', res)
  } catch (e) {
    if (!alive) return
    recordingController.value = null
    status.value = 'error'
    error.value = e.detail || e.message
    emit('error', e.detail || e.message)
  }
}

function onPointerDown(e) {
  e.preventDefault()
  startRecordingFlow()
}

function onPointerUp(e) {
  e.preventDefault()
  stopRecordingFlow()
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
          </div>

          <div v-if='sentence.words?.length' class='word-chips'>
            <button
              v-for='(w, idx) in sentence.words'
              :key='idx'
              type='button'
              class='chip word-chip-btn'
              :class='{ active: selectedWord === w.w }'
              @click='selectWord(w.w)'
            >
              {{ w.w }}
            </button>
          </div>

          <div class='custom-input'>
            <label for='repeat-custom'>自定义跟读文本</label>
            <input
              id='repeat-custom'
              v-model.trim='customText'
              type='text'
              placeholder='输入想跟读的内容，会覆盖默认台词'
              @keydown.space.stop
            />
          </div>

          <div class='record-area'>
            <button
              class='record-btn'
              type='button'
              :class='{ recording: status === "recording", scoring: status === "scoring" }'
              :disabled='status === "scoring"'
              @pointerdown='onPointerDown'
              @pointerup='onPointerUp'
              @pointercancel='onPointerUp'
              @pointerleave='onPointerUp'
            >
              <span v-if='status === "scoring"' class='spinner'></span>
              <span v-else-if='status === "recording"' class='rec-dot'></span>
              <svg v-else width='24' height='24' viewBox='0 0 24 24' fill='currentColor'>
                <path d='M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z'/>
                <path d='M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z'/>
              </svg>
              <span class='record-label'>
                {{ status === 'recording' ? '松开停止' : status === 'scoring' ? '评分中…' : '按住录音' }}
              </span>
            </button>
            <p class='record-hint'>按住空格或按住按钮录音</p>
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

.word-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.word-chip-btn {
  padding: 9px 16px;
  min-height: 44px;
  border-radius: var(--radius-pill);
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  background: var(--card);
  border: 2px solid var(--border);
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    border-color var(--transition), transform var(--transition);
}

.word-chip-btn:hover {
  border-color: var(--blue);
  color: var(--blue);
  transform: translateY(-2px);
}

.word-chip-btn.active {
  background: var(--grad-blue);
  color: #fff;
  border-color: transparent;
  transform: translateY(-2px);
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.custom-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  touch-action: none;
  user-select: none;
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
