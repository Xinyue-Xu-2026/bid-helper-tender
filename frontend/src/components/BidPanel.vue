<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  bidExportUrl, exportBidTemplate, generateBidDraft, getBidAssets, getBidDraft,
  getBidDraftHeadings, getProject, listAssets, saveBidAssets, saveBidDraftBindings,
  uploadBidDraft,
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
const exportForm = ref({ project_no: '', project_name: '', doc_date: '', tenderer: '', bidder_name: '' })

watch(exportDialogVisible, async v => {
  if (!v) return
  exportForm.value = {
    project_no: '',
    project_name: props.projectName,
    doc_date: props.bidDate || '',
    // 招标人：底稿提取值优先，缺省回落项目委托人（下方异步补齐）
    tenderer: draft.value?.tenderer || '',
    bidder_name: '宏信天德工程顾问有限公司',
  }
  if (!exportForm.value.tenderer) {
    try {
      const p = await getProject(props.projectId)
      exportForm.value.tenderer = p.client || ''
    } catch { /* 拦截器已弹错；留空可手填 */ }
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
      tenderer: exportForm.value.tenderer.trim(),
      bidder_name: exportForm.value.bidder_name.trim(),
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
    // 有底稿时响应头带 X-Fill-Report（URL 编码 JSON）→ 弹出填充报告；旧模板路径无此头，维持现状
    const fr = r.headers['x-fill-report']
    if (fr) {
      try {
        fillReport.value = JSON.parse(decodeURIComponent(fr))
        reportDialogVisible.value = true
      } catch { /* 报告解析失败不阻塞下载结果 */ }
    }
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

// ---------- 商务标底稿：生成 / 上传 / 预览确认 / 绑定保存 ----------
const DRAFT_ROLE_OPTIONS = [
  { value: 'person_roster', label: '人员一览表' },
  { value: 'lead_resume', label: '负责人简历表' },
  { value: 'perf_list', label: '业绩一览表' },
  { value: 'quote', label: '报价表' },
  { value: 'image_slot', label: '图片占位' },
  { value: 'ignore', label: '忽略' },
]
const PERSON_SCOPE_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'lead', label: '仅负责人' },
  { value: 'members', label: '仅成员' },
]
const PERF_SCOPE_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'lead', label: '负责人业绩' },
  { value: 'section1', label: '小节1' },
  { value: 'section2', label: '小节2' },
]
const LABEL_KIND_OPTIONS = ['职称证书', '社保', '身份证', '注册证书']

function roleLabel(v) {
  return DRAFT_ROLE_OPTIONS.find(o => o.value === v)?.label || v || '-'
}

const draft = ref(null)              // 底稿预览对象；null = 无底稿
const draftLoading = ref(false)      // 底稿卡片加载/生成/上传中
const draftDialogVisible = ref(false)
const draftHeadings = ref([])        // 裁切起止候选标题 [{index, level, title}]
const draftRange = ref({ start: '', end: '' })  // 裁切起止（值=heading.index；'' = 未选；end -1 = 文档末尾）
const bindingRows = ref([])          // 对话框内可编辑的表格绑定行（基于预览 tables 拷贝）
const swapToc = ref(false)
const regenerating = ref(false)
const bindingsSaving = ref(false)

// 图片占位「归属人员」选项：负责人 + 成员0..N（按当前已选非负责人数量）
const imagePersonOptions = computed(() => {
  const opts = [{ value: 'lead', label: '负责人' }]
  const n = selectedPersons.value.filter(p => p.id !== leadPersonId.value).length
  for (let i = 0; i < n; i++) opts.push({ value: `member:${i}`, label: `成员${i}` })
  return opts
})

// 低置信度建议行弱提示（未确认时才需要人工核对）
function needManualConfirm(row) {
  if (row.confirmed) return false
  const c = row.confidence
  // 后端分类器输出中文 "高"/"低"；'low'/数值分支为防御性兜底
  return c === '低' || c === 'low' || (typeof c === 'number' && c < 0.6)
}

// GET /bid-draft：有底稿返回预览对象本身，无底稿返回 { draft: null }
async function loadDraft() {
  draftLoading.value = true
  try {
    const r = await getBidDraft(props.projectId)
    draft.value = (r && 'draft' in r) ? r.draft : r
  } catch { /* 拦截器已弹错 */ } finally {
    draftLoading.value = false
  }
}

// 用预览对象刷新卡片与对话框状态（bindings 拷贝为可编辑行）
function applyDraftPreview(preview) {
  draft.value = preview
  bindingRows.value = (preview.tables || []).map(t => ({ ...t }))
  swapToc.value = !!preview.swap_toc
  // 裁切范围在 headings 加载后由 syncRangeFromDraft 回填（title → index）
}

// 重名标题集合（目录条目区与正文区同名时需要序号后缀区分）
const dupHeadingTitles = computed(() => {
  const count = {}
  for (const h of draftHeadings.value) count[h.title] = (count[h.title] || 0) + 1
  return new Set(Object.keys(count).filter(t => count[t] > 1))
})

function headingLabel(h) {
  return dupHeadingTitles.value.has(h.title) ? `${h.title} ｜ #${h.index}` : h.title
}

// 标题文本 → heading.index；重名取最后一次出现（与后端目录区在前的兜底一致）
function titleToIndex(title) {
  const t = (title || '').trim()
  if (!t) return ''
  const hits = draftHeadings.value.filter(h => (h.title || '').trim() === t)
  return hits.length ? hits[hits.length - 1].index : ''
}

// 底稿已存裁切范围（cut_start/cut_end 标题）回填到索引型 select
function syncRangeFromDraft() {
  if (!draft.value) return
  draftRange.value = {
    start: titleToIndex(draft.value.cut_start),
    end: titleToIndex(draft.value.cut_end),
  }
}

// 拉取裁切起止候选标题（失败不阻塞对话框，起止选择留空）
async function fetchDraftHeadings() {
  try {
    const r = await getBidDraftHeadings(props.projectId)
    draftHeadings.value = r.headings || []
    syncRangeFromDraft()
    return r.suggested || null
  } catch { /* 拦截器已弹错 */ }
  return null
}

// 打开预览与确认对话框：有底稿按其刷新绑定行；同时加载 headings
async function openDraftDialog() {
  if (draft.value) applyDraftPreview(draft.value)
  draftDialogVisible.value = true
  await fetchDraftHeadings()
}

// 「生成底稿」：先尝试自动定位（空参）；422 未识别格式章节 → 打开对话框手动选起止
async function onGenerateDraft() {
  draftLoading.value = true
  try {
    const preview = await generateBidDraft(props.projectId, { start_heading: '', end_heading: '' })
    applyDraftPreview(preview)
    ElMessage.success('底稿已生成，请预览并确认表格绑定')
    openDraftDialog()
  } catch (e) {
    if (e?.response?.status === 422) {
      const suggested = await fetchDraftHeadings()
      draftRange.value = {
        start: titleToIndex(suggested?.start),
        end: titleToIndex(suggested?.end),
      }
      draftDialogVisible.value = true
    }
  } finally {
    draftLoading.value = false
  }
}

// 「重新生成」（卡片入口）：二次确认后按当前裁切范围重新生成（清空已确认绑定）
async function onRegenerateDraft() {
  try {
    await ElMessageBox.confirm('重新生成将清空已确认的表格绑定，确定继续？', '重新生成底稿',
      { type: 'warning', confirmButtonText: '重新生成', cancelButtonText: '取消' })
  } catch { return }
  draftLoading.value = true
  try {
    const preview = await generateBidDraft(props.projectId, {
      start_heading: draft.value?.cut_start || '',
      end_heading: draft.value?.cut_end || '',
    })
    applyDraftPreview(preview)
    ElMessage.success('底稿已重新生成，请重新确认表格绑定')
  } catch (e) {
    if (e?.response?.status === 422) {
      const suggested = await fetchDraftHeadings()
      draftRange.value = {
        start: titleToIndex(suggested?.start),
        end: titleToIndex(suggested?.end),
      }
      draftDialogVisible.value = true
    }
  } finally {
    draftLoading.value = false
  }
}

// 对话框内「按此范围重新生成」：手动起止生成（无底稿时即首次生成）
// 起止 select 的值为 heading.index；未选起始 → 不传索引（走后端自动定位）
async function onRegenerateWithRange() {
  regenerating.value = true
  try {
    const payload = {}
    if (draftRange.value.start !== '' && draftRange.value.start != null) {
      payload.start_index = draftRange.value.start
      // 选了起始但未选截至 → 裁到文档末尾（-1）
      payload.end_index = (draftRange.value.end === '' || draftRange.value.end == null)
        ? -1 : draftRange.value.end
    }
    const preview = await generateBidDraft(props.projectId, payload)
    applyDraftPreview(preview)
    ElMessage.success('已按所选范围生成，请确认表格绑定')
  } catch { /* 拦截器已弹错 */ } finally {
    regenerating.value = false
  }
}

// 上传底稿（.docx，替换现有底稿）→ 成功后打开预览对话框
async function onUploadDraft(uploadFile) {
  const file = uploadFile.raw
  if (!file) return
  draftLoading.value = true
  try {
    const preview = await uploadBidDraft(props.projectId, file)
    applyDraftPreview(preview)
    ElMessage.success('底稿已上传，请预览并确认表格绑定')
    openDraftDialog()
  } catch { /* 拦截器已弹错 */ } finally {
    draftLoading.value = false
  }
}

// 角色切换时重置该行的条件字段为默认值（避免残留其它角色的条件）
function onBindingRoleChange(row) {
  row.person_scope = 'all'
  row.perf_scope = 'all'
  row.label_kind = LABEL_KIND_OPTIONS[0]
  row.person = 'lead'
}

// 「确认并保存绑定」：整表提交，所有行 confirmed=true（提交后即生效，未确认的表不会被填充）
async function onSaveBindings() {
  bindingsSaving.value = true
  try {
    await saveBidDraftBindings(props.projectId, {
      tables: bindingRows.value.map(r => ({
        table_index: r.table_index,
        role: r.role,
        columns: r.columns,
        person_scope: r.person_scope,
        perf_scope: r.perf_scope,
        label_kind: r.label_kind,
        person: r.person,
        confirmed: true,
      })),
      swap_toc: swapToc.value,
    })
    ElMessage.success('绑定已保存，导出时将按确认结果填充')
    draftDialogVisible.value = false
    loadDraft()
  } catch { /* 拦截器已弹错 */ } finally {
    bindingsSaving.value = false
  }
}

// ---------- 导出填充报告对话框 ----------
const reportDialogVisible = ref(false)
const fillReport = ref(null)

onMounted(() => { load(); loadDraft() })
</script>

<template>
  <div v-loading="loading">
    <el-card shadow="never" style="margin-bottom: 16px" v-loading="draftLoading">
      <div v-if="!draft" style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <span style="color: #909399; font-size: 13px">尚未生成商务标底稿（生成后可按底稿表格结构精确填充导出）</span>
        <el-button type="primary" size="small" :loading="draftLoading" @click="onGenerateDraft">生成底稿</el-button>
        <el-upload :show-file-list="false" accept=".docx" :auto-upload="false" :on-change="onUploadDraft">
          <el-button size="small">上传底稿</el-button>
        </el-upload>
      </div>
      <div v-else style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <span style="font-size: 13px">
          底稿：{{ draft.name || '-' }}　裁切范围：{{ draft.cut_start || '自动定位' }} ～ {{ draft.cut_end || '文档末尾' }}　来源：{{ draft.source === 'upload' ? '手动上传' : '招标文件自动生成' }}
        </span>
        <el-button type="primary" size="small" plain @click="openDraftDialog">预览与确认</el-button>
        <el-button size="small" :loading="draftLoading" @click="onRegenerateDraft">重新生成</el-button>
        <el-upload :show-file-list="false" accept=".docx" :auto-upload="false" :on-change="onUploadDraft">
          <el-button size="small">上传底稿</el-button>
        </el-upload>
      </div>
    </el-card>

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
      <el-tooltip :disabled="!!draft" content="未生成底稿，使用内置模板导出" placement="top">
        <el-button type="primary" plain :loading="exporting"
                   @click="exportDialogVisible = true">导出商务标</el-button>
      </el-tooltip>
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
        <el-form-item label="招标人">
          <el-input v-model="exportForm.tenderer" placeholder="请输入招标人名称（留空则不填充）" />
        </el-form-item>
        <el-form-item label="投标人">
          <el-input v-model="exportForm.bidder_name" placeholder="请输入投标人名称（留空则不填充）" />
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

    <el-dialog v-model="draftDialogVisible" title="商务标底稿预览与确认" width="760px">
      <!-- 顶部工具区：裁切起止 + 按范围（重新）生成 -->
      <el-space wrap style="margin-bottom: 12px">
        <el-select v-model="draftRange.start" filterable placeholder="起始标题" style="width: 240px">
          <el-option v-for="h in draftHeadings" :key="h.index" :label="headingLabel(h)" :value="h.index" />
        </el-select>
        <span>～</span>
        <el-select v-model="draftRange.end" filterable placeholder="截至标题" style="width: 240px">
          <el-option label="文档末尾" :value="-1" />
          <el-option v-for="h in draftHeadings" :key="h.index" :label="headingLabel(h)" :value="h.index" />
        </el-select>
        <el-button type="primary" plain :loading="regenerating" @click="onRegenerateWithRange">
          {{ draft ? '按此范围重新生成' : '按此范围生成' }}
        </el-button>
      </el-space>

      <template v-if="!draft">
        <el-alert type="info" :closable="false"
                  title="尚未生成底稿：请选择裁切起止标题后点击「按此范围生成」。" />
      </template>
      <template v-else>
        <el-alert v-for="(w, i) in draft.warnings || []" :key="i" type="warning" :closable="false"
                  :title="w" style="margin-bottom: 6px" />
        <el-alert type="info" :closable="false" style="margin-bottom: 10px"
                  title="以下为建议绑定，未点击「确认并保存绑定」前不会生效；未确认的表格导出时不会被填充。" />

        <h4 style="margin: 8px 0 4px">大纲</h4>
        <div style="max-height: 160px; overflow: auto; font-size: 12px; color: #606266; border: 1px solid #ebeef5; border-radius: 4px; padding: 6px 10px">
          <div v-for="(o, i) in draft.outline || []" :key="i"
               :style="{ paddingLeft: `${(Number(o[0]) - 1) * 16}px` }">{{ o[1] }}</div>
        </div>

        <h4 style="margin: 12px 0 4px">表格绑定</h4>
        <el-table :data="bindingRows" size="small" max-height="320">
          <el-table-column prop="table_index" label="#" width="50" />
          <el-table-column label="表头预览" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ (row.header || []).join(' / ') || '-' }}</template>
          </el-table-column>
          <el-table-column prop="context_heading" label="前文标题" min-width="120"
                           show-overflow-tooltip>
            <template #default="{ row }">{{ row.context_heading || '-' }}</template>
          </el-table-column>
          <el-table-column label="角色" width="140">
            <template #default="{ row }">
              <el-select v-model="row.role" size="small" @change="onBindingRoleChange(row)">
                <el-option v-for="o in DRAFT_ROLE_OPTIONS" :key="o.value"
                           :label="o.label" :value="o.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="条件" min-width="190">
            <template #default="{ row }">
              <el-select v-if="row.role === 'person_roster'" v-model="row.person_scope"
                         size="small" placeholder="人员范围">
                <el-option v-for="o in PERSON_SCOPE_OPTIONS" :key="o.value"
                           :label="o.label" :value="o.value" />
              </el-select>
              <el-select v-else-if="row.role === 'perf_list'" v-model="row.perf_scope"
                         size="small" placeholder="业绩范围">
                <el-option v-for="o in PERF_SCOPE_OPTIONS" :key="o.value"
                           :label="o.label" :value="o.value" />
              </el-select>
              <el-space v-else-if="row.role === 'image_slot'" wrap>
                <el-select v-model="row.label_kind" size="small" placeholder="图片类型"
                           style="width: 110px">
                  <el-option v-for="k in LABEL_KIND_OPTIONS" :key="k" :label="k" :value="k" />
                </el-select>
                <el-select v-model="row.person" size="small" placeholder="归属人员"
                           style="width: 90px">
                  <el-option v-for="o in imagePersonOptions" :key="o.value"
                             :label="o.label" :value="o.value" />
                </el-select>
              </el-space>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.confirmed" type="success" size="small">已确认</el-tag>
              <el-tag v-else-if="needManualConfirm(row)" type="warning" size="small">需人工确认</el-tag>
              <el-tag v-else type="info" size="small">建议</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-checkbox v-model="swapToc" style="margin-top: 10px">
          将目录页替换为自动目录（导出后请在 Word 中按 F9 更新页码）
        </el-checkbox>
      </template>

      <template #footer>
        <el-button @click="draftDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindingsSaving" :disabled="!draft"
                   @click="onSaveBindings">确认并保存绑定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportDialogVisible" title="导出填充报告" width="560px">
      <template v-if="fillReport">
        <el-alert v-if="fillReport.verify && fillReport.verify.ok === false" type="error"
                  :closable="false" title="校验未通过：检测到未授权改动，请勿使用该文件。"
                  style="margin-bottom: 10px" />
        <ul v-if="fillReport.verify && (fillReport.verify.issues || []).length"
            style="margin: 0 0 10px; padding-left: 20px; color: #f56c6c; font-size: 13px">
          <li v-for="(s, i) in fillReport.verify.issues" :key="i">{{ s }}</li>
        </ul>

        <template v-if="(fillReport.filled || []).length">
          <h4 style="margin: 8px 0 4px">已填充</h4>
          <div v-for="(f, i) in fillReport.filled" :key="i" style="font-size: 13px; margin: 2px 0">
            表格#{{ f.table_index }}（{{ roleLabel(f.role) }}）：填充 {{ f.rows }} 行
          </div>
        </template>

        <template v-if="(fillReport.images || []).length">
          <h4 style="margin: 8px 0 4px">图片</h4>
          <div v-for="(im, i) in fillReport.images" :key="i"
               :style="`font-size: 13px; margin: 2px 0; ${im.ok ? '' : 'color: #f56c6c'}`">
            #{{ im.table_index }} {{ im.person }} · {{ im.label_kind }}{{ im.ok ? '' : ' 插入失败' }}
          </div>
        </template>

        <template v-if="(fillReport.skipped || []).length">
          <h4 style="margin: 8px 0 4px">已跳过</h4>
          <div v-for="(s, i) in fillReport.skipped" :key="i"
               style="font-size: 13px; margin: 2px 0; color: #909399">
            表格#{{ s.table_index }}（{{ roleLabel(s.role) }}）：{{ s.reason }}
          </div>
        </template>
      </template>
      <template #footer>
        <el-button type="primary" @click="reportDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>
