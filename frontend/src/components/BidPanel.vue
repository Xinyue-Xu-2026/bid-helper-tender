<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { bidExportUrl, getBidAssets, getFieldConfig, listAssets, saveBidAssets } from '../api'

const props = defineProps({ projectId: Number, bidDate: String })

const persons = ref([])
const contracts = ref([])
const selectedPersons = ref([])
const selectedContracts = ref([])
const roles = ref({})
const fieldConfig = ref({ person: [], contract: [] })
const personTable = ref(null)
const contractTable = ref(null)
const loading = ref(false)
const saving = ref(false)

const selectedPersonIds = computed(() => new Set(selectedPersons.value.map(r => r.id)))

// 企业业绩列：复用 AssetsView 的 contractCols 逻辑——字段配置驱动，未配置时用默认列
const contractCols = computed(() =>
  fieldConfig.value.contract.length
    ? fieldConfig.value.contract
    : [
        { key: '类型', type: 'dropdown', options: ['编标', '审标', '跟踪', '结算'] },
        { key: '项目经理', type: 'text', options: [] },
        { key: '合同金额', type: 'text', options: [] },
        { key: '年份', type: 'text', options: [] },
      ])

// 字段值显示：数组/对象折叠为摘要，避免出现 [object Object]
function displayField(v) {
  if (v === null || v === undefined || v === '') return ''
  if (Array.isArray(v)) return v.length ? `共 ${v.length} 条` : ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

// 证书有效期警告：与后端同规则、本地计算，仅对已勾选人员判定（与后端 cert_warnings 口径一致）。
// 有效期早于投标日 → expired；否则 30 天内到期 → soon；有效期无法解析的证书跳过。
function certWarning(row, cert) {
  if (!selectedPersonIds.value.has(row.id)) return null
  const expiry = cert['有效期'] || cert['有效期至']
  if (!expiry) return null
  const exp = new Date(expiry)
  if (isNaN(exp)) return null
  if (props.bidDate) {
    const bid = new Date(props.bidDate)
    if (!isNaN(bid) && exp < bid) return { level: 'expired', text: '投标日已过期' }
  }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((exp - today) / 86400000)
  if (days >= 0 && days <= 30) return { level: 'soon', text: `剩 ${days} 天` }
  return null
}

function certTagType(row, cert) {
  const w = certWarning(row, cert)
  return w ? (w.level === 'expired' ? 'danger' : 'warning') : ''
}

function certLabel(row, cert) {
  const base = cert['类型'] || cert['证书名称'] || '证书'
  const w = certWarning(row, cert)
  return w ? `${base}（${w.text}）` : base
}

async function load() {
  loading.value = true
  try {
    const [p, c, selected, cfg] = await Promise.all([
      listAssets('person'),
      listAssets('contract'),
      getBidAssets(props.projectId),
      getFieldConfig().catch(() => null),
    ])
    persons.value = p
    contracts.value = c
    if (cfg) fieldConfig.value = { person: cfg.person || [], contract: cfg.contract || [] }

    // 回填已选：勾选状态用 toggleRowSelection（需等表格渲染完成），岗位回填到对应行
    const personSel = new Map((selected.persons || []).map(x => [x.asset_id, x.role || '']))
    const contractSel = new Set((selected.contracts || []).map(x => x.asset_id))
    for (const row of persons.value) roles.value[row.id] = personSel.get(row.id) || ''
    await nextTick()
    for (const row of persons.value)
      if (personSel.has(row.id)) personTable.value.toggleRowSelection(row, true)
    for (const row of contracts.value)
      if (contractSel.has(row.id)) contractTable.value.toggleRowSelection(row, true)
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    await saveBidAssets(props.projectId, {
      persons: selectedPersons.value.map(r => ({ asset_id: r.id, role: roles.value[r.id] || '' })),
      contracts: selectedContracts.value.map(r => r.id),
    })
    ElMessage.success('勾选已保存')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <h3>拟派人员</h3>
    <el-table ref="personTable" :data="persons" max-height="40vh"
              @selection-change="v => selectedPersons = v">
      <el-table-column type="selection" width="45" />
      <el-table-column prop="name" label="姓名" width="110" />
      <el-table-column label="职称" width="140">
        <template #default="{ row }">{{ row.fields['职称'] || '-' }}</template>
      </el-table-column>
      <el-table-column label="证书" min-width="280">
        <template #default="{ row }">
          <template v-if="(row.fields['证书'] || []).length">
            <el-tag v-for="(cert, i) in row.fields['证书']" :key="i" size="small"
                    :type="certTagType(row, cert)" style="margin: 2px 6px 2px 0">
              {{ certLabel(row, cert) }}
            </el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="拟派岗位" width="180">
        <template #default="{ row }">
          <el-input v-model="roles[row.id]" size="small" placeholder="如：项目经理"
                    :disabled="!selectedPersonIds.has(row.id)" />
        </template>
      </el-table-column>
    </el-table>

    <h3 style="margin-top: 24px">企业业绩</h3>
    <el-table ref="contractTable" :data="contracts" max-height="40vh"
              @selection-change="v => selectedContracts = v">
      <el-table-column type="selection" width="45" />
      <el-table-column prop="name" label="项目名称" min-width="200" show-overflow-tooltip />
      <el-table-column v-for="f in contractCols" :key="f.key" :label="f.key" min-width="120">
        <template #default="{ row }">{{ displayField(row.fields[f.key]) || '-' }}</template>
      </el-table-column>
    </el-table>

    <el-space style="margin-top: 16px">
      <el-button type="primary" :loading="saving" @click="onSave">保存勾选</el-button>
      <el-button tag="a" :href="bidExportUrl(projectId, 'xlsx')" target="_blank">导出 Excel</el-button>
      <el-button tag="a" :href="bidExportUrl(projectId, 'docx')" target="_blank">导出 Word</el-button>
    </el-space>
  </div>
</template>
