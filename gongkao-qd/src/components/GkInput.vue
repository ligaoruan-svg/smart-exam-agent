<script setup>
const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'keydown'])

const onInput = (e) => emit('update:modelValue', e.target.value)
const onFocus = (e) => {
  e.target.style.borderColor = 'var(--gk-green-500)'
  e.target.style.boxShadow = '0 0 0 3px rgba(16,185,129,0.2)'
}
const onBlur = (e) => {
  e.target.style.borderColor = 'var(--gk-gray-200)'
  e.target.style.boxShadow = 'none'
}
</script>

<template>
  <div v-if="label" style="display:flex;flex-direction:column;gap:6px;">
    <div style="font-size:12px;color:var(--gk-gray-600);font-weight:500;">{{ label }}</div>
    <input
      :value="modelValue"
      :placeholder="placeholder"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
      @keydown="$emit('keydown', $event)"
      style="font-family:inherit;font-size:14px;padding:9px 12px;border:1px solid var(--gk-gray-200);border-radius:8px;background:#fff;color:#111827;width:100%;outline:none;"
    />
  </div>
  <input
    v-else
    :value="modelValue"
    :placeholder="placeholder"
    @input="onInput"
    @focus="onFocus"
    @blur="onBlur"
    @keydown="$emit('keydown', $event)"
    style="font-family:inherit;font-size:14px;padding:9px 12px;border:1px solid var(--gk-gray-200);border-radius:8px;background:#fff;color:#111827;width:100%;outline:none;"
  />
</template>
