<script setup>
import { computed, watch, ref } from 'vue'

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
    <p v-if="currentCue" class="subtitle-cue">{{ currentCue.text }}</p>
  </div>
</template>

<style>
.subtitle-overlay {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 90%;
  text-align: center;
  pointer-events: none;
  z-index: 5;
  min-height: 2em;
}

.subtitle-cue {
  display: inline-block;
  margin: 0;
  padding: 0.35em 0.75em;
  border-radius: 0.4em;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.45;
  white-space: pre-wrap;
}

.sub-clean .subtitle-cue {
  color: #fff;
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.8),
    0 0 4px rgba(0, 0, 0, 0.6);
}

.sub-cinema .subtitle-cue {
  color: #ffeb3b;
  font-size: 22px;
  text-shadow:
    0 1px 3px rgba(0, 0, 0, 0.9),
    0 0 6px rgba(0, 0, 0, 0.7);
}

.sub-opaque .subtitle-cue {
  color: #fff;
  background: rgba(0, 0, 0, 0.72);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
}

.sub-off .subtitle-cue {
  display: none;
}
</style>
