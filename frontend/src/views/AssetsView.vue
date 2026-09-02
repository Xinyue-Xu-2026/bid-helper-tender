<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmImport, createAsset, deleteAsset, downloadImportTemplate, getFieldConfig,
  getImportSettings, importAssets, listAssets, scanImport, updateAsset, uploadAssetFile,
} from '../api'

const router = useRouter()
const tab = ref('credit')
const assets = ref([])
const dialogVisible = ref(false)
const editing = ref(null)
const form = ref({ name: '', fields: {}, expiry_date: '' })

const TABS = [
  { key: 'credit', label: '资信证书', nameLabel: '证书名称',
    fieldDefs: ['发证机关', '发证日期'], hasExpiry: true, hasImport: true },
  { key: 'person', label: '常用人员', nameLabel: '姓名',
    fieldDefs: ['身份证号', '职称', '联系方式', '证书名称'], hasExpiry: true, hasImport: true },
  { key: 'contract', label: '合同业绩', nameLabel: '项目名称',
    fieldDefs: [], hasExpiry: false, hasImport: true },
  { key: 'info', label: '企业信息', nameLabel: '项目',
    fieldDefs: ['值'], hasExpiry: false, hasImport: false },
  { key: 'material', label: '素材库', nameLabel: '素材名称',
    fieldDefs: ['备注'], hasExpiry: false, hasImport: false },
]

const currentTab = () => TABS.find(t => t.key === tab.value)

// ---------- 字段配置（设置页维护，驱动人员/合同业绩的列与表单） ----------
const fieldConfig = ref({ person: [], contract: [] })

const DEFAULT_CERT_TYPES = ['一级造价师', '二级造价师', '一级建造师', '二级建筑师', '监理工程师']
const DEFAULT_PERFORMANCE_TYPES = ['编标', '审标', '跟踪', '结算']

// 人员表格列：field-config 的 person 列表驱动；「姓名」固定绑 form.name，配置里出现则剔除（防御）
const personCols = computed(() => {
  const list = fieldConfig.value.person.length
    ? fieldConfig.value.person
    : TABS.find(t => t.key === 'person').fieldDefs.map(k => ({ key: k, type: 'text', options: [] }))
  return list.filter(f => f.key !== '姓名')
})

// 合同业绩表格列：field-config 的 contract 列表驱动；未配置时给一份默认列
const contractCols = computed(() =>
  fieldConfig.value.contract.length
    ? fieldConfig.value.contract
    : [
        { key: '类型', type: 'dropdown', options: DEFAULT_PERFORMANCE_TYPES },
        { key: '项目经理', type: 'text', options: [] },
        { key: '合同金额', type: 'text', options: [] },
        { key: '年份', type: 'text', options: [] },
      ])

// 人员展开区业绩小表格列：同合同配置，保证含「类型」列
const performanceCols = computed(() =>
  contractCols.value.some(f => f.key === '类型')
    ? contractCols.value
    : [{ key: '类型', type: 'dropdown', options: DEFAULT_PERFORMANCE_TYPES }, ...contractCols.value])

// 人员/合同业绩 tab 均由字段配置驱动
const isConfigTab = computed(() => ['person', 'contract'].includes(tab.value))
const configCols = computed(() => tab.value === 'person' ? personCols.value : contractCols.value)

// 动态表单字段：去掉固定名称列（姓名/项目名称绑 form.name）与结构化数组（证书/业绩单独处理）
const configFormFields = computed(() =>
  configCols.value.filter(f => f.key !== currentTab().nameLabel && !['证书', '业绩'].includes(f.key)))

const certTypeOptions = computed(() => {
  const f = fieldConfig.value.person.find(f =>
    f.type === 'dropdown' && ['证书类型', '类型'].includes(f.key) && f.options?.length)
  return f ? f.options : DEFAULT_CERT_TYPES
})

const performanceTypeOptions = computed(() => {
  const f = fieldConfig.value.contract.find(f => f.key === '类型' && f.type === 'dropdown' && f.options?.length)
  return f ? f.options : DEFAULT_PERFORMANCE_TYPES
})

async function loadFieldConfig() {
  try {
    const r = await getFieldConfig()
    fieldConfig.value = { person: r?.person || [], contract: r?.contract || [] }
  } catch {
    // 后端未就绪时使用默认列
  }
}

// 设置页保存字段配置后会写 localStorage 标记；此处消费标记并强制刷新配置。
// 路由无 keep-alive，每次进入本页都会重新挂载，天然拿到最新配置；标记机制作为兜底。
function consumeFieldConfigFlag() {
  if (localStorage.getItem('fieldConfigUpdatedAt')) {
    localStorage.removeItem('fieldConfigUpdatedAt')
    return loadFieldConfig()
  }
  return Promise.resolve()
}

// 字段值显示：数组/对象折叠为摘要，避免表格里出现 [object Object]
function displayField(v) {
  if (v === null || v === undefined || v === '') return ''
  if (Array.isArray(v)) return v.length ? `共 ${v.length} 条（展开查看）` : ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

const TAG_PALETTE = ['primary', 'success', 'warning', 'danger', 'info']
function tagTypeOf(v, options) {
  const i = options.indexOf(v)
  return TAG_PALETTE[(i >= 0 ? i : 0) % TAG_PALETTE.length]
}
function certTagType(v) { return tagTypeOf(v, certTypeOptions.value) }
function perfTagType(v) { return tagTypeOf(v, performanceTypeOptions.value) }

async function load() { assets.value = await listAssets(tab.value) }

function openDialog(row) {
  editing.value = row || null
  const fields = row ? { ...row.fields } : {}
  if (tab.value === 'person') {
    fields['证书'] = Array.isArray(fields['证书']) ? fields['证书'].map(c => ({ ...c })) : []
  }
  form.value = row
    ? { name: row.name, fields, expiry_date: row.expiry_date }
    : { name: '', fields, expiry_date: '' }
  dialogVisible.value = true
}

function newCertRow() {
  form.value.fields['证书'].push({ 类型: '', 证书名称: '', 有效期: '', 编号: '' })
}

async function save() {
  const payload = { ...form.value, type: tab.value }
  if (tab.value === 'person') {
    // 丢弃整行为空的证书行
    payload.fields = { ...payload.fields }
    payload.fields['证书'] = (payload.fields['证书'] || [])
      .filter(c => c['类型'] || c['证书名称'] || c['有效期'] || c['编号'])
  }
  if (editing.value) await updateAsset(editing.value.id, payload)
  else await createAsset(payload)
  dialogVisible.value = false
  load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」？`, '提示', { type: 'warning' })
  } catch { return }
  await deleteAsset(row.id); load()
}

async function onUploadFile(row, options) {
  await uploadAssetFile(row.id, options.file)
  ElMessage.success('附件已上传')
  load()
}

async function onImport(options) {
  const r = await importAssets(tab.value, options.file)
  ElMessage.success(`导入 ${r.imported} 条` + (r.errors.length ? `，跳过 ${r.errors.length} 行` : ''))
  load()
}

function isExpiringSoon(row) {
  if (!row.expiry_date) return false
  const days = (new Date(row.expiry_date) - new Date()) / 86400000
  return days >= 0 && days <= 30
}

function onTabChange() { load() }

onMounted(() => {
  loadFieldConfig()
  consumeFieldConfigFlag()
})

// ---------- 共享文件夹导入 ----------
const scanning = ref(false)
const confirming = ref(false)
const importDialogVisible = ref(false)
const importItems = ref([])
const importTableRef = ref()
const selectedItems = ref([])

const TYPE_LABELS = { person: '人员证书', credit: '企业资质' }
const ACTION_LABELS = { new: '新增', update: '更新' }

function typeLabel(t) { return TYPE_LABELS[t] || t || '-' }
function actionLabel(a) { return ACTION_LABELS[a] || a || '-' }

// 把 fields 对象摊平成可编辑行；数组/对象值以 JSON 文本编辑
function toFieldRows(fields) {
  return Object.entries(fields || {}).map(([k, v]) => {
    const isComplex = v !== null && typeof v === 'object'
    return { k, v: isComplex ? JSON.stringify(v, null, 2) : String(v ?? ''), isComplex }
  })
}

function fromFieldRows(rows) {
  const fields = {}
  for (const r of rows) {
    if (!r.k) continue
    if (r.isComplex) {
      try { fields[r.k] = JSON.parse(r.v) } catch { fields[r.k] = r.v }
    } else {
      fields[r.k] = r.v
    }
  }
  return fields
}

function fieldSummary(item) {
  const parts = []
  for (const [k, v] of Object.entries(item.fields || {})) {
    if (v === null || v === '') continue
    if (Array.isArray(v)) parts.push(`${k}（${v.length} 条）`)
    else if (typeof v === 'object') parts.push(k)
    else parts.push(`${k}：${v}`)
    if (parts.length >= 3) break
  }
  return parts.join('；') || '-'
}

async function onImportFolder() {
  scanning.value = true
  try {
    const settings = await getImportSettings()
    if (!settings?.shared_folder) {
      try {
        await ElMessageBox.confirm(
          '尚未配置共享文件夹路径，请先到设置页配置后再扫描。',
          '未配置共享文件夹',
          { confirmButtonText: '去设置', cancelButtonText: '取消', type: 'warning' },
        )
        router.push('/settings')
      } catch { /* 用户取消 */ }
      return
    }
    const r = await scanImport()
    if (r.errors?.length) {
      ElMessage.warning('部分文件识别失败：' + r.errors.map(e => `${e.filename}（${e.reason}）`).join('；'))
    }
    const items = (r.items || []).map(it => ({ ...it, fieldRows: toFieldRows(it.fields) }))
    if (!items.length) {
      ElMessage.info('共享文件夹中没有识别到可入库的资料')
      return
    }
    importItems.value = items
    importDialogVisible.value = true
    // 默认全选，有警告的默认不选
    await nextTick()
    for (const it of importItems.value) {
      const checked = !(it.warnings && it.warnings.length)
      importTableRef.value?.toggleRowSelection(it, checked)
    }
  } finally {
    scanning.value = false
  }
}

function onImportSelectionChange(rows) { selectedItems.value = rows }

function selectAll() {
  for (const it of importItems.value) importTableRef.value?.toggleRowSelection(it, true)
}

function invertSelection() {
  const selected = new Set(selectedItems.value)
  for (const it of importItems.value) importTableRef.value?.toggleRowSelection(it, !selected.has(it))
}

function importRowClass({ row }) {
  return (row.highlight || (row.warnings && row.warnings.length)) ? 'import-highlight-row' : ''
}

async function onConfirmImport() {
  confirming.value = true
  try {
    const items = selectedItems.value.map(it => {
      const { fieldRows, ...rest } = it
      return { ...rest, fields: fromFieldRows(fieldRows) }
    })
    const r = await confirmImport(items)
    const parts = [`新增 ${r.created ?? 0} 条`, `更新 ${r.updated ?? 0} 条`]
    if (r.new_persons?.length) parts.push(`新入库人员：${r.new_persons.join('、')}`)
    ElMessage.success('入库完成：' + parts.join('，'))
    importDialogVisible.value = false
    importItems.value = []
    load()
  } finally {
    confirming.value = false
  }
}

onMounted(load)
</script>

<template>
  <h2>资产库</h2>
  <el-tabs v-model="tab" @tab-change="onTabChange">
    <el-tab-pane v-for="t in TABS" :key="t.key" :label="t.label" :name="t.key" />
  </el-tabs>

  <el-space style="margin-bottom: 12px">
    <el-button type="primary" @click="openDialog(null)">新增</el-button>
    <el-upload v-if="currentTab().hasImport" :show-file-list="false" accept=".xlsx"
               :http-request="onImport">
      <el-button>Excel 导入</el-button>
    </el-upload>
    <el-button v-if="isConfigTab" @click="downloadImportTemplate(tab)">下载导入模板</el-button>
    <el-button :loading="scanning" @click="onImportFolder">从共享文件夹导入</el-button>
  </el-space>

  <el-table :key="tab" :data="assets" :row-class-name="({ row }) => isExpiringSoon(row) ? 'expiring-row' : ''">
    <!-- 人员：展开显示证书与业绩明细 -->
    <el-table-column v-if="tab === 'person'" type="expand">
      <template #default="{ row }">
        <div class="expand-panel">
          <div class="expand-block">
            <div class="expand-title">证书（{{ (row.fields['证书'] || []).length }} 本）</div>
            <el-table v-if="(row.fields['证书'] || []).length" :data="row.fields['证书']" size="small">
              <el-table-column label="类型" width="120">
                <template #default="{ row: c }">
                  <el-tag v-if="c['类型']" :type="certTagType(c['类型'])" size="small">{{ c['类型'] }}</el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="证书名称" min-width="160">
                <template #default="{ row: c }">{{ c['证书名称'] || '-' }}</template>
              </el-table-column>
              <el-table-column label="有效期" width="120">
                <template #default="{ row: c }">{{ c['有效期'] || '-' }}</template>
              </el-table-column>
              <el-table-column label="编号" min-width="140">
                <template #default="{ row: c }">{{ c['编号'] || '-' }}</template>
              </el-table-column>
            </el-table>
            <div v-else class="expand-empty">暂无证书记录</div>
          </div>
          <div class="expand-block">
            <div class="expand-title">业绩（{{ (row.fields['业绩'] || []).length }} 条）</div>
            <el-table v-if="(row.fields['业绩'] || []).length" :data="row.fields['业绩']" size="small">
              <el-table-column v-for="f in performanceCols" :key="f.key" :label="f.key"
                               :min-width="f.key === '类型' ? 100 : 140">
                <template #default="{ row: p }">
                  <el-tag v-if="f.key === '类型' && p[f.key]" :type="perfTagType(p[f.key])"
                          size="small">{{ p[f.key] }}</el-tag>
                  <span v-else>{{ displayField(p[f.key]) || '-' }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-else class="expand-empty">暂无业绩记录</div>
          </div>
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="name" :label="currentTab().nameLabel" width="180" />
    <template v-if="isConfigTab">
      <el-table-column v-for="f in configCols" :key="f.key" :label="f.key" min-width="120">
        <template #default="{ row }">
          <el-tag v-if="f.key === '类型' && row.fields[f.key]" size="small"
                  :type="perfTagType(row.fields[f.key])">{{ row.fields[f.key] }}</el-tag>
          <span v-else>{{ displayField(row.fields[f.key]) }}</span>
        </template>
      </el-table-column>
    </template>
    <template v-else>
      <el-table-column v-for="f in currentTab().fieldDefs" :key="f" :label="f">
        <template #default="{ row }">{{ displayField(row.fields[f]) }}</template>
      </el-table-column>
    </template>
    <el-table-column v-if="currentTab().hasExpiry" label="有效期至" width="130">
      <template #default="{ row }">
        <span :style="isExpiringSoon(row) ? 'color: #f56c6c; font-weight: bold' : ''">
          {{ row.expiry_date }}{{ isExpiringSoon(row) ? '（即将到期）' : '' }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="附件" width="120">
      <template #default="{ row }">
        <el-upload :show-file-list="false" :http-request="opt => onUploadFile(row, opt)">
          <el-button size="small" link type="primary">{{ row.file_path ? '替换' : '上传' }}</el-button>
        </el-upload>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="140">
      <template #default="{ row }">
        <el-button size="small" @click="openDialog(row)">编辑</el-button>
        <el-button size="small" type="danger" link @click="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑' : '新增'"
             :width="tab === 'person' ? '680px' : tab === 'contract' ? '560px' : '500px'">
    <el-form label-width="110px">
      <el-form-item :label="currentTab().nameLabel" required>
        <el-input v-model="form.name" />
      </el-form-item>
      <!-- 人员/合同业绩：按字段配置动态生成 -->
      <template v-if="isConfigTab">
        <el-form-item v-for="f in configFormFields" :key="f.key" :label="f.key">
          <el-date-picker v-if="f.type === 'date'" v-model="form.fields[f.key]"
                          value-format="YYYY-MM-DD" style="width: 100%" />
          <el-select v-else-if="f.type === 'dropdown'" v-model="form.fields[f.key]"
                     clearable filterable style="width: 100%">
            <el-option v-for="opt in f.options || []" :key="opt" :label="opt" :value="opt" />
          </el-select>
          <el-input v-else v-model="form.fields[f.key]" />
        </el-form-item>
      </template>
      <!-- 人员：证书数组编辑 -->
      <template v-if="tab === 'person'">
        <el-form-item label="证书">
          <div class="cert-editor">
            <el-table v-if="form.fields['证书'].length" :data="form.fields['证书']" size="small">
              <el-table-column label="类型" width="150">
                <template #default="{ row: c }">
                  <el-select v-model="c['类型']" size="small" clearable filterable allow-create
                             placeholder="选择类型">
                    <el-option v-for="t in certTypeOptions" :key="t" :label="t" :value="t" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="证书名称" min-width="150">
                <template #default="{ row: c }">
                  <el-input v-model="c['证书名称']" size="small" placeholder="证书名称" />
                </template>
              </el-table-column>
              <el-table-column label="有效期" width="150">
                <template #default="{ row: c }">
                  <el-date-picker v-model="c['有效期']" size="small" value-format="YYYY-MM-DD"
                                  placeholder="有效期" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column label="编号" min-width="120">
                <template #default="{ row: c }">
                  <el-input v-model="c['编号']" size="small" placeholder="编号" />
                </template>
              </el-table-column>
              <el-table-column label="" width="60">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" link
                             @click="form.fields['证书'].splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="newCertRow">添加证书</el-button>
          </div>
        </el-form-item>
      </template>
      <!-- 其他类型：沿用固定字段 -->
      <template v-if="!isConfigTab">
        <el-form-item v-for="f in currentTab().fieldDefs" :key="f" :label="f">
          <el-input v-model="form.fields[f]" />
        </el-form-item>
      </template>
      <el-form-item v-if="currentTab().hasExpiry" label="有效期至">
        <el-date-picker v-model="form.expiry_date" value-format="YYYY-MM-DD" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="!form.name" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <!-- 共享文件夹导入：待确认列表 -->
  <el-dialog v-model="importDialogVisible" title="共享文件夹扫描结果（请确认后入库）"
             fullscreen :close-on-click-modal="false">
    <div class="import-tip">共识别 {{ importItems.length }} 条，带警告的行已默认取消勾选，可展开行核对并修改字段。</div>
    <el-table ref="importTableRef" :data="importItems" :row-class-name="importRowClass"
              height="calc(100vh - 220px)" @selection-change="onImportSelectionChange">
      <el-table-column type="selection" width="45" />
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="field-editor">
            <div class="field-editor-title">
              来源：{{ row.source || '-' }} ｜ 字段内容（可直接修改）
            </div>
            <el-table :data="row.fieldRows" size="small">
              <el-table-column label="字段名" width="220">
                <template #default="{ row: fr }">
                  <el-input v-model="fr.k" size="small" placeholder="字段名" />
                </template>
              </el-table-column>
              <el-table-column label="值">
                <template #default="{ row: fr }">
                  <el-input v-if="fr.isComplex" v-model="fr.v" type="textarea" :rows="3" size="small" />
                  <el-input v-else v-model="fr.v" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="" width="70">
                <template #default="{ $index }">
                  <el-button size="small" type="danger" link
                             @click="row.fieldRows.splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px"
                       @click="row.fieldRows.push({ k: '', v: '', isComplex: false })">添加字段</el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="file_name" label="来源文件" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ typeLabel(row.asset_type) }}</template>
      </el-table-column>
      <el-table-column label="关键字段" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">{{ fieldSummary(row) }}</template>
      </el-table-column>
      <el-table-column label="警告" min-width="180">
        <template #default="{ row }">
          <template v-if="row.warnings && row.warnings.length">
            <el-tag v-for="(w, i) in row.warnings" :key="i" type="warning" size="small"
                    style="margin: 2px 4px 2px 0">{{ w }}</el-tag>
          </template>
          <span v-else style="color: #909399">-</span>
        </template>
      </el-table-column>
      <el-table-column label="动作" width="90">
        <template #default="{ row }">
          <el-tag :type="row.action === 'new' ? 'success' : 'info'" size="small">
            {{ actionLabel(row.action) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <div class="import-footer">
        <el-space>
          <el-button size="small" @click="selectAll">全选</el-button>
          <el-button size="small" @click="invertSelection">反选</el-button>
          <span class="selected-count">已选 {{ selectedItems.length }} 项</span>
        </el-space>
        <el-space>
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="confirming" :disabled="!selectedItems.length"
                     @click="onConfirmImport">确认入库</el-button>
        </el-space>
      </div>
    </template>
  </el-dialog>
</template>

<style>
.expiring-row { background: #fef0f0; }
.import-highlight-row { background: #fdf6ec; }
.import-tip { margin-bottom: 12px; color: #606266; font-size: 13px; }
.import-footer { display: flex; justify-content: space-between; align-items: center; }
.selected-count { color: #606266; font-size: 13px; }
.field-editor { padding: 8px 24px 16px 48px; }
.field-editor-title { margin-bottom: 8px; color: #606266; font-size: 13px; }
.expand-panel { padding: 4px 24px 12px 48px; }
.expand-block + .expand-block { margin-top: 12px; }
.expand-title { margin-bottom: 6px; color: #606266; font-size: 13px; }
.expand-empty { color: #909399; font-size: 12px; padding: 4px 0 8px; }
.cert-editor { width: 100%; }
</style>
