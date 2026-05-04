<script setup>
import Card from '../components/Card.vue'
import SectionHeader from '../components/SectionHeader.vue'

const days = [1, 2, 3, 4, 5, 6, 7]
const done = [1, 1, 1, 1, 0.6, 0, 0]
const dayLabels = ['一', '二', '三', '四', '五', '六', '日']

const barStyle = (i) => ({
  position: 'absolute',
  inset: 0,
  top: ((1 - done[i]) * 100) + '%',
  background: done[i] === 1 ? 'var(--gk-green-500)' : done[i] > 0 ? 'var(--gk-green-300)' : 'transparent'
})
</script>

<template>
  <Card :padding="20">
    <SectionHeader emoji="📅" title="本周学习计划">
      <template #right>
        <span style="font-size:12px;color:var(--gk-green-600);font-weight:500;">已完成 65%</span>
      </template>
    </SectionHeader>
    <div style="display:flex;gap:8px;margin-bottom:14px;">
      <div v-for="(d, i) in days" :key="d" style="flex:1;text-align:center;">
        <div style="font-size:11px;color:var(--gk-gray-500);margin-bottom:6px;">周{{ dayLabels[i] }}</div>
        <div style="height:48px;background:var(--gk-gray-100);border-radius:6px;position:relative;overflow:hidden;">
          <div :style="barStyle(i)"></div>
        </div>
      </div>
    </div>
    <div style="font-size:13px;color:var(--gk-gray-600);line-height:1.7;">
      今日目标: 完成 <b style="color:var(--gk-gray-900);">行测 30 题</b> + <b style="color:var(--gk-gray-900);">申论范文精读 1 篇</b>
    </div>
  </Card>
</template>
