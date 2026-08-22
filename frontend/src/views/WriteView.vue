<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSection, deleteSection, exportWordUrl, generateOutline, getProject,
  getRequirements, getSections, listAssets, listMaterials, listTemplates,
  sectionGenerateUrl, updateSection,
} from '../api'

const route = useRoute()
const pid = Number(route.params.id)

const project = ref({})
const tree = ref([])
const currentId = ref(null)
const content = ref('')
const saving = ref(false)
const generating = ref(false)
const outlineLoading = ref(false)
const assets = ref([])
const materials = ref([])
const templates = ref([])
const requirements = ref([])
const selectedAssets = ref([])
const selectedMaterials = ref([])
const selectedReqs = ref([])
const templateId = ref(null)
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

const matchedReqs = computed(() => {
  const title = (current.value.title || '').replace(/[第章节一二三四五六七八九十\d.（）()、\s]/g, ' ')
  const tokens = title.split(' ').filter(t => t.length >= 2)
  if (!tokens.length) return requirements.value
  return requirements.value.filter(r => tokens.some(t => (r.content || '').includes(t)))
})

async function load() {
  project.value = await getProject(pid)
  tree.value = await getSections(pid)
  assets.value = (await listAssets()).filter(a => a.type !== 'material')
  materials.value = await listMaterials(pid)
  templates.value = await listTemplates()
  requirements.value = await getRequirements(pid)
  if (currentId.value == null && tree.value.length) select(tree.value[0])
}

function select(node) {
  if (generating.value) return
  currentId.value = node.id
  content.value = node.content || ''
  selectedReqs.value = matchedReqs.value.map(r => r.id)
}

async function onGenerateOutline() {
  if (generating.value) return
  try {
    await ElMessageBox.confirm('AI 将生成目录初稿并覆盖现有章节，继续？', '提示', { type: 'warning' })
  } catch { return }
  outlineLoading.value = true
  try {
    await generateOutline(pid)
    ElMessage.success('目录初稿已生成')
    currentId.value = null
    await load()
  } finally {
    outlineLoading.value = false
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
  content.value = ''
  const url = sectionGenerateUrl(pid, currentId.value, {
    assetIds: selectedAssets.value, materialIds: selectedMaterials.value, reqIds: selectedReqs.value,
  })
  es = new EventSource(url)
  es.addEventListener('chunk', e => { content.value += e.data })
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

onMounted(load)
onBeforeUnmount(() => { if (es) es.close() })
</script>

<template>
  <div style="display: flex; gap: 16px; height: calc(100vh - 80px)">
    <!-- 左：章节树 -->
    <div style="width: 260px; flex-shrink: 0">
      <el-space direction="vertical" style="width: 100%">
        <el-button type="primary" :loading="outlineLoading" style="width: 100%"
                   @click="onGenerateOutline">AI 生成目录初稿</el-button>
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
      <el-divider content-position="left">关联要求（可增删）</el-divider>
      <el-select v-model="selectedReqs" multiple collapse-tags placeholder="本节关联的招标要求"
                 style="width: 100%">
        <el-option v-for="r in requirements" :key="r.id" :label="r.content" :value="r.id" />
      </el-select>
      <el-divider content-position="left">导出</el-divider>
      <el-select v-model="templateId" clearable placeholder="选择样式模板（可选）"
                 style="width: 100%; margin-bottom: 8px">
        <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-button type="success" style="width: 100%" :disabled="!tree.length"
                 tag="a" :href="exportWordUrl(pid, templateId)">导出 Word</el-button>
      <el-button type="primary" style="width: 100%; margin-top: 12px"
                 :loading="generating" :disabled="!currentId" @click="onGenerate">
        {{ generating ? '生成中…' : (current.gen_status === '已生成' || current.gen_status === '已编辑' ? '重写本节' : '生成本节') }}
      </el-button>
      <el-alert v-if="generating" type="info" :closable="false"
                title="正在生成，内容将实时追加到编辑区…" style="margin-top: 8px" />
    </div>
  </div>
</template>
