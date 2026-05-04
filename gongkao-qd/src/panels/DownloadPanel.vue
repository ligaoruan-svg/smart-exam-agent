<script setup>
/**
 * DownloadPanel.vue - 真题下载中心
 *
 * round 3：接真接口
 *   - GET /api/paper/provinces  → 省份网格 + 整包 ZIP
 *   - GET /api/paper/list       → 最近真题列表（按年倒序）
 *   - 单文件 / ZIP 下载都走 token 鉴权（用 fetch + Authorization 头），
 *     避免在 URL 里暴露 token
 */
import { ref, computed, onMounted } from 'vue'
import Card from '../components/Card.vue'
import SectionHeader from '../components/SectionHeader.vue'
import GkInput from '../components/GkInput.vue'
import Button from '../components/Button.vue'
import { paperApi, getToken } from '@/api'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'

const provinces = ref([])      // [{province, files, size_mb, has_zip, zip_url, zip_size_mb}]
const extras    = ref([])      // [{name, filename, size_mb, zip_url}] 专题资料
const recent    = ref([])      // 最近真题
const loading   = ref(true)
const errorMsg  = ref('')

const q         = ref('')
const toast     = ref(null)
const hoverKey  = ref(null)

const filtered = computed(() =>
  provinces.value.filter(p => !q.value || p.province.includes(q.value))
)

const filteredExtras = computed(() =>
  extras.value.filter(e => !q.value || (e.name || '').includes(q.value))
)

const totalFiles = computed(() =>
  provinces.value.reduce((a, p) => a + p.files, 0)
)

const totalSizeMb = computed(() => {
  // 总包大小用各省份 zip 之和（更准确），如果都没 zip 用 paper size 之和
  const zipSum = provinces.value.reduce((a, p) => a + (p.zip_size_mb || 0), 0)
  if (zipSum > 0) return zipSum
  return provinces.value.reduce((a, p) => a + (p.size_mb || 0), 0)
})

const totalSizeText = computed(() => {
  const m = totalSizeMb.value
  if (m >= 1024) return `${(m / 1024).toFixed(2)} GB`
  return `${m.toFixed(0)} MB`
})

/* ============================================================
 * 加载数据
 * ============================================================ */
async function loadProvinces() {
  try {
    const r = await paperApi.listProvinces()
    provinces.value = r.provinces || []
    extras.value    = r.extras || []
  } catch (e) {
    console.error('[loadProvinces]', e)
    errorMsg.value = '省份数据加载失败：' + (e.message || e)
  }
}

async function loadRecent() {
  try {
    const r = await paperApi.list({ page: 1, page_size: 8 })
    recent.value = (r.items || [])
  } catch (e) {
    console.error('[loadRecent]', e)
    // 静默失败
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadProvinces(), loadRecent()])
  loading.value = false
})

/* ============================================================
 * 下载（统一用 fetch + Authorization 头）
 * ============================================================ */
async function fetchAndSave(url, suggestedName) {
  const token = getToken()
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`
  toast.value = `正在下载：${suggestedName}…`
  try {
    const resp = await fetch(fullUrl, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (!resp.ok) {
      const t = await resp.text().catch(() => '')
      throw new Error(`HTTP ${resp.status} ${t.slice(0, 80)}`)
    }
    const blob = await resp.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objUrl
    a.download = suggestedName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(objUrl), 1500)
    toast.value = `✓ 已下载：${suggestedName}`
  } catch (e) {
    toast.value = `✗ 下载失败：${e.message}`
  }
  setTimeout(() => (toast.value = null), 2800)
}

function downloadProvinceZip(p) {
  if (!p.has_zip) {
    toast.value = `${p.province} 暂无整包 ZIP`
    setTimeout(() => (toast.value = null), 2400)
    return
  }
  fetchAndSave(p.zip_url, `${p.province}公考真题.zip`)
}

function downloadExtra(e) {
  fetchAndSave(e.zip_url, e.filename || `${e.name}.zip`)
}

function downloadPaper(it) {
  fetchAndSave(it.download_url, (it.name || '真题') + '.pdf')
}
</script>

<template>
  <div style="display:flex;flex-direction:column;gap:20px;">
    <Card :padding="20">
      <SectionHeader emoji="📦" title="真题下载">
        <template #right>
          <div style="font-size:12px;color:var(--gk-gray-500);">
            <template v-if="loading">加载中…</template>
            <template v-else>
              共 {{ provinces.length }} 个省份 ·
              {{ totalFiles.toLocaleString() }} 份文件
              <template v-if="extras.length"> · {{ extras.length }} 份专题</template>
              · {{ totalSizeText }} · 全部免费
            </template>
          </div>
        </template>
      </SectionHeader>

      <div v-if="errorMsg" style="padding:14px;color:var(--gk-red-600);font-size:13px;background:var(--gk-red-50);border-radius:8px;margin-bottom:14px;">
        {{ errorMsg }}
      </div>

      <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;">
        <div style="flex:1;max-width:320px;">
          <GkInput v-model="q" placeholder="🔍 搜索省份或专题..." />
        </div>
      </div>

      <div v-if="loading && provinces.length === 0" style="padding:40px;text-align:center;color:var(--gk-gray-400);font-size:13px;">
        加载中…
      </div>

      <div
        v-else
        style="display:grid;grid-template-columns:repeat(auto-fill, minmax(160px, 1fr));gap:10px;"
      >
        <div
          v-for="p in filtered"
          :key="p.province"
          @mouseenter="hoverKey = p.province"
          @mouseleave="hoverKey = null"
          :style="{
            background: '#fff',
            border: `1px solid ${hoverKey === p.province ? 'var(--gk-green-400)' : 'var(--gk-gray-200)'}`,
            borderRadius: '10px',
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            cursor: 'pointer',
            transition: 'all 180ms',
            position: 'relative'
          }"
        >
          <span
            v-if="p.has_zip"
            style="position:absolute;top:8px;right:8px;font-size:10px;padding:2px 6px;border-radius:4px;background:var(--gk-blue-50, #eff6ff);color:var(--gk-blue-700, #1d4ed8);font-weight:600;"
          >ZIP</span>
          <div style="font-size:15px;font-weight:600;color:var(--gk-gray-900);">{{ p.province }}</div>
          <div style="font-size:12px;color:var(--gk-gray-500);">
            {{ p.files }} 份
            <template v-if="p.has_zip"> · {{ p.zip_size_mb }} MB</template>
            <template v-else-if="p.size_mb"> · {{ p.size_mb }} MB</template>
          </div>
          <button
            @click="downloadProvinceZip(p)"
            :disabled="!p.has_zip"
            :style="{
              marginTop: '4px',
              border: 0,
              background: !p.has_zip
                ? 'var(--gk-gray-100)'
                : (hoverKey === p.province ? 'var(--gk-green-500)' : 'var(--gk-green-50)'),
              color: !p.has_zip
                ? 'var(--gk-gray-400)'
                : (hoverKey === p.province ? '#fff' : 'var(--gk-green-700)'),
              fontSize: '12px',
              fontWeight: 500,
              padding: '6px 0',
              borderRadius: '6px',
              cursor: p.has_zip ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
              transition: 'all 180ms'
            }"
          >
            {{ p.has_zip ? '↓ 下载 ZIP' : '暂无 ZIP' }}
          </button>
        </div>

        <!-- 专题资料：跟省份混在同一网格里，用紫色调区分 -->
        <div
          v-for="e in filteredExtras"
          :key="`extra-${e.name}`"
          @mouseenter="hoverKey = `extra-${e.name}`"
          @mouseleave="hoverKey = null"
          :style="{
            background: '#fff',
            border: `1px solid ${hoverKey === `extra-${e.name}` ? 'var(--gk-purple-400, #c084fc)' : 'var(--gk-gray-200)'}`,
            borderRadius: '10px',
            padding: '12px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            cursor: 'pointer',
            transition: 'all 180ms',
            position: 'relative'
          }"
        >
          <span
            style="position:absolute;top:8px;right:8px;font-size:10px;padding:2px 6px;border-radius:4px;background:var(--gk-purple-50, #faf5ff);color:var(--gk-purple-700, #7e22ce);font-weight:600;"
          >专题</span>
          <div style="font-size:15px;font-weight:600;color:var(--gk-gray-900);">📘 {{ e.name }}</div>
          <div style="font-size:12px;color:var(--gk-gray-500);">
            学习资料 · {{ e.size_mb }} MB
          </div>
          <button
            @click="downloadExtra(e)"
            :style="{
              marginTop: '4px',
              border: 0,
              background: hoverKey === `extra-${e.name}` ? 'var(--gk-purple-500, #a855f7)' : 'var(--gk-purple-50, #faf5ff)',
              color: hoverKey === `extra-${e.name}` ? '#fff' : 'var(--gk-purple-700, #7e22ce)',
              fontSize: '12px',
              fontWeight: 500,
              padding: '6px 0',
              borderRadius: '6px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              transition: 'all 180ms'
            }"
          >
            ↓ 下载 ZIP
          </button>
        </div>
      </div>

      <div v-if="!loading && filtered.length === 0 && filteredExtras.length === 0" style="padding:40px;text-align:center;color:var(--gk-gray-400);font-size:13px;">
        没有找到匹配的内容
      </div>
    </Card>

    <Card :padding="20">
      <SectionHeader emoji="📄" title="最近的 PDF 真题">
        <template #right>
          <span style="font-size:12px;color:var(--gk-gray-500);">
            按年份倒序
          </span>
        </template>
      </SectionHeader>
      <div v-if="loading && recent.length === 0" style="padding:20px;color:var(--gk-gray-400);font-size:13px;">
        加载中…
      </div>
      <div v-else-if="recent.length === 0" style="padding:20px;color:var(--gk-gray-400);font-size:13px;">
        暂无数据
      </div>
      <div v-else>
        <div
          v-for="(it, i) in recent"
          :key="it.id"
          :style="{ display: 'flex', alignItems: 'center', padding: '10px 0', borderTop: i ? '1px solid var(--gk-gray-100)' : 'none', gap: '12px' }"
        >
          <div style="width:32px;height:32px;border-radius:6px;background:var(--gk-red-50);color:var(--gk-red-600);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0;">PDF</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:13px;font-weight:500;color:var(--gk-gray-900);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ it.name }}</div>
            <div style="font-size:11px;color:var(--gk-gray-500);margin-top:2px;">
              {{ it.province }} · {{ it.year }} · {{ it.exam_type }}
              <template v-if="it.doc_type"> · {{ it.doc_type }}</template>
              <template v-if="it.size_mb"> · {{ it.size_mb }} MB</template>
            </div>
          </div>
          <button
            @click="downloadPaper(it)"
            style="border:0;background:var(--gk-blue-600);color:#fff;font-size:12px;padding:6px 14px;border-radius:6px;cursor:pointer;font-family:inherit;font-weight:500;"
          >↓ PDF</button>
        </div>
      </div>
    </Card>

    <div
      v-if="toast"
      style="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--gk-gray-900);color:#fff;padding:10px 18px;border-radius:8px;font-size:13px;box-shadow:0 10px 25px rgba(0,0,0,0.2);display:flex;align-items:center;gap:8px;z-index:100;"
    >
      {{ toast }}
    </div>
  </div>
</template>
