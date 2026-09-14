<script setup>
import { ref, computed, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { calendarApi } from '../api.js'
import { todayKey, getMonthGrid, addMonth, formatMonth } from '../utils/date.js'

const router = useRouter()

const now = new Date()
const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const days = ref([])
const loading = ref(false)
const error = ref('')

const monthLabel = computed(() => {
  return `${year.value} 年 ${month.value} 月`
})

const weekHeaders = ['一', '二', '三', '四', '五', '六', '日']
const cells = computed(() => getMonthGrid(year.value, month.value))

const dayMap = computed(() => {
  const map = {}
  for (const d of days.value) {
    map[d.date] = d
  }
  return map
})

watchEffect(async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await calendarApi.getMonth(formatMonth(year.value, month.value))
    days.value = res.days || []
  } catch (e) {
    error.value = e.detail || e.message
    days.value = []
  } finally {
    loading.value = false
  }
})

function prevMonth() {
  const n = addMonth(year.value, month.value, -1)
  year.value = n.year
  month.value = n.month
}

function nextMonth() {
  const n = addMonth(year.value, month.value, 1)
  year.value = n.year
  month.value = n.month
}

function goPlay(date) {
  const info = dayMap.value[date]
  if (info && info.videoId != null) {
    router.push(`/play/${date}`)
  }
}

function isToday(date) {
  return date === todayKey()
}
</script>

<template>
  <div class="page calendar-page">
    <header class="page-header">
      <h1 class="page-title">每日英语</h1>
      <router-link to="/admin" class="icon-btn settings" title="后台管理">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </router-link>
    </header>

    <div class="calendar-toolbar">
      <button class="btn btn-secondary btn-sm" @click="prevMonth">‹ 上月</button>
      <span class="calendar-month">{{ monthLabel }}</span>
      <button class="btn btn-secondary btn-sm" @click="nextMonth">下月 ›</button>
    </div>

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-if="loading" class="empty-state">加载中…</div>

    <template v-else>
      <div v-if="days.length === 0" class="card empty-state">
        <h3>本月还没有学习任务</h3>
        <p>去后台添加视频，让学习日历充实起来吧。</p>
        <router-link to="/admin" class="btn btn-primary" style="margin-top: 20px">进入后台</router-link>
      </div>

      <div v-else class="card calendar">
        <div class="calendar-head">
          <div v-for="h in weekHeaders" :key="h" class="cell header-cell">{{ h }}</div>
        </div>
        <div class="calendar-body">
          <div
            v-for="(date, idx) in cells"
            :key="idx"
            class="cell day-cell"
            :class="{
              'is-today': date && isToday(date),
              'has-video': date && dayMap[date]?.videoId != null,
              checked: date && dayMap[date]?.checked,
            }"
            @click="date && goPlay(date)"
          >
            <template v-if="date">
              <span class="day-number">{{ Number(date.split('-')[2]) }}</span>
              <span v-if="dayMap[date]?.title" class="day-title">{{ dayMap[date].title }}</span>
              <span v-if="dayMap[date]?.checked" class="check-mark" aria-label="已打卡">✓</span>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-bottom: 24px;
}

.calendar-month {
  font-family: var(--font-display);
  font-size: 22px;
  min-width: 140px;
  text-align: center;
}

.calendar {
  overflow: hidden;
}

.calendar-head,
.calendar-body {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}

.calendar-head {
  background: var(--paper-2);
  border-bottom: 1px solid var(--border);
}

.cell {
  min-height: 96px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.cell:nth-child(7n) {
  border-right: none;
}

.calendar-body .cell:nth-last-child(-n+7) {
  border-bottom: none;
}

.header-cell {
  min-height: auto;
  padding: 12px 10px;
  align-items: center;
  font-weight: 700;
  color: var(--ink-light);
  border-bottom: none;
}

.day-cell {
  cursor: default;
  transition: background 0.15s;
}

.day-cell.has-video {
  cursor: pointer;
}

.day-cell.has-video:hover {
  background: #fffaf5;
}

.day-number {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--ink-light);
}

.is-today .day-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
}

.day-title {
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.check-mark {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--sage-bg);
  color: var(--sage);
  font-size: 12px;
  font-weight: 700;
}

.day-cell.checked {
  background: rgba(109, 127, 110, 0.06);
}

.settings {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 10;
}

@media (max-width: 768px) {
  .cell {
    min-height: 74px;
    padding: 6px;
  }
  .day-title {
    display: none;
  }
  .settings {
    top: 12px;
    right: 12px;
  }
}
</style>
