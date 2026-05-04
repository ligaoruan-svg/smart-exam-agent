<script setup>
import { computed } from 'vue'

const props = defineProps({
  padding: { type: [Number, String], default: 20 }
})

const style = computed(() => ({
  background: '#fff',
  border: '1px solid var(--gk-gray-200)',
  borderRadius: '12px',
  padding: typeof props.padding === 'number' ? props.padding + 'px' : props.padding
}))
</script>

<template>
  <div :style="style"><slot /></div>
</template>
