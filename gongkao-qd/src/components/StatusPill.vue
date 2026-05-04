<template>
  <span
    :style="{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '8px',
      padding: '6px 12px',
      borderRadius: '9999px',
      fontSize: '12px',
      fontWeight: 500,
      background: 'var(--gk-green-50)',
      color: 'var(--gk-green-700)',
      border: '1px solid var(--gk-green-200)'
    }"
  >
    <span
      :style="{
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        background: 'var(--gk-green-500)'
      }"
    ></span>
    <slot />
  </span>
</template>
