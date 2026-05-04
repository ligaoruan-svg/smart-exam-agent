<script setup>
defineProps({
  emoji: { type: String, default: '' },
  title: { type: String, required: true }
})
</script>

<template>
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
    <div style="font-size:18px;font-weight:600;color:var(--gk-gray-900);display:flex;align-items:center;gap:8px;flex:1;">
      <span v-if="emoji" style="font-size:20px;">{{ emoji }}</span>{{ title }}
    </div>
    <slot name="right" />
  </div>
</template>
