<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: { type: String, default: 'default' },
  active: { type: Boolean, default: false }
})

const style = computed(() => {
  const s = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 14px',
    borderRadius: '9999px',
    fontSize: '13px',
    fontWeight: 500,
    border: '1px solid var(--gk-gray-200)',
    background: '#fff',
    color: 'var(--gk-gray-700)',
    cursor: 'pointer',
    transition: 'all 120ms',
    fontFamily: 'inherit'
  }
  if (props.variant === 'danger')
    Object.assign(s, { borderColor: '#fca5a5', color: 'var(--gk-red-600)' })
  if (props.variant === 'success')
    Object.assign(s, { background: 'var(--gk-green-50)', borderColor: 'var(--gk-green-200)', color: 'var(--gk-green-700)' })
  if (props.active)
    Object.assign(s, { background: 'var(--gk-blue-50)', borderColor: 'var(--gk-blue-500)', color: 'var(--gk-blue-700)' })
  return s
})
</script>

<template>
  <button :style="style"><slot /></button>
</template>
