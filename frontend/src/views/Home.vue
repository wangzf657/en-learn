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

const checkedCount = computed(() => days.value.filter((d) => d.checked).length)

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
      <header class="hero">
        <div class="hero-mascot-wrap">
          <img :src="mascotUrl" alt="" class="hero-mascot" />
          <span class="hero-spark hero-spark-a" aria-hidden="true">✦</span>
          <span class="hero-spark hero-spark-b" aria-hidden="true">✦</span>
        </div>
        <div class="hero-text">
          <h1 class="hero-title">今天也要加油鸭！</h1>
          <p class="hero-sub">
            本月已打卡 <strong>{{ checkedCount }}</strong> 天 · 点一下有视频的日子就能开始跟读
          </p>
        </div>
        <div class="hero-stickers" aria-hidden="true">
          <span>🎧</span><span>🎈</span><span>⭐</span>
        </div>
      </header>

      <div v-if="days.length === 0" class="card empty-state">
        <img :src="mascotUrl" alt="" class="mascot" />
        <h3>本月还没有学习任务</h3>
        <p>去后台添加视频，让学习日历充实起来吧。</p>
        <router-link to="/admin" class="btn btn-primary btn-lg" style="margin-top: 22px">进入后台</router-link>
      </div>

      <div v-else class="calendar-frame">
        <div class="calendar-toolbar">
          <button class="btn btn-secondary" @click="prevMonth">‹ 上月</button>
          <span class="calendar-month">{{ monthLabel }}</span>
          <button class="btn btn-secondary" @click="nextMonth">下月 ›</button>
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
              :style="{ '--i': idx }"
              :class="{
                'is-blank': !date,
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
                <span v-if="date && isToday(date)" class="today-tag">今天</span>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ---------- 顶部问候 ---------- */
.hero {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 26px;
  margin-bottom: 24px;
  border-radius: var(--radius-card);
  border: 3px solid #fff;
  background:
    radial-gradient(circle at 88% 20%, rgba(255, 255, 255, 0.55), transparent 45%),
    linear-gradient(120deg, var(--yellow-bg), var(--pink-bg) 48%, var(--purple-bg));
  box-shadow: var(--shadow);
}

.hero-mascot-wrap {
  position: relative;
  flex: 0 0 auto;
}

.hero-mascot {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  object-fit: cover;
  border: 5px solid #fff;
  box-shadow: var(--shadow-blue);
  animation: float-y 3.4s var(--ease-soft) infinite;
}

.hero-spark {
  position: absolute;
  color: var(--pink);
  font-size: 15px;
  animation: pulse 2.2s ease-in-out infinite;
}

.hero-spark-a {
  top: -4px;
  right: 0;
}

.hero-spark-b {
  bottom: 2px;
  left: -6px;
  color: var(--purple);
  animation-delay: 0.7s;
}

.hero-text {
  flex: 1 1 auto;
  min-width: 0;
}

.hero-title {
  font-size: 30px;
  line-height: 1.25;
  background: linear-gradient(90deg, var(--blue), var(--purple) 70%, var(--pink));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-sub {
  margin: 6px 0 0;
  font-size: 16px;
  color: var(--muted);
}

.hero-sub strong {
  font-family: var(--font-display);
  font-size: 20px;
  color: var(--orange-ink);
}

.hero-stickers {
  display: flex;
  gap: 8px;
  font-size: 26px;
  flex: 0 0 auto;
}

.hero-stickers span {
  animation: float-y 3s var(--ease-soft) infinite;
}

.hero-stickers span:nth-child(2) {
  animation-delay: 0.5s;
}

.hero-stickers span:nth-child(3) {
  animation-delay: 1s;
}

/* ---------- 日历 ---------- */
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
  font-size: 24px;
  font-weight: 700;
  min-width: 170px;
  text-align: center;
  color: var(--ink);
}

.calendar {
  padding: 16px;
  overflow: hidden;
}

.calendar-head,
.calendar-body {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
}

.calendar-head {
  margin-bottom: 8px;
}

.cell {
  min-height: 112px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-radius: var(--radius-sm);
  position: relative;
}

.header-cell {
  min-height: auto;
  padding: 10px;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  color: var(--purple);
  background: var(--purple-bg);
  border-radius: var(--radius-pill);
}

.day-cell {
  background: var(--bg);
  border: 2px solid transparent;
  cursor: default;
  transition: transform 200ms var(--ease-bounce), background 200ms ease,
    box-shadow 200ms ease, border-color 200ms ease;
}

.day-cell.is-blank {
  background: transparent;
}

.day-cell.has-video {
  cursor: pointer;
  background: var(--blue-bg);
  border-color: rgba(63, 140, 255, 0.35);
  animation: pop-in 420ms var(--ease-bounce) backwards;
  animation-delay: calc(var(--i, 0) * 16ms);
}

.day-cell.has-video:hover {
  transform: translateY(-4px) scale(1.03) rotate(-1deg);
  background: #d8ebff;
  box-shadow: var(--shadow), var(--shadow-pop);
}

.day-cell.has-video:active {
  transform: translateY(1px) scale(0.98);
  box-shadow: var(--shadow-sm);
}

.day-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.day-number {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--muted);
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.is-today .day-number {
  background: linear-gradient(160deg, var(--pink), var(--red));
  color: #fff;
  box-shadow: 0 8px 16px -6px rgba(255, 95, 109, 0.6);
}

.day-title {
  font-size: 14px;
  line-height: 1.4;
  font-weight: 700;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.day-hint {
  font-size: 13px;
  color: var(--blue);
  font-weight: 700;
}

.check-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: linear-gradient(160deg, var(--yellow), var(--orange));
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
  box-shadow: 0 4px 10px rgba(255, 159, 69, 0.45);
  animation: star-pop 500ms var(--ease-bounce) backwards;
}

.day-cell.checked {
  background: linear-gradient(180deg, var(--yellow-bg), var(--orange-bg));
  border-color: rgba(255, 159, 69, 0.4);
}

.today-tag {
  margin-top: auto;
  align-self: flex-start;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  background: var(--pink);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

@media (max-width: 768px) {
  .hero {
    flex-wrap: wrap;
    padding: 16px 18px;
    gap: 12px;
  }
  .hero-mascot {
    width: 62px;
    height: 62px;
    border-width: 4px;
  }
  .hero-title {
    font-size: 22px;
  }
  .hero-stickers {
    display: none;
  }
  .calendar {
    padding: 8px;
  }
  .calendar-head,
  .calendar-body {
    gap: 5px;
  }
  .cell {
    min-height: 66px;
    padding: 6px;
    border-radius: var(--radius-xs);
  }
  .day-title,
  .day-hint,
  .today-tag {
    display: none;
  }
  .day-number {
    width: 26px;
    height: 26px;
    font-size: 14px;
  }
  .check-mark {
    width: 18px;
    height: 18px;
    font-size: 10px;
  }
}
</style>
