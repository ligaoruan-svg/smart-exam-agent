<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: Number, default: 32 },
  showText: { type: Boolean, default: true }
})

const imgStyle = computed(() => ({
  borderRadius: (props.size * 0.22) + 'px',
  display: 'block'
}))
const textStyle = computed(() => ({
  fontSize: (props.size * 0.55) + 'px',
  fontWeight: 700,
  color: 'var(--gk-gray-900)'
}))
</script>

<template>
  <div style="display:flex;align-items:center;gap:10px;">
    <img src="/logo-mark.svg" :width="size" :height="size" :style="imgStyle" alt="公考小智" />
    <div v-if="showText" :style="textStyle">公考小智</div>
  </div>
</template>
