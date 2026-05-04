<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TopNav from '../panels/TopNav.vue'
import { fetchQuestion } from '@/api'

const route = useRoute()
const router = useRouter()

const question = ref(null)
const selected = ref(null)
const submitted = ref(false)
const favorited = ref(false)

async function load() {
  selected.value = null
  submitted.value = false
  question.value = await fetchQuestion(route.params.id)
}

onMounted(load)
watch(() => route.params.id, load)

const isCorrect = computed(() => submitted.value && selected.value === question.value?.answer)

const select = (k) => { if (!submitted.value) selected.value = k }
const submit = () => { if (selected.value) submitted.value = true }
const reset = () => { selected.value = null; submitted.value = false }

const goSimilar = (id) => router.push('/question/' + id)
const goPractice = () => router.push('/practice')

const optionClass = (k) => {
  if (!submitted.value) return selected.value === k ? 'opt opt--sel' : 'opt'
  if (k === question.value.answer) return 'opt opt--ok'
  if (k === selected.value) return 'opt opt--bad'
  return 'opt opt--dim'
}
</script>

<template>
  <TopNav active="" @change="(k) => router.push('/' + k)" @login="router.push('/login')" />
  <div class="qd-wrap" v-if="question">
    <!-- Breadcrumb -->
    <div class="crumb">
      <a @click="goPractice">真题练习</a> / <a @click="goPractice">{{ question.province }} · {{ question.year }}</a> / <b>{{ question.subject }}</b>
    </div>

    <div class="qd-main">
      <!-- 题目卡 -->
      <article class="q-card">
        <header class="q-head">
          <div class="q-meta">
            <span class="q-type">{{ question.type }}</span>
            <span class="q-tag">{{ question.province }}</span>
            <span class="q-tag">{{ question.year }}</span>
            <span class="q-tag">{{ question.subject }}</span>
            <span class="q-diff">
              难度
              <span v-for="i in 5" :key="i" :class="['star', { on: i <= question.difficulty }]">★</span>
            </span>
          </div>
          <button class="fav-btn" :class="{ on: favorited }" @click="favorited = !favorited">
            {{ favorited ? '★ 已收藏' : '☆ 收藏' }}
          </button>
        </header>

        <div class="q-stem">
          <div class="q-id">题目 #{{ question.id }}</div>
          <p>{{ question.stem }}</p>
        </div>

        <div class="q-options">
          <button
            v-for="opt in question.options"
            :key="opt.key"
            :class="optionClass(opt.key)"
            @click="select(opt.key)"
          >
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-text">{{ opt.text }}</span>
            <span v-if="submitted && opt.key === question.answer" class="opt-mark">✓</span>
            <span v-else-if="submitted && opt.key === selected" class="opt-mark">✗</span>
          </button>
        </div>

        <div class="q-actions">
          <button v-if="!submitted" class="btn-primary" :disabled="!selected" @click="submit">提交答案</button>
          <button v-else class="btn-ghost" @click="reset">再做一遍</button>
          <button class="btn-ghost" @click="goPractice">下一题 →</button>
        </div>

        <!-- 提交后展开 -->
        <div v-if="submitted" class="q-result">
          <div :class="['result-banner', isCorrect ? 'ok' : 'bad']">
            <div class="rb-icon">{{ isCorrect ? '🎉' : '😅' }}</div>
            <div class="rb-text">
              <div class="rb-title">{{ isCorrect ? '回答正确！' : '答错了' }}</div>
              <div class="rb-sub">
                正确答案：<b>{{ question.answer }}</b>
                <template v-if="!isCorrect"> · 你选了：<b>{{ selected }}</b></template>
              </div>
            </div>
          </div>

          <div class="q-section">
            <h3>📖 题目解析</h3>
            <p>{{ question.analysis }}</p>
          </div>

          <div class="q-section">
            <h3>🏷️ 涉及知识点</h3>
            <div class="tag-row">
              <span v-for="k in question.knowledge" :key="k" class="kw">{{ k }}</span>
            </div>
          </div>
        </div>
      </article>

      <!-- 侧栏：相似题 -->
      <aside class="q-side">
        <div class="side-card">
          <h4>🤖 AI 讲解</h4>
          <p style="font-size:13px;color:var(--gk-gray-600);line-height:1.6;">
            遇到不懂的步骤？问 AI 老师，秒级响应。
          </p>
          <button class="btn-primary" style="width:100%;" @click="router.push('/chat')">向 AI 提问 →</button>
        </div>

        <div class="side-card">
          <h4>🔁 相似题推荐</h4>
          <div class="sim-list">
            <div
              v-for="s in question.similar"
              :key="s.id"
              class="sim-item"
              @click="goSimilar(s.id)"
            >
              <div class="sim-id">#{{ s.id }} · {{ s.subject }}</div>
              <div class="sim-stem">{{ s.stem }}</div>
            </div>
          </div>
        </div>

        <div class="side-card">
          <h4>📊 本题数据</h4>
          <div class="stat-row"><span>已答 / 总人数</span><b>23,418</b></div>
          <div class="stat-row"><span>整体正确率</span><b style="color:var(--gk-green-600);">62%</b></div>
          <div class="stat-row"><span>平均用时</span><b>1 分 12 秒</b></div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.qd-wrap { max-width: 1100px; margin: 0 auto; padding: 24px 32px 48px; }

.crumb { font-size: 13px; color: var(--gk-gray-500); margin-bottom: 16px; }
.crumb a { color: var(--gk-green-600); cursor: pointer; }
.crumb a:hover { text-decoration: underline; }
.crumb b { color: var(--gk-gray-900); }

.qd-main { display: grid; grid-template-columns: 1fr 320px; gap: 20px; }

/* Card */
.q-card { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 14px; padding: 28px 32px; }

.q-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.q-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.q-type { font-size: 12px; padding: 3px 10px; background: var(--gk-violet-50); color: var(--gk-violet-600); border-radius: 12px; font-weight: 500; }
.q-tag { font-size: 12px; padding: 3px 10px; background: var(--gk-gray-50); color: var(--gk-gray-600); border-radius: 12px; }
.q-diff { font-size: 12px; color: var(--gk-gray-500); margin-left: 4px; }
.q-diff .star { color: var(--gk-gray-300); margin: 0 1px; }
.q-diff .star.on { color: var(--gk-amber-500); }
.fav-btn { padding: 5px 12px; border: 1px solid var(--gk-gray-200); background: #fff; border-radius: 8px; font-size: 12px; cursor: pointer; color: var(--gk-gray-600); font-family: inherit; }
.fav-btn.on { background: #fffbeb; border-color: var(--gk-amber-300); color: var(--gk-amber-600); }

.q-stem { padding: 20px; background: var(--gk-gray-50); border-radius: 10px; margin-bottom: 20px; }
.q-id { font-size: 11px; color: var(--gk-gray-500); margin-bottom: 8px; letter-spacing: .05em; }
.q-stem p { font-size: 15px; line-height: 1.8; color: var(--gk-gray-900); margin: 0; }

.q-options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px; }
.opt {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--gk-gray-200);
  border-radius: 10px;
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  text-align: left;
  transition: all .15s;
}
.opt:hover { border-color: var(--gk-green-400); background: var(--gk-green-50); }
.opt-key { width: 28px; height: 28px; border-radius: 50%; background: var(--gk-gray-100); color: var(--gk-gray-700); display: flex; align-items: center; justify-content: center; font-weight: 600; flex-shrink: 0; }
.opt-text { flex: 1; color: var(--gk-gray-800); }
.opt-mark { font-size: 18px; font-weight: 700; }

.opt--sel { border-color: var(--gk-blue-500); background: var(--gk-blue-50); }
.opt--sel .opt-key { background: var(--gk-blue-500); color: #fff; }

.opt--ok { border-color: var(--gk-green-500); background: var(--gk-green-50); }
.opt--ok .opt-key { background: var(--gk-green-500); color: #fff; }
.opt--ok .opt-mark { color: var(--gk-green-600); }

.opt--bad { border-color: var(--gk-red-300); background: #fef2f2; }
.opt--bad .opt-key { background: var(--gk-red-500); color: #fff; }
.opt--bad .opt-mark { color: var(--gk-red-600); }

.opt--dim { opacity: .5; cursor: default; }

.q-actions { display: flex; gap: 10px; }
.btn-primary, .btn-ghost { padding: 10px 20px; border-radius: 8px; font-family: inherit; font-size: 14px; font-weight: 500; cursor: pointer; border: 0; }
.btn-primary { background: var(--gk-gray-900); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--gk-green-600); }
.btn-primary:disabled { background: var(--gk-gray-300); cursor: not-allowed; }
.btn-ghost { background: #fff; border: 1px solid var(--gk-gray-200); color: var(--gk-gray-700); }
.btn-ghost:hover { background: var(--gk-gray-50); }

/* Result */
.q-result { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--gk-gray-100); }
.result-banner { display: flex; align-items: center; gap: 14px; padding: 18px 22px; border-radius: 12px; margin-bottom: 24px; }
.result-banner.ok { background: linear-gradient(135deg, #ecfdf5, #d1fae5); border: 1px solid var(--gk-green-200); }
.result-banner.bad { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 1px solid #fecaca; }
.rb-icon { font-size: 36px; }
.rb-title { font-size: 18px; font-weight: 700; color: var(--gk-gray-900); }
.rb-sub { font-size: 13px; color: var(--gk-gray-600); margin-top: 4px; }
.rb-sub b { color: var(--gk-gray-900); }

.q-section { margin-bottom: 20px; }
.q-section h3 { font-size: 14px; font-weight: 600; color: var(--gk-gray-900); margin: 0 0 10px; }
.q-section p { font-size: 14px; line-height: 1.8; color: var(--gk-gray-700); margin: 0; }
.tag-row { display: flex; gap: 8px; flex-wrap: wrap; }
.kw { background: var(--gk-indigo-50); color: var(--gk-indigo-600); font-size: 12px; padding: 4px 12px; border-radius: 12px; }

/* Side */
.q-side { display: flex; flex-direction: column; gap: 14px; }
.side-card { background: #fff; border: 1px solid var(--gk-gray-200); border-radius: 12px; padding: 18px; }
.side-card h4 { font-size: 13px; font-weight: 600; color: var(--gk-gray-900); margin: 0 0 12px; }

.sim-list { display: flex; flex-direction: column; gap: 10px; }
.sim-item { padding: 12px; border: 1px solid var(--gk-gray-200); border-radius: 8px; cursor: pointer; transition: all .15s; }
.sim-item:hover { border-color: var(--gk-green-400); background: var(--gk-green-50); }
.sim-id { font-size: 11px; color: var(--gk-gray-500); margin-bottom: 4px; }
.sim-stem { font-size: 12px; color: var(--gk-gray-700); line-height: 1.5; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

.stat-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: var(--gk-gray-600); }
.stat-row b { color: var(--gk-gray-900); }

@media (max-width: 768px) {
  .qd-main { grid-template-columns: 1fr; }
  .q-card { padding: 20px; }
}
</style>
