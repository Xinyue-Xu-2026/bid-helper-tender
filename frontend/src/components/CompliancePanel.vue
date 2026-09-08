<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { aiCheckCompliance, getCompliance, setCompliance } from '../api'

const props = defineProps({ projectId: Number })
const data = ref({ items: [], total: 0, checked: 0 })
const aiLoading = ref(false)

const percent = computed(() =>
  data.value.total ? Math.round((data.value.checked / data.value.total) * 100) : 0)

// 自动比对结果汇总（items 已由后端按 fail→manual→pass 排序）
const failCount = computed(() => data.value.items.filter(i => i.verdict === 'fail').length)
const manualCount = computed(() => data.value.items.filter(i => i.verdict === 'manual').length)
const passCount = computed(() => data.value.items.filter(i => i.verdict === 'pass').length)

const VERDICT_LABELS = { fail: '不满足', manual: '需人工确认', pass: '满足' }
const VERDICT_TYPES = { fail: 'danger', manual: 'warning', pass: 'success' }

async function load() { data.value = await getCompliance(props.projectId) }

async function onCheck(row, val) { await setCompliance(row.id, val); load() }

// AI 判定所有「需人工确认」项：结果按 requirement_id 覆盖到本地对应行
async function onAiCheck() {
  aiLoading.value = true
  try {
    const r = await aiCheckCompliance(props.projectId, [])
    const byId = new Map(r.results.map(x => [x.requirement_id, x]))
    for (const item of data.value.items) {
      const hit = byId.get(item.id)
      if (hit) { item.verdict = hit.verdict; item.reason = hit.reason }
    }
    ElMessage.success('AI 判定完成')
  } finally {
    aiLoading.value = false
  }
}

// 「不满足」行浅红高亮
function rowClass({ row }) { return row.verdict === 'fail' ? 'compliance-fail-row' : '' }

onMounted(load)
</script>

<template>
  <el-progress :percentage="percent" style="margin-bottom: 16px; max-width: 400px" />
  <el-space style="margin-bottom: 8px" wrap>
    <span>已核对 {{ data.checked }} / {{ data.total }} 项（废标项与资质门槛）</span>
    <el-tag type="danger" size="small">不满足 {{ failCount }}</el-tag>
    <el-tag type="warning" size="small">需人工确认 {{ manualCount }}</el-tag>
    <el-tag type="success" size="small">满足 {{ passCount }}</el-tag>
    <el-button type="primary" plain size="small" :loading="aiLoading"
               @click="onAiCheck">AI 判定需确认项</el-button>
  </el-space>
  <el-table :data="data.items" max-height="55vh" :row-class-name="rowClass">
    <el-table-column label="核对" width="70">
      <template #default="{ row }">
        <el-checkbox :model-value="row.checked" @change="v => onCheck(row, v)" />
      </template>
    </el-table-column>
    <el-table-column label="比对结果" width="110">
      <template #default="{ row }">
        <el-tag :type="VERDICT_TYPES[row.verdict] || 'info'">
          {{ VERDICT_LABELS[row.verdict] || row.verdict || '-' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="原因" min-width="160" show-overflow-tooltip>
      <template #default="{ row }">
        <span :style="row.reason ? '' : 'color: #c0c4cc'">{{ row.reason || '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column prop="category" label="分类" width="100">
      <template #default="{ row }">
        <el-tag :type="row.category === '废标项' ? 'danger' : 'warning'">{{ row.category }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="content" label="内容" show-overflow-tooltip />
    <el-table-column prop="source" label="来源" width="110" />
    <el-table-column prop="checked_at" label="核对时间" width="170">
      <template #default="{ row }">{{ row.checked_at ? row.checked_at.slice(0, 16).replace('T', ' ') : '' }}</template>
    </el-table-column>
  </el-table>
</template>

<style>
/* el-table 行样式需全局生效（不加 scoped） */
.compliance-fail-row { background: #fef0f0; }
</style>
