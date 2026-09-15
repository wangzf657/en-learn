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
      <h1 class="page-title">{{ day?.title || date }}</h1>
      <span v-if="checkedIn" class="checked-badge">已打卡</span>
      <span v-else class="unchecked-badge">未打卡</span>
    </header>

    <div v-if="loading" class="empty-state">加载中…</div>

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
            <span v-if="playing">❚❚</span>
            <span v-else>▶</span>
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
            <label for="volume">音量</label>
            <input id="volume" type="range" min="0" max="1" step="0.05" v-model.number="volume" @input="setVolume" />
          </div>
        </div>
      </section>

      <section class="panel-section card">
        <h2 class="panel-title">今日台词</h2>
        <div v-if="sentences.length === 0" class="empty-state" style="padding: 40px 20px">
          暂无字幕数据
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
            <p class="en">{{ s.en }}</p>
            <p v-if="s.zh" class="zh">{{ s.zh }}</p>
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
                <span v-if="scoreState(i).status === 'recording'">停止</span>
                <span v-else-if="scoreState(i).status === 'scoring'">评分中…</span>
                <span v-else-if="scoreState(i).result">重新跟读</span>
                <span v-else>跟读</span>
              </button>
            </div>

            <div v-if="scoreState(i).error" class="error-detail score-error">{{ scoreState(i).error }}</div>

            <div v-if="scoreState(i).result" class="score-detail">
              <div class="score-pills">
                <span class="pill">准确度 {{ Math.round(scoreState(i).result.accuracy_score) }}</span>
                <span class="pill">流利度 {{ Math.round(scoreState(i).result.fluency_score) }}</span>
                <span class="pill">完整度 {{ Math.round(scoreState(i).result.completeness_score) }}</span>
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
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.play-page {
  padding-top: 28px;
}

.play-page .page-header {
  align-items: baseline;
}

.checked-badge,
.unchecked-badge {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}

.checked-badge {
  background: var(--sage-bg);
  color: var(--sage);
}

.unchecked-badge {
  background: var(--paper-2);
  color: var(--ink-light);
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}

.video-section {
  position: sticky;
  top: 24px;
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
  gap: 14px;
  padding: 14px 18px;
  background: var(--paper-2);
}

.play-btn {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.play-btn:hover {
  background: var(--accent-hover);
}

.progress-area {
  flex: 1 1 auto;
  min-width: 0;
}

.progress-track {
  position: relative;
  height: 8px;
  background: var(--paper-3);
  border-radius: 4px;
  cursor: pointer;
}

.progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--accent);
  border-radius: 4px;
  pointer-events: none;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 16px;
  height: 16px;
  margin-top: -8px;
  margin-left: -8px;
  background: #fff;
  border: 2px solid var(--accent);
  border-radius: 50%;
  pointer-events: none;
}

.time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.time {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--ink-light);
}

.rate-btn {
  padding: 4px 10px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--accent);
}

.volume-area {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-light);
}

.volume-area input[type='range'] {
  width: 90px;
  padding: 0;
}

.panel-section {
  padding: 20px 22px;
  max-height: calc(100svh - 160px);
  overflow-y: auto;
}

.panel-title {
  font-size: 22px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.sentence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sentence-card {
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--paper);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}

.sentence-card:hover {
  border-color: var(--accent);
  transform: translateX(4px);
}

.sentence-card.active {
  background: var(--highlight);
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.en {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
  margin: 0 0 6px;
}

.zh {
  font-size: 14px;
  color: var(--ink-light);
  margin: 0 0 10px;
}

.words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.word-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  border-radius: 8px;
  background: var(--paper-2);
  border: 1px solid var(--border);
  font-size: 13px;
}

.word-chip .w {
  font-weight: 600;
  color: var(--ink);
}

.word-chip .phonetic {
  font-family: var(--font-mono);
  color: var(--sage);
  font-size: 12px;
}

.word-chip .note {
  color: var(--ink-light);
  font-size: 12px;
  line-height: 1.4;
}

.repeat-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.repeat-btn {
  min-width: 80px;
}

.repeat-btn.recording {
  animation: pulse 1.2s ease-in-out infinite;
  background: var(--accent-bg);
  color: var(--accent);
  border: 1px solid var(--accent);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.score-error {
  margin-top: 10px;
}

.score-detail {
  margin-top: 12px;
  padding: 14px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
}

.score-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  background: var(--paper-2);
  color: var(--ink);
}

.word-scores {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 1.6;
}

.ws-word {
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: help;
}

.word-good {
  background: var(--sage-bg);
  color: var(--sage);
}

.word-ok {
  background: #fff8e1;
  color: #9a6d00;
}

.word-bad {
  background: var(--accent-bg);
  color: var(--accent);
}

.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  transform: translateX(-50%);
  padding: 10px 22px;
  border-radius: 999px;
  background: var(--ink);
  color: #fff;
  font-size: 14px;
  box-shadow: var(--shadow);
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
    gap: 10px;
  }
  .volume-area {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
