<script setup>
defineProps({
  title: { type: String, default: '' }
})
</script>

<template>
  <button
    :title="title"
    :style="{
      width: '36px',
      height: '36px',
      border: '1px solid var(--gk-gray-200)',
      background: '#fff',
      borderRadius: '8px',
      color: 'var(--gk-gray-500)',
      cursor: 'pointer',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '16px'
    }"
  >
    <slot />
  </button>
</template>
