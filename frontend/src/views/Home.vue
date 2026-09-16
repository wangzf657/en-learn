<script setup>
import { ref, computed, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { calendarApi } from '../api.js'
import { todayKey, getMonthGrid, addMonth, formatMonth } from '../utils/date.js'
import mascotUrl from '../assets/mascot.jpg'

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
  if (info && info.materialId != null) {
    router.push(`/play/${date}`)
  }
}

function isToday(date) {
  return date === todayKey()
}
</script>

<template>
  <div class="page calendar-page">

    <div v-if="error" class="error-detail">{{ error }}</div>

    <div v-if="loading" class="card empty-state">
      <p>正在加载学习日历…</p>
    </div>

    <template v-else>
      <div v-if="days.length === 0" class="card empty-state">
        <img :src="mascotUrl" alt="" class="mascot" />
        <h3>本月还没有学习任务</h3>
        <p>去后台添加视频，让学习日历充实起来吧。</p>
        <router-link to="/admin" class="btn btn-primary" style="margin-top: 20px">进入后台</router-link>
      </div>

      <div v-else class="calendar-frame">
        <div class="calendar-toolbar">
          <button class="btn btn-secondary btn-sm" @click="prevMonth">‹ 上月</button>
          <span class="calendar-month">{{ monthLabel }}</span>
          <button class="btn btn-secondary btn-sm" @click="nextMonth">下月 ›</button>
        </div>

        <div class="card calendar">
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
                'has-video': date && dayMap[date]?.materialId != null,
                checked: date && dayMap[date]?.checked,
              }"
              @click="date && goPlay(date)"
            >
              <template v-if="date">
                <div class="day-top">
                  <span class="day-number">{{ Number(date.split('-')[2]) }}</span>
                  <span v-if="dayMap[date]?.checked" class="check-mark" aria-label="已打卡">★</span>
                </div>
                <span v-if="dayMap[date]?.title" class="day-title">{{ dayMap[date].title }}</span>
                <span v-else-if="dayMap[date]?.materialId != null" class="day-hint">开始跟读</span>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.hero-title {
  display: flex;
  align-items: center;
  gap: 14px;
}

.calendar-frame {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
}

.calendar-month {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  min-width: 150px;
  text-align: center;
  color: var(--ink);
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
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}

.cell {
  min-height: 110px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  padding: 14px 10px;
  align-items: center;
  font-weight: 700;
  color: var(--muted);
  border-bottom: none;
}

.day-cell {
  cursor: default;
  transition: background var(--transition), transform var(--transition);
}

.day-cell.has-video {
  cursor: pointer;
}

.day-cell.has-video:hover {
  background: var(--blue-bg);
  transform: translateY(-2px);
}

.day-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.day-number {
  font-family: var(--font-mono);
  font-size: 15px;
  color: var(--muted);
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.is-today .day-number {
  background: var(--blue);
  color: #fff;
  box-shadow: var(--shadow-blue);
}

.day-title {
  font-size: 14px;
  line-height: 1.45;
  font-weight: 600;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.day-hint {
  font-size: 13px;
  color: var(--blue);
  font-weight: 600;
}

.check-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--yellow);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  box-shadow: 0 2px 6px rgba(255, 204, 0, 0.35);
}

.day-cell.checked {
  background: rgba(255, 204, 0, 0.08);
}

@media (max-width: 768px) {
  .hero-title {
    gap: 10px;
  }
  .cell {
    min-height: 86px;
    padding: 8px;
  }
  .day-title,
  .day-hint {
    display: none;
  }
  .day-number {
    width: 24px;
    height: 24px;
    font-size: 13px;
  }
}
</style>
