<script setup>
import { computed } from 'vue'

const props = defineProps({
  kind: { type: String, default: 'ai' },
  size: { type: Number, default: 34 }
})

const map = {
  ai: { bg: 'var(--gk-indigo-600)', label: '智' },
  me: { bg: 'var(--gk-green-500)', label: '你' }
}
const cfg = computed(() => map[props.kind] || map.ai)
const style = computed(() => ({
  width: props.size + 'px',
  height: props.size + 'px',
  borderRadius: '50%',
  background: cfg.value.bg,
  color: '#fff',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: props.size * 0.4 + 'px',
  fontWeight: 600,
  flexShrink: 0
}))
</script>

<template>
  <div :style="style">{{ cfg.label }}</div>
</template>
