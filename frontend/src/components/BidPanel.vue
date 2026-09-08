<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  bidExportUrl, exportBidTemplate, getBidAssets, listAssets, saveBidAssets,
} from '../api'
import { CONTRACT_UNION_FIELDS } from '../constants/contractSubtypes'

const props = defineProps({ projectId: Number, bidDate: String, projectName: { type: String, default: '' } })

const persons = ref([])
const contracts = ref([])
const selectedContracts = ref([])
const roles = ref({})
const contractTable = ref(null)
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
// 旧版 Excel/Word 导出按格式记录 loading（导出走后端已保存勾选，故先保存再导出）
const exportingLegacy = ref('')

const selectedContractIds = computed(() => new Set(selectedContracts.value.map(r => r.id)))

// 人员姓名多选：搜索式添加（value = 资产 id），已选列表完全由它驱动
const personPick = ref([])
// 已选人员：按 personPick 顺序映射出行对象（保持用户添加顺序）
const selectedPersons = computed(() => {
  const byId = new Map(persons.value.map(p => [p.id, p]))
  return personPick.value.map(id => byId.get(id)).filter(Boolean)
})
const selectedPersonIds = computed(() => new Set(personPick.value))
// 项目负责人：仅一名，且只能从未勾选外的已勾选行中选择
const leadPersonId = ref(null)

function onPersonPick(ids) {
  if (leadPersonId.value && !ids.includes(leadPersonId.value)) leadPersonId.value = null
}

// 从已选人员中移除（同步处理负责人失效）
function removePerson(id) {
  personPick.value = personPick.value.filter(x => x !== id)
  if (leadPersonId.value === id) leadPersonId.value = null
}

// 从业年限有效值：基础年限 + max(0, 当前年份 - 基准年)；空返回 ''，非数字原样返回
function effectiveYears(fields) {
  const raw = String(fields?.['从业年限'] ?? '').trim()
  if (!raw) return ''
  const base = parseInt(raw.replace(/年$/, ''), 10)
  if (Number.isNaN(base)) return raw
  const ref = String(fields?.['从业年限基准年'] ?? '').trim()
  const m = ref.match(/(\d{4})/)
  const years = m ? base + Math.max(0, new Date().getFullYear() - Number(m[1])) : base
  return `${years}年`
}

// ---------- 业绩筛选 ----------
const CONTRACT_TYPE_OPTIONS = ['编标', '审标', '跟踪', '结算', '水利审计', '中标通知书']
const typeFilter = ref([])
const keyword = ref('')
const yearFilter = ref('')
const leadFilter = ref('')
const amountMin = ref(null)
const amountMax = ref(null)

// 项目负责人选项：全部人员姓名 ∪ 合同中已出现的 fields['项目负责人'] 非空非"/"值，去重排序
const leadOptions = computed(() => {
  const names = new Set(persons.value.map(p => p.name).filter(Boolean))
  for (const c of contracts.value) {
    const v = String(c.fields?.['项目负责人'] ?? '').trim()
    if (v && v !== '/') names.add(v)
  }
  return [...names].sort((a, b) => a.localeCompare(b, 'zh'))
})

// 年份选项：fields['年份'] 去重，前 4 位数字降序
const contractYearOptions = computed(() => {
  const years = new Set()
  for (const c of contracts.value) {
    const y = String(c.fields?.['年份'] ?? '').trim()
    if (y) years.add(y)
  }
  return [...years].sort((a, b) => {
    const ma = a.match(/^(\d{4})/)
    const mb = b.match(/^(\d{4})/)
    if (ma && mb) return Number(mb[1]) - Number(ma[1])
    if (ma) return -1
    if (mb) return 1
    return a.localeCompare(b)
  })
})

// 金额解析：fields['工程造价（万元）'] 取首个浮点数；「合同金额」旧字段兜底；解析不出返回 null
function parseAmount(c) {
  const raw = c.fields?.['工程造价（万元）'] ?? c.fields?.['合同金额'] ?? ''
  const m = String(raw).match(/-?\d+(?:\.\d+)?/)
  return m ? Number(m[0]) : null
}

const filteredContracts = computed(() => {
  const kw = keyword.value.trim()
  const useAmount = amountMin.value != null || amountMax.value != null
  return contracts.value.filter(c => {
    if (typeFilter.value.length && !typeFilter.value.includes(c.fields?.['类型'])) return false
    if (kw && !(c.name || '').includes(kw)
        && !String(c.fields?.['委托单位'] ?? '').includes(kw)) return false
    if (yearFilter.value && String(c.fields?.['年份'] ?? '').trim() !== yearFilter.value) return false
    if (leadFilter.value
        && String(c.fields?.['项目负责人'] ?? '').trim() !== leadFilter.value) return false
    if (useAmount) {
      const amt = parseAmount(c)
      if (amt === null) return false
      if (amountMin.value != null && amt < amountMin.value) return false
      if (amountMax.value != null && amt > amountMax.value) return false
    }
    return true
  })
})

// ---------- 业绩表格分页：只渲染当前页，避免大数据量 DOM 爆炸 ----------
const contractPage = ref(1)
const contractPageSize = ref(50)
const pagedContracts = computed(() => {
  const start = (contractPage.value - 1) * contractPageSize.value
  return filteredContracts.value.slice(start, start + contractPageSize.value)
})
// 筛选条件变化时回到第 1 页（勾选靠 row-key + reserve-selection 跨页保留）
watch([typeFilter, keyword, yearFilter, leadFilter, amountMin, amountMax],
  () => { contractPage.value = 1 }, { deep: true })

// ---------- 小节归属（仅本次导出用，默认小节1） ----------
const sections = ref({})

function onContractSelectionChange(rows) {
  selectedContracts.value = rows
  for (const r of rows) if (!sections.value[r.id]) sections.value[r.id] = 1
}

// 业绩表格列：[类型, 年份] + 子类型字段有序并集（见 constants/contractSubtypes.js），隐藏不展示的 5 列
const HIDDEN_CONTRACT_COLS = ['咨询单位', '份数', '合同到期时间', 'OA系统', '合同签订情况']
const unionCols = CONTRACT_UNION_FIELDS.filter(k => !HIDDEN_CONTRACT_COLS.includes(k))

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
  const expiry = cert['有效期至']
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

// 证书显示名：「专业+证书名称」（如"土建专业一级造价工程师"），不含有效期
function certName(cert) {
  const ctype = cert['类型'] || ''
  const major = cert['专业'] || ''
  return major ? `${major}专业${ctype}` : ctype
}

// Web 显示名：证书名 + 有效期（用于提醒临期；导出不含有效期）
function certWebLabel(cert) {
  const expiry = cert['有效期至'] || ''
  return expiry ? `${certName(cert)}（有效期至 ${expiry}）` : certName(cert)
}

// ---------- 证书勾选（personId -> 选中下标数组；未定义 = 从未调整，保存时传 null，后端按全部证书处理） ----------
const certPick = ref({})

function isCertSelected(personId, idx) {
  const sel = certPick.value[personId]
  return sel === undefined ? false : sel.includes(idx)
}

function toggleCert(personId, idx, checked) {
  const sel = certPick.value[personId] || []
  const next = checked ? [...new Set([...sel, idx])].sort((a, b) => a - b) : sel.filter(i => i !== idx)
  certPick.value = { ...certPick.value, [personId]: next }
}

// 导出时只传勾选的证书下标（默认不选）
function exportCertIndices(personId) {
  return certPick.value[personId] || []
}

// 回填期间置位，抑制自动保存 watcher（load 内所有状态回填完成后复位）
let restoring = false

async function load() {
  loading.value = true
  restoring = true
  try {
    const [p, c, selected] = await Promise.all([
      listAssets('person'),
      listAssets('contract'),
      getBidAssets(props.projectId),
    ])
    persons.value = p
    contracts.value = c

    // 回填已选：人员回填到搜索多选框，业绩勾选状态用 toggleRowSelection（需等表格渲染完成）
    const personSel = new Map((selected.persons || []).map(x => [x.asset_id, x.role || '']))
    const contractSel = new Set((selected.contracts || []).map(x => x.asset_id))
    personPick.value = (selected.persons || []).map(x => x.asset_id)
    for (const row of persons.value) roles.value[row.id] = personSel.get(row.id) || ''
    // 回填导出相关状态：负责人 / 证书勾选（certs 为 null 表示从未调整，保持未定义）/ 业绩小节
    leadPersonId.value = null
    certPick.value = {}
    for (const x of selected.persons || []) {
      if (x.is_lead) leadPersonId.value = x.asset_id
      if (Array.isArray(x.certs)) certPick.value[x.asset_id] = x.certs
    }
    sections.value = {}
    for (const x of selected.contracts || [])
      sections.value[x.asset_id] = Number(x.section || 1)
    await nextTick()
    for (const row of contracts.value)
      if (contractSel.has(row.id)) contractTable.value.toggleRowSelection(row, true)
  } finally {
    loading.value = false
    restoring = false
  }
}

// 保存载荷：人员含岗位/负责人/证书勾选（certs 为 null 表示从未调整，后端按全部证书处理），
// 业绩为 {asset_id, section}（默认小节1）
function buildSavePayload() {
  return {
    persons: selectedPersons.value.map(r => ({
      asset_id: r.id, role: roles.value[r.id] || '',
      is_lead: r.id === leadPersonId.value,
      certs: certPick.value[r.id] ?? null,
    })),
    contracts: selectedContracts.value.map(r => ({
      asset_id: r.id, section: Number(sections.value[r.id] || 1),
    })),
  }
}

async function onSave() {
  saving.value = true
  try {
    await saveBidAssets(props.projectId, buildSavePayload())
    ElMessage.success('勾选已保存')
  } finally {
    saving.value = false
  }
}

// 负责人 / 证书勾选 / 业绩小节变化时自动静默保存（不弹成功提示；保存失败由拦截器弹错）。
// flush: 'sync' 保证 load() 回填期间的变更被同步抑制，不受 watcher 默认异步 flush 时序影响
function persistSilently() {
  if (restoring) return
  saveBidAssets(props.projectId, buildSavePayload()).catch(() => { /* 拦截器已弹错 */ })
}
watch(leadPersonId, persistSilently, { flush: 'sync' })
watch(certPick, persistSilently, { deep: true, flush: 'sync' })
watch(sections, persistSilently, { deep: true, flush: 'sync' })

// 导出 Excel/Word：先按当前勾选保存（载荷同 onSave），成功后再触发后端导出
async function onExport(fmt) {
  exportingLegacy.value = fmt
  try {
    await saveBidAssets(props.projectId, buildSavePayload())
    window.open(bidExportUrl(props.projectId, fmt), '_blank')
  } catch { /* 保存失败：拦截器已弹错，中止导出 */ } finally {
    exportingLegacy.value = ''
  }
}

// ---------- 导出商务标对话框：每次打开时按当前项目信息重新初始化 ----------
const exportDialogVisible = ref(false)
const exportForm = ref({ project_no: '', project_name: '', doc_date: '' })

watch(exportDialogVisible, v => {
  if (!v) return
  exportForm.value = {
    project_no: '',
    project_name: props.projectName,
    doc_date: props.bidDate || '',
  }
})

// 导出商务标：is_lead / certs / section 与保存载荷同源（均已持久化），另加对话框字段
async function onExportTemplate() {
  if (!exportForm.value.project_name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  exporting.value = true
  try {
    const payload = {
      persons: selectedPersons.value.map(r => ({
        asset_id: r.id, is_lead: r.id === leadPersonId.value,
        certs: exportCertIndices(r.id),
      })),
      contracts: selectedContracts.value.map(r => ({
        asset_id: r.id, section: Number(sections.value[r.id] || 1),
      })),
      project_no: exportForm.value.project_no,
      project_name: exportForm.value.project_name.trim(),
      doc_date: exportForm.value.doc_date || '',
    }
    const r = await exportBidTemplate(props.projectId, payload)
    const cd = r.headers['content-disposition'] || ''
    const m = cd.match(/filename\*=UTF-8''([^;]+)/) || cd.match(/filename="?([^";]+)"?/)
    const filename = m ? decodeURIComponent(m[1]) : '商务标.docx'
    const url = URL.createObjectURL(r.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    exportDialogVisible.value = false
  } catch (e) {
    // blob 错误响应：转 json 读 detail 弹错（拦截器的通用提示不含 detail）
    if (e.response?.data instanceof Blob) {
      try {
        const detail = JSON.parse(await e.response.data.text())?.detail
        if (detail) ElMessage.error(typeof detail === 'string' ? detail : JSON.stringify(detail))
      } catch { /* 忽略解析失败 */ }
    }
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <h3>拟派人员</h3>
    <el-select v-model="personPick" multiple filterable placeholder="按姓名搜索并添加人员"
               style="width: 100%; margin-bottom: 8px" @change="onPersonPick">
      <el-option v-for="p in persons" :key="p.id" :label="p.name" :value="p.id" />
    </el-select>
    <el-table :data="selectedPersons" row-key="id">
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column label="从业年限" width="90">
        <template #default="{ row }">{{ effectiveYears(row.fields) || '-' }}</template>
      </el-table-column>
      <el-table-column label="职称" width="120">
        <template #default="{ row }">{{ row.fields['职称'] || '-' }}</template>
      </el-table-column>
      <el-table-column label="证书" min-width="320">
        <template #default="{ row }">
          <template v-if="(row.fields['证书'] || []).length">
            <el-checkbox v-for="(cert, i) in row.fields['证书']" :key="i"
                         :model-value="isCertSelected(row.id, i)"
                         @change="v => toggleCert(row.id, i, v)"
                         style="margin-right: 14px; margin-bottom: 2px">
              <span :style="certWarning(row, cert) ? 'color: #f56c6c; font-weight: 500' : ''">
                {{ certWebLabel(cert) }}<template v-if="certWarning(row, cert)">（{{ certWarning(row, cert).text }}）</template>
              </span>
            </el-checkbox>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="70" align="center">
        <template #default="{ row }">
          <el-radio-group v-model="leadPersonId">
            <el-radio :value="row.id" :disabled="!selectedPersonIds.has(row.id)" />
          </el-radio-group>
        </template>
      </el-table-column>
      <el-table-column label="拟派岗位" width="180">
        <template #default="{ row }">
          <el-input v-model="roles[row.id]" size="small" placeholder="如：项目经理"
                    :disabled="!selectedPersonIds.has(row.id)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="70" align="center">
        <template #default="{ row }">
          <el-button size="small" type="danger" link @click="removePerson(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="!selectedPersons.length" style="padding: 16px 0; color: #909399; font-size: 13px">
      尚未添加人员
    </div>

    <h3 style="margin-top: 24px">企业业绩</h3>
    <el-space style="margin-bottom: 8px" wrap>
      <el-select v-model="typeFilter" multiple collapse-tags placeholder="合同类型"
                 style="width: 220px">
        <el-option v-for="t in CONTRACT_TYPE_OPTIONS" :key="t" :label="t" :value="t" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="关键词（项目名称/委托单位）"
                style="width: 220px" />
      <el-select v-model="leadFilter" clearable filterable placeholder="项目负责人"
                 style="width: 150px">
        <el-option v-for="n in leadOptions" :key="n" :label="n" :value="n" />
      </el-select>
      <el-select v-model="yearFilter" clearable placeholder="年份" style="width: 130px">
        <el-option v-for="y in contractYearOptions" :key="y" :label="y" :value="y" />
      </el-select>
      <el-input-number v-model="amountMin" :controls="false" placeholder="金额下限（万元）"
                       style="width: 140px" />
      <span>-</span>
      <el-input-number v-model="amountMax" :controls="false" placeholder="金额上限（万元）"
                       style="width: 140px" />
    </el-space>
    <el-table ref="contractTable" :data="pagedContracts" row-key="id" max-height="40vh"
              @selection-change="onContractSelectionChange">
      <el-table-column type="selection" width="45" reserve-selection />
      <el-table-column prop="name" label="项目名称" min-width="200" show-overflow-tooltip />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.fields['类型']" size="small">{{ row.fields['类型'] }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="年份" width="100">
        <template #default="{ row }">{{ row.fields['年份'] || '-' }}</template>
      </el-table-column>
      <el-table-column v-for="k in unionCols" :key="k" :label="k" min-width="120"
                       show-overflow-tooltip>
        <template #default="{ row }">{{ displayField(row.fields[k]) || '-' }}</template>
      </el-table-column>
      <el-table-column label="小节" width="110">
        <template #default="{ row }">
          <el-select :model-value="sections[row.id] ?? 1" size="small"
                     :disabled="!selectedContractIds.has(row.id)"
                     @update:model-value="v => sections[row.id] = v">
            <el-option :value="1" label="小节1" />
            <el-option :value="2" label="小节2" />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="contractPage" v-model:page-size="contractPageSize"
                   :total="filteredContracts.length" :page-sizes="[20, 50, 100]"
                   layout="total, sizes, prev, pager, next"
                   style="margin-top: 8px; justify-content: flex-end" />

    <el-space style="margin-top: 16px">
      <el-button type="primary" :loading="saving" @click="onSave">保存勾选</el-button>
      <el-button type="primary" plain :loading="exporting"
                 @click="exportDialogVisible = true">导出商务标</el-button>
      <el-button :loading="exportingLegacy === 'xlsx'" @click="onExport('xlsx')">导出 Excel</el-button>
      <el-button :loading="exportingLegacy === 'docx'" @click="onExport('docx')">导出 Word</el-button>
    </el-space>

    <el-dialog v-model="exportDialogVisible" title="导出商务标" width="440px">
      <el-form label-width="80px">
        <el-form-item label="项目编号">
          <el-input v-model="exportForm.project_no" placeholder="请输入项目编号" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="exportForm.project_name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="exportForm.doc_date" type="date" value-format="YYYY-MM-DD"
                          placeholder="选择日期" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="exportDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="onExportTemplate">确定导出</el-button>
      </template>
    </el-dialog>
  </div>
</template>
