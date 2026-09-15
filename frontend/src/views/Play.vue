<script setup>
import { ref, computed, watch, reactive, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { dayApi, scoringApi } from '../api.js'
import { startRecording } from '../utils/recorder.js'

const props = defineProps({ date: String })
const router = useRouter()

const day = ref(null)
const loading = ref(true)
const error = ref('')
const checkedIn = ref(false)
const checkinSent = ref(false)
const toast = ref('')

const videoEl = ref(null)
const progressEl = ref(null)
const sentenceRefs = ref([])

const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const volume = ref(1)
const playbackRate = ref(1)
const rates = [0.5, 0.75, 1, 1.25, 1.5, 2]

const sentences = computed(() => day.value?.subtitle?.sentences || [])
const scoreMap = ref(new Map())
let recordingController = null

watch(
  sentences,
  (list) => {
    list.forEach((_, i) => {
      if (!scoreMap.value.has(i)) {
        scoreMap.value.set(i, reactive({ status: 'idle', result: null, error: '' }))
      }
    })
  },
  { immediate: true },
)

function scoreState(i) {
  return scoreMap.value.get(i) || { status: 'idle', result: null, error: '' }
}

async function startRepeat(i) {
  if (recordingController) {
    try { await recordingController.stop() } catch {}
    recordingController = null
  }
  const state = scoreState(i)
  state.error = ''
  state.result = null
  state.status = 'recording'
  videoEl.value?.pause()
  try {
    recordingController = await startRecording()
  } catch (e) {
    state.status = 'idle'
    state.error = e.message
  }
}

async function stopRepeat(i, reference) {
  const state = scoreState(i)
  if (!recordingController) {
    state.status = 'idle'
    return
  }
  state.status = 'scoring'
  try {
    const blob = await recordingController.stop()
    recordingController = null
    const result = await scoringApi.score(blob, reference)
    state.result = result
    state.status = 'result'
  } catch (e) {
    state.status = 'idle'
    state.error = e.detail || e.message
  }
}

function toggleRepeat(i, s) {
  if (scoreState(i).status === 'recording') {
    stopRepeat(i, s.en)
  } else {
    startRepeat(i)
  }
}

function wordScoreClass(score) {
  if (score >= 80) return 'word-good'
  if (score >= 60) return 'word-ok'
  return 'word-bad'
}

const currentIndex = computed(() => {
  const list = sentences.value
  if (!list.length) return -1
  const t = currentTime.value
  for (let i = 0; i < list.length; i++) {
    if (t >= list[i].start && t < list[i].end) return i
  }
  if (t >= list[list.length - 1].end) return list.length - 1
  return -1
})

const progressPercent = computed(() => {
  if (!duration.value) return 0
  return Math.min(100, Math.max(0, (currentTime.value / duration.value) * 100))
})

watch(currentIndex, (next, prev) => {
  if (next !== prev && next >= 0 && sentenceRefs.value[next]) {
    sentenceRefs.value[next].scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
})

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await dayApi.get(props.date)
    day.value = data
    checkedIn.value = !!data.checked
  } catch (e) {
    error.value = e.detail || e.message
    day.value = null
  } finally {
    loading.value = false
  }
}

function togglePlay() {
  const v = videoEl.value
  if (!v) return
  if (v.paused) v.play()
  else v.pause()
}

function onTimeUpdate() {
  const v = videoEl.value
  if (!v) return
  currentTime.value = v.currentTime
  if (v.duration && !isNaN(v.duration)) duration.value = v.duration
  if (!checkinSent.value && !checkedIn.value && v.duration) {
    if (v.currentTime / v.duration >= 0.9) {
      doCheckin()
    }
  }
}

function onLoadedMetadata() {
  const v = videoEl.value
  if (v && !isNaN(v.duration)) duration.value = v.duration
}

function onEnded() {
  playing.value = false
  if (!checkinSent.value && !checkedIn.value) {
    doCheckin()
  }
}

async function doCheckin() {
  checkinSent.value = true
  try {
    await dayApi.checkin(props.date)
    checkedIn.value = true
    toast.value = '今日已打卡'
    setTimeout(() => (toast.value = ''), 2200)
  } catch (e) {
    checkinSent.value = false
  }
}

function seekToRatio(ratio) {
  const v = videoEl.value
  if (!v || !duration.value) return
  const t = Math.max(0, Math.min(duration.value, ratio * duration.value))
  v.currentTime = t
  currentTime.value = t
}

function seekFromEvent(e) {
  if (!progressEl.value || !duration.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  seekToRatio(ratio)
}

const dragging = ref(false)
function startDrag(e) {
  dragging.value = true
  seekFromEvent(e)
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
}
function onDrag(e) {
  if (!dragging.value) return
  seekFromEvent(e)
}
function stopDrag() {
  dragging.value = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
}

function cycleRate() {
  const v = videoEl.value
  if (!v) return
  let i = rates.indexOf(playbackRate.value)
  if (i < 0) i = 1
  const next = rates[(i + 1) % rates.length]
  playbackRate.value = next
  v.playbackRate = next
}

function setVolume() {
  const v = videoEl.value
  if (v) v.volume = volume.value
}

function seekToSentence(s) {
  const v = videoEl.value
  if (!v) return
  v.currentTime = s.start
  currentTime.value = s.start
  v.play()
}

function formatTime(s) {
  if (!s && s !== 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

onBeforeUnmount(() => {
  const v = videoEl.value
  if (v) v.pause()
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  if (recordingController) {
    recordingController.stop().catch(() => {})
    recordingController = null
  }
})
</script>

<template>
  <div class="page play-page">
    <header class="page-header">
      <button class="btn btn-ghost btn-sm" @click="$router.push('/')">‹ 返回日历</button>
      <div class="title-group">
        <h1 class="page-title">{{ day?.title || date }}</h1>
        <span v-if="checkedIn" class="badge badge-blue">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          已打卡
        </span>
        <span v-else class="badge badge-yellow">未打卡</span>
      </div>
    </header>

    <div v-if="loading" class="card empty-state">
      <p>正在加载学习内容…</p>
    </div>

    <div v-else-if="error" class="card empty-state">
      <h3>{{ error }}</h3>
      <button class="btn btn-primary" style="margin-top: 16px" @click="router.push('/')">回日历</button>
    </div>

    <div v-else class="play-layout">
      <section class="video-section card">
        <div class="video-wrap">
          <video
            ref="videoEl"
            :src="day.videoUrl"
            preload="metadata"
            @timeupdate="onTimeUpdate"
            @loadedmetadata="onLoadedMetadata"
            @play="playing = true"
            @pause="playing = false"
            @ended="onEnded"
          ></video>
        </div>

        <div class="controls">
          <button class="play-btn" @click="togglePlay" :aria-label="playing ? '暂停' : '播放'">
            <svg v-if="playing" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" /><rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>

          <div class="progress-area">
            <div
              ref="progressEl"
              class="progress-track"
              @click="seekFromEvent"
              @mousedown="startDrag"
            >
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
              <div class="progress-thumb" :style="{ left: progressPercent + '%' }"></div>
            </div>
            <div class="time-row">
              <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
              <button class="rate-btn" @click="cycleRate" title="切换倍速">{{ playbackRate }}×</button>
            </div>
          </div>

          <div class="volume-area">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
              <path v-if="volume > 0" d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              <path v-if="volume > 0.5" d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
            </svg>
            <input id="volume" type="range" min="0" max="1" step="0.05" v-model.number="volume" @input="setVolume" />
          </div>
        </div>
      </section>

      <section class="panel-section card">
        <h2 class="panel-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
          </svg>
          今日台词
        </h2>
        <div v-if="sentences.length === 0" class="empty-state" style="padding: 40px 20px">
          <p>暂无字幕数据</p>
        </div>
        <div v-else class="sentence-list">
          <div
            v-for="(s, i) in sentences"
            :key="i"
            ref="sentenceRefs"
            class="sentence-card"
            :class="{ active: i === currentIndex }"
            @click="seekToSentence(s)"
          >
            <div class="sentence-main">
              <p class="en">{{ s.en }}</p>
              <p v-if="s.zh" class="zh">{{ s.zh }}</p>
            </div>

            <div v-if="s.words?.length" class="words">
              <div v-for="(w, j) in s.words" :key="j" class="word-chip">
                <span class="w">{{ w.w }}</span>
                <span v-if="w.phonetic" class="phonetic">/{{ w.phonetic }}/</span>
                <span v-if="w.note" class="note">{{ w.note }}</span>
              </div>
            </div>

            <div class="repeat-row">
              <button
                class="btn btn-sm repeat-btn"
                :class="scoreState(i).status === 'recording' ? 'btn-secondary recording' : 'btn-primary'"
                :disabled="scoreState(i).status === 'scoring'"
                @click.stop="toggleRepeat(i, s)"
              >
                <svg v-if="scoreState(i).status === 'recording'" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/></svg>
                <svg v-else-if="scoreState(i).status === 'scoring'" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8Z" opacity=".4"/><path d="M12 6v6l4 2"/></svg>
                <svg v-else-if="scoreState(i).result" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
                <span v-if="scoreState(i).status === 'recording'">停止录音</span>
                <span v-else-if="scoreState(i).status === 'scoring'">评分中…</span>
                <span v-else-if="scoreState(i).result">重新跟读</span>
                <span v-else>跟读一下</span>
              </button>
            </div>

            <div v-if="scoreState(i).error" class="error-detail score-error">{{ scoreState(i).error }}</div>

            <div v-if="scoreState(i).result" class="score-detail">
              <div class="score-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
                <span>本次得分</span>
              </div>
              <div class="score-pills">
                <span class="pill pill-blue">准确度 {{ Math.round(scoreState(i).result.accuracy_score) }}</span>
                <span class="pill pill-green">流利度 {{ Math.round(scoreState(i).result.fluency_score) }}</span>
                <span class="pill pill-orange">完整度 {{ Math.round(scoreState(i).result.completeness_score) }}</span>
              </div>
              <div class="word-scores">
                <span
                  v-for="(ws, k) in scoreState(i).result.word_scores"
                  :key="k"
                  :class="['ws-word', wordScoreClass(ws.accuracy_score)]"
                  :title="`分数: ${Math.round(ws.accuracy_score)}\n预期音素: ${ws.expected_phonemes || '-'}\n实际音素: ${ws.actual_phonemes || '-'}`"
                >
                  {{ ws.word }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <transition name="fade">
      <div v-if="toast" class="toast">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<style scoped>
.play-page {
  padding-top: 20px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.video-section {
  position: sticky;
  top: 84px;
  padding: 0;
  overflow: hidden;
}

.video-wrap {
  background: #000;
  aspect-ratio: 16 / 9;
  display: flex;
  align-items: center;
  justify-content: center;
}

video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.controls {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--bg);
}

.play-btn {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--blue);
  color: #fff;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-blue);
  transition: transform var(--transition), background var(--transition);
}

.play-btn:hover {
  background: var(--blue-hover);
  transform: scale(1.05);
}

.play-btn:active {
  transform: scale(0.98);
}

.progress-area {
  flex: 1 1 auto;
  min-width: 0;
}

.progress-track {
  position: relative;
  height: 10px;
  background: var(--border);
  border-radius: 999px;
  cursor: pointer;
}

.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--blue);
  border-radius: 999px;
  pointer-events: none;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 18px;
  height: 18px;
  margin-top: -9px;
  margin-left: -9px;
  background: #fff;
  border: 3px solid var(--blue);
  border-radius: 50%;
  pointer-events: none;
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.35);
}

.time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}

.time {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--muted);
}

.rate-btn {
  padding: 5px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--blue);
  transition: border-color var(--transition), background var(--transition);
}

.rate-btn:hover {
  border-color: var(--blue);
  background: var(--blue-bg);
}

.volume-area {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--muted);
}

.volume-area input[type='range'] {
  width: 100px;
  padding: 0;
  min-height: auto;
  accent-color: var(--blue);
}

.panel-section {
  padding: 22px 24px;
  max-height: calc(100svh - 160px);
  overflow-y: auto;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  color: var(--ink);
}

.sentence-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sentence-card {
  padding: 18px 20px;
  border-radius: var(--radius-card);
  border: 1px solid var(--border);
  background: var(--card);
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition), transform var(--transition);
}

.sentence-card:hover {
  border-color: var(--blue);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.sentence-card.active {
  background: var(--blue-bg);
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.12);
}

.sentence-main {
  margin-bottom: 10px;
}

.en {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
  margin: 0 0 6px;
  color: var(--ink);
}

.zh {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.word-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 13px;
}

.word-chip .w {
  font-weight: 600;
  color: var(--ink);
}

.word-chip .phonetic {
  font-family: var(--font-mono);
  color: var(--blue);
  font-size: 12px;
}

.word-chip .note {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}

.repeat-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.repeat-btn {
  min-width: 100px;
}

.repeat-btn.recording {
  animation: pulse 1.2s ease-in-out infinite;
  background: var(--red-bg);
  color: var(--red);
  border: 1px solid var(--red);
  box-shadow: none;
}

.score-error {
  margin-top: 12px;
}

.score-detail {
  margin-top: 14px;
  padding: 16px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}

.score-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-weight: 700;
  color: var(--yellow);
}

.score-header svg {
  color: var(--yellow);
  filter: drop-shadow(0 1px 2px rgba(255, 204, 0, 0.35));
}

.score-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.pill {
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
}

.pill-blue {
  background: var(--blue-bg);
  color: var(--blue);
}

.pill-green {
  background: var(--green-bg);
  color: var(--green);
}

.pill-orange {
  background: var(--orange-bg);
  color: #c46a00;
}

.word-scores {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.6;
}

.ws-word {
  padding: 4px 10px;
  border-radius: var(--radius-xs);
  font-size: 14px;
  font-weight: 600;
  cursor: help;
}

.word-good {
  background: var(--green-bg);
  color: var(--green);
}

.word-ok {
  background: var(--yellow-bg);
  color: #a67c00;
}

.word-bad {
  background: var(--red-bg);
  color: var(--red);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: var(--radius-pill);
  background: var(--ink);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow);
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.toast svg {
  color: var(--yellow);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}

@media (max-width: 1024px) {
  .play-layout {
    grid-template-columns: 1fr;
  }
  .video-section {
    position: static;
  }
  .panel-section {
    max-height: none;
  }
}

@media (max-width: 640px) {
  .controls {
    flex-wrap: wrap;
    gap: 12px;
  }
  .volume-area {
    width: 100%;
    justify-content: flex-end;
  }
  .title-group {
    width: 100%;
  }
}
</style>
