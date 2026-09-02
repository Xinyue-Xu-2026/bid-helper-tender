<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSection, deleteSection, exportWordUrl, getProject, getSections, listAssets,
  listMaterials, listTemplates, mimicApply, mimicDownloadUrl, mimicPlan,
  sectionGenerateUrl, sectionsAdaptTitles, sectionsFromTemplate, updateSection,
} from '../api'

const route = useRoute()
const pid = Number(route.params.id)

const project = ref({})
const tree = ref([])
const currentId = ref(null)
const content = ref('')
const saving = ref(false)
const generating = ref(false)
const targetWords = ref(null)
const progressInfo = ref(null)
const templateGenLoading = ref(false)
const adaptLoading = ref(false)
const assets = ref([])
const materials = ref([])
const templates = ref([])
const selectedAssets = ref([])
const selectedMaterials = ref([])
const templateId = ref(null)
const mimicLoading = ref(false)
const mimicApplying = ref(false)
const mimicPlanResult = ref(null)
const mimicReport = ref(null)
let es = null

function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n
    const r = findNode(n.children || [], id)
    if (r) return r
  }
  return null
}

const current = computed(() => findNode(tree.value, currentId.value) || {})

async function load() {
  project.value = await getProject(pid)
  tree.value = await getSections(pid)
  assets.value = (await listAssets()).filter(a => a.type !== 'material')
  materials.value = await listMaterials(pid)
  templates.value = await listTemplates()
  if (currentId.value == null && tree.value.length) select(tree.value[0])
}

function select(node) {
  if (generating.value) return
  currentId.value = node.id
  content.value = node.content || ''
}

async function onSectionsFromTemplate() {
  if (generating.value) return
  if (!templateId.value) { ElMessage.warning('请先选择模板'); return }
  templateGenLoading.value = true
  try {
    await sectionsFromTemplate(pid, templateId.value)
    ElMessage.success('已按模板标题结构生成章节')
    currentId.value = null
    await load()
  } catch (e) {
    if (e.response?.status === 422) {
      ElMessage.warning('该模板没有可用的标题结构，无法生成章节，请先在模板管理中解析或更换模板')
    }
  } finally {
    templateGenLoading.value = false
  }
}

async function onAdaptTitles() {
  if (generating.value) return
  if (!tree.value.length) { ElMessage.warning('请先生成章节'); return }
  adaptLoading.value = true
  try {
    await sectionsAdaptTitles(pid)
    ElMessage.success('章节标题已改写')
    await load()
  } catch (e) {
    if (e.response?.status === 502) {
      ElMessage.error('标题改写失败，请重试')
    }
  } finally {
    adaptLoading.value = false
  }
}

async function onAddChild() {
  if (generating.value) return
  if (!currentId.value) { ElMessage.warning('请先选择父章节'); return }
  const node = current.value
  const { id } = await createSection(pid, {
    parent_id: node.id, title: '新章节',
    level: Math.min((node.level || 0) + 1, 3), sort_order: 0,
  })
  await load()
  select(findNode(tree.value, id))
}

async function onDeleteSection() {
  if (generating.value) return
  if (!currentId.value) return
  try {
    await ElMessageBox.confirm('删除该章节及其子章节？', '提示', { type: 'warning' })
  } catch { return }
  await deleteSection(currentId.value)
  currentId.value = null
  ElMessage.success('已删除')
  await load()
}

async function onSave() {
  if (!currentId.value) return
  saving.value = true
  try {
    await updateSection(currentId.value, { content: content.value, gen_status: '已编辑' })
    ElMessage.success('已保存')
    await load()
  } finally {
    saving.value = false
  }
}

function onGenerate() {
  if (!currentId.value) { ElMessage.warning('请先选择章节'); return }
  if (es) es.close()
  generating.value = true
  targetWords.value = null
  progressInfo.value = null
  content.value = ''
  const url = sectionGenerateUrl(pid, currentId.value, {
    assetIds: selectedAssets.value, materialIds: selectedMaterials.value,
    templateId: templateId.value,
  })
  es = new EventSource(url)
  es.addEventListener('chunk', e => { content.value += e.data })
  // 逐小节进度：{"type":"progress","current":i,"total":n,"title":"..."}
  es.addEventListener('progress', e => {
    try {
      const d = JSON.parse(e.data)
      if (d.current && d.total) progressInfo.value = { current: d.current, total: d.total, title: d.title || '' }
    } catch { /* 忽略无法解析的进度事件 */ }
  })
  // 后端若在生成前下发 meta 事件（{"target_words": N} 或纯数字），显示目标篇幅
  es.addEventListener('meta', e => {
    try {
      const d = JSON.parse(e.data)
      targetWords.value = d.target_words || d.target_length || null
    } catch {
      const n = parseInt(e.data, 10)
      targetWords.value = Number.isNaN(n) ? null : n
    }
  })
  es.addEventListener('done', e => {
    content.value = e.data
    es.close(); es = null; generating.value = false
    ElMessage.success('生成完成，请检查后保存')
    load()
  })
  es.addEventListener('error', e => {
    es.close(); es = null; generating.value = false
    ElMessage.error(e.data || '生成失败，请重试')
  })
}

function truncate(s, n = 30) {
  return (s || '').length > n ? s.slice(0, n) + '…' : (s || '')
}

function opLabel(o) {
  if (o.op === 'insert') {
    const first = (o.items && o.items[0]) || {}
    const n = (o.items || []).length
    return `在第 ${o.index} 段后插入 ${n} 段（${first.style} 等）：${truncate(first.text)}`
  }
  if (o.op === 'set_text') return `修改第 ${o.index} 段：${truncate(o.text)}`
  if (o.op === 'add_row') return `表格${o.table} 在含“${o.match}”的行后追加 ${(o.cells || []).length} 列`
  return JSON.stringify(o)
}

async function onMimicPlan() {
  if (!templateId.value) { ElMessage.warning('请先选择模板'); return }
  mimicLoading.value = true
  mimicReport.value = null
  try {
    mimicPlanResult.value = await mimicPlan(pid, templateId.value)
    ElMessage.success('仿写方案已生成，请预览后应用')
  } catch (e) {
    if (e.response?.status === 502) ElMessage.error('仿写方案生成失败，请重试')
  } finally {
    mimicLoading.value = false
  }
}

async function onMimicApply() {
  if (!mimicPlanResult.value) return
  mimicApplying.value = true
  try {
    mimicReport.value = await mimicApply(pid, templateId.value, mimicPlanResult.value.ops)
  } catch (e) {
    if (e.response?.status === 422) ElMessage.error('应用失败：' + (e.response.data?.detail || '编辑指令锚点不匹配'))
  } finally {
    mimicApplying.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => { if (es) es.close() })
</script>

<template>
  <div style="display: flex; gap: 16px; height: calc(100vh - 80px)">
    <!-- 左：章节树 -->
    <div style="width: 260px; flex-shrink: 0">
      <el-space direction="vertical" style="width: 100%">
        <el-button style="width: 100%" :disabled="!currentId" @click="onAddChild">添加子章节</el-button>
        <el-button type="danger" plain style="width: 100%" :disabled="!currentId"
                   @click="onDeleteSection">删除章节</el-button>
      </el-space>
      <el-tree :data="tree" node-key="id" :props="{ label: 'title', children: 'children' }"
               highlight-current @node-click="select" style="margin-top: 12px" />
    </div>

    <!-- 中：正文编辑区 -->
    <div style="flex: 1; display: flex; flex-direction: column">
      <h3 style="margin: 0 0 8px">
        {{ current.title || '未选择章节' }}
        <el-tag v-if="current.gen_status" size="small" style="margin-left: 8px">{{ current.gen_status }}</el-tag>
      </h3>
      <el-input v-model="content" type="textarea" :rows="20" resize="none"
                placeholder="选择章节后在此编辑正文，或点击右侧「生成」由 AI 撰写" style="flex: 1" />
      <el-space style="margin-top: 12px">
        <el-button type="primary" :loading="saving" :disabled="!currentId" @click="onSave">保存</el-button>
      </el-space>
    </div>

    <!-- 右：生成面板 -->
    <div style="width: 300px; flex-shrink: 0; overflow-y: auto">
      <h4 style="margin: 0 0 8px">生成面板</h4>
      <el-divider content-position="left">结构化资产</el-divider>
      <el-select v-model="selectedAssets" multiple collapse-tags placeholder="勾选企业信息/人员/证书"
                 style="width: 100%">
        <el-option v-for="a in assets" :key="a.id"
                   :label="`[${a.type === 'info' ? '企业' : a.type === 'person' ? '人员' : '证书'}] ${a.name}`"
                   :value="a.id" />
      </el-select>
      <el-divider content-position="left">项目素材</el-divider>
      <el-select v-model="selectedMaterials" multiple collapse-tags placeholder="勾选素材文件"
                 style="width: 100%">
        <el-option v-for="m in materials" :key="m.id"
                   :label="m.file_path.split(/[\\/]/).pop()" :value="m.id" />
      </el-select>
      <el-divider content-position="left">模板</el-divider>
      <el-select v-model="templateId" clearable placeholder="选择样式模板（可选）"
                 style="width: 100%; margin-bottom: 8px">
        <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-button style="width: 100%" :loading="templateGenLoading" :disabled="!templateId"
                 @click="onSectionsFromTemplate">从模板生成章节</el-button>
      <el-button style="width: 100%; margin: 8px 0 0" :loading="adaptLoading" :disabled="!tree.length"
                 @click="onAdaptTitles">AI 改写为项目标题</el-button>
      <el-divider content-position="left">导出</el-divider>
      <el-button type="success" style="width: 100%" :disabled="!tree.length"
                 tag="a" :href="exportWordUrl(pid, templateId)">导出 Word</el-button>
      <el-button type="primary" style="width: 100%; margin-top: 12px"
                 :loading="generating" :disabled="!currentId" @click="onGenerate">
        {{ generating ? '生成中…' : (current.gen_status === '已生成' || current.gen_status === '已编辑' ? '重写本节' : '生成本节') }}
      </el-button>
      <el-alert v-if="generating" type="info" :closable="false" style="margin-top: 8px">
        <template #title>
          <div v-if="progressInfo">
            正在生成 第 {{ progressInfo.current }}/{{ progressInfo.total }} 节<span v-if="progressInfo.title">：{{ progressInfo.title }}</span>
          </div>
          <div>
            内容将实时追加到编辑区…
            <span v-if="targetWords">目标篇幅：约 {{ targetWords }} 字</span>
          </div>
        </template>
      </el-alert>
      <el-divider content-position="left">保格式仿写</el-divider>
      <el-button style="width: 100%" :loading="mimicLoading" :disabled="!templateId"
                 @click="onMimicPlan">生成仿写方案</el-button>
      <el-alert v-if="mimicPlanResult" type="info" :closable="false" style="margin-top: 8px"
                :title="mimicPlanResult.summary" />
      <el-collapse v-if="mimicPlanResult && mimicPlanResult.ops.length" style="margin-top: 8px">
        <el-collapse-item v-for="(o, i) in mimicPlanResult.ops" :key="i" :title="opLabel(o)">
          <pre style="white-space: pre-wrap; word-break: break-all; margin: 0; font-size: 12px">{{ JSON.stringify(o, null, 2) }}</pre>
        </el-collapse-item>
      </el-collapse>
      <el-button type="primary" style="width: 100%; margin-top: 8px"
                 :loading="mimicApplying" :disabled="!mimicPlanResult"
                 @click="onMimicApply">应用并生成 docx</el-button>
      <template v-if="mimicReport">
        <el-alert :type="mimicReport.report.drift === 0 && mimicReport.report.invalid_new === 0 ? 'success' : 'warning'"
                  :closable="false" style="margin-top: 8px"
                  :title="mimicReport.report.drift === 0 && mimicReport.report.invalid_new === 0
                    ? '格式校验通过'
                    : `格式存在 ${mimicReport.report.issues.length} 处问题，请检查`" />
        <el-alert v-for="(w, i) in mimicReport.warnings" :key="'w' + i" type="warning"
                  :title="w" :closable="false" style="margin-top: 4px" />
        <el-button type="success" style="width: 100%; margin-top: 8px" tag="a"
                   :href="mimicDownloadUrl(pid, mimicReport.output_file)" target="_blank">下载 docx</el-button>
      </template>
    </div>
  </div>
</template>
