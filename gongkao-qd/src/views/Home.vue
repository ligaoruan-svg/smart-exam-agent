<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import TopNav from '../panels/TopNav.vue'
import ChatPanel from '../panels/ChatPanel.vue'
import PracticePanel from '../panels/PracticePanel.vue'
import DownloadPanel from '../panels/DownloadPanel.vue'
import MistakeBook from '../panels/MistakeBook.vue'
import StudyPlan from '../panels/StudyPlan.vue'

const router = useRouter()
const route = useRoute()

const active = computed(() => route.params.tab || 'chat')
const goTab = (k) => router.push('/' + k)
const goLogin = () => router.push('/login')
</script>

<template>
  <TopNav :active="active" @change="goTab" @login="goLogin" />

  <!-- 聊天页独占整屏，不套 .page 容器 -->
  <ChatPanel v-if="active === 'chat'" />

  <!-- 其他页维持原有布局 -->
  <div v-else class="page">
    <PracticePanel v-if="active === 'practice'" />
    <DownloadPanel v-if="active === 'download'" />
    <MistakeBook v-if="active === 'mistakes'" />
    <StudyPlan v-if="active === 'plan'" />
  </div>
</template>
