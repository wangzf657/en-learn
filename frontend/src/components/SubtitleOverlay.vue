<script setup>
import { computed } from 'vue'

const props = defineProps({
  cues: { type: Array, default: () => [] },
  currentTime: { type: Number, default: 0 },
  enabled: { type: Boolean, default: true },
  styleClass: { type: String, default: 'sub-clean' },
})

const currentCue = computed(() => {
  if (!props.enabled || !props.cues.length) return null
  const t = props.currentTime || 0
  return props.cues.find((c) => t >= c.start && t < c.end) || null
})
</script>

<template>
  <div class="subtitle-overlay" :class="[styleClass, { 'sub-off': !enabled }]" aria-live="polite">
    <Transition name="cue" mode="out-in">
      <p v-if="currentCue" :key="currentCue.text" class="subtitle-cue">{{ currentCue.text }}</p>
    </Transition>
  </div>
</template>

<!-- 全局样式:字幕类名由父组件动态指定,需要跨组件作用域 -->
<style>
.subtitle-overlay {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: 92%;
  text-align: center;
  pointer-events: none;
  z-index: 5;
  min-height: 2em;
}

.subtitle-cue {
  display: inline-block;
  margin: 0;
  padding: 0.4em 0.85em;
  border-radius: 0.75em;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.45;
  white-space: pre-wrap;
}

/* 清晰:白字 + 重描边式阴影,不挡画面也能读清 */
.sub-clean .subtitle-cue {
  color: #fff;
  text-shadow:
    0 2px 4px rgba(0, 0, 0, 0.85),
    0 0 8px rgba(0, 0, 0, 0.65);
}

/* 影院:黄色大字,情绪更足 */
.sub-cinema .subtitle-cue {
  color: #ffe25a;
  font-family: var(--font-display);
  font-size: 25px;
  letter-spacing: 0.01em;
  text-shadow:
    0 2px 5px rgba(0, 0, 0, 0.92),
    0 0 10px rgba(0, 0, 0, 0.7);
}

/* 黑底:圆角色块,读得最省力 */
.sub-opaque .subtitle-cue {
  color: #fff;
  background: rgba(22, 16, 43, 0.78);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  padding: 0.45em 1em;
}

.sub-off .subtitle-cue {
  display: none;
}

/* 台词切换:只做入场(淡入上浮) */
.cue-enter-active {
  transition: opacity 200ms ease, transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.cue-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.96);
}

/*
  刻意不写 .cue-leave-active / -to:
  容器宽度由在流内容决定(width: max-content),离场元素一旦脱离文档流,
  句间间隙时容器会塌缩到 ~0 宽,旧字幕被逐字挤成竖排。
  不声明离场过渡 → Vue 判定无过渡,旧句同帧立即移除,间隙就是干净空白;
  配合 mode="out-in" 保证新旧字幕绝不共存,容器宽度永不被求和/塌缩。
  !!! 不要为 .cue-* 添加 leave 过渡,除非离场元素能拿到与在流时一致的宽度 !!!
*/

@media (max-width: 640px) {
  .subtitle-cue {
    font-size: 17px;
  }
  .sub-cinema .subtitle-cue {
    font-size: 20px;
  }
}
</style>
