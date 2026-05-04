<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  options: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue'])
const caret = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>\")"
const baseStyle = {
  fontFamily: 'inherit',
  fontSize: '14px',
  padding: '9px 32px 9px 12px',
  border: '1px solid var(--gk-gray-200)',
  borderRadius: '8px',
  background: `#fff ${caret} no-repeat right 10px center`,
  color: '#111827',
  width: '100%',
  outline: 'none',
  appearance: 'none',
  cursor: 'pointer'
}
</script>

<template>
  <div v-if="label" style="display:flex;flex-direction:column;gap:6px;">
    <div style="font-size:12px;color:var(--gk-gray-600);font-weight:500;">{{ label }}</div>
    <select
      :value="modelValue"
      @change="emit('update:modelValue', $event.target.value)"
      :style="baseStyle"
    >
      <option v-for="o in options" :key="o" :value="o">{{ o }}</option>
    </select>
  </div>
  <select
    v-else
    :value="modelValue"
    @change="emit('update:modelValue', $event.target.value)"
    :style="baseStyle"
  >
    <option v-for="o in options" :key="o" :value="o">{{ o }}</option>
  </select>
</template>
