<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'primary' },
  icon: { type: String, default: '' }
})

const styleMap = {
  primary:  { background: 'var(--gk-blue-600)',   color: '#fff' },
  practice: { background: 'var(--gk-violet-600)', color: '#fff' },
  success:  { background: 'var(--gk-green-500)',  color: '#fff' },
  ai:       { background: 'var(--gk-indigo-600)', color: '#fff' },
  ghost:    { background: 'transparent', border: '1px solid var(--gk-gray-300)', color: 'var(--gk-gray-700)' },
  danger:   { background: 'transparent', border: '1px solid #fca5a5', color: 'var(--gk-red-600)' }
}

const base = {
  border: 0,
  fontFamily: 'inherit',
  fontWeight: 500,
  fontSize: '14px',
  padding: '8px 18px',
  borderRadius: '8px',
  cursor: 'pointer',
  transition: 'all 180ms',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '6px'
}

const computedStyle = computed(() => ({ ...base, ...(styleMap[props.variant] || styleMap.primary) }))
</script>

<template>
  <button :style="computedStyle">
    <span v-if="icon">{{ icon }}</span>
    <slot />
  </button>
</template>
