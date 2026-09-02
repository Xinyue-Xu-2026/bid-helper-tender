<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  analyzeTemplate, deleteMaterial, deleteTemplate, listMaterials,
  listTemplates, uploadMaterials, uploadTemplates,
} from '../api'

const props = defineProps({ projectId: Number })
const templates = ref([])
const materials = ref([])
const analyzingId = ref(null)
const uploading = ref(false)

async function load() {
  templates.value = await listTemplates()
  materials.value = await listMaterials(props.projectId)
}

// el-upload 的 change 事件按文件逐个触发，这里用去抖把一次选择的多个文件攒成一批上传
function batchUpload(uploadFile, pending, flush) {
  pending.files.push(uploadFile.raw)
  clearTimeout(pending.timer)
  pending.timer = setTimeout(flush, 100)
}

function reportErrors(errors) {
  if (!errors?.length) return
  ElMessage.warning('部分文件上传失败：' + errors.map(e => `${e.filename}（${e.reason}）`).join('；'))
}

const templateBatch = { files: [], timer: null }
const templateUploadRef = ref()
function onTemplateChange(uploadFile) {
  batchUpload(uploadFile, templateBatch, flushTemplateUpload)
}
async function flushTemplateUpload() {
  const files = templateBatch.files
  templateBatch.files = []
  templateUploadRef.value?.clearFiles()
  if (!files.length) return
  uploading.value = true
  try {
    const r = await uploadTemplates(files)
    reportErrors(r.errors)
    const items = r.items || []
    if (items.length) ElMessage.success(`已上传 ${items.length} 个模板`)
    load()
    // 逐个做风格画像分析
    for (const t of items) {
      if (!t?.id) continue
      analyzingId.value = t.id
      try {
        await analyzeTemplate(t.id)
      } catch {
        ElMessage.warning(`模板「${t.name || t.id}」画像分析失败（可点击「分析/重试」）`)
      } finally {
        analyzingId.value = null
        load()
      }
    }
  } finally {
    uploading.value = false
  }
}

const materialBatch = { files: [], timer: null }
const materialUploadRef = ref()
function onMaterialChange(uploadFile) {
  batchUpload(uploadFile, materialBatch, flushMaterialUpload)
}
async function flushMaterialUpload() {
  const files = materialBatch.files
  materialBatch.files = []
  materialUploadRef.value?.clearFiles()
  if (!files.length) return
  uploading.value = true
  try {
    const r = await uploadMaterials(props.projectId, files)
    reportErrors(r.errors)
    if (r.items?.length) ElMessage.success(`已上传 ${r.items.length} 份资料`)
    load()
  } finally {
    uploading.value = false
  }
}

async function onAnalyze(t) {
  analyzingId.value = t.id
  try {
    await analyzeTemplate(t.id)
    ElMessage.success('画像分析完成')
  } catch {
    ElMessage.warning('画像分析失败，请稍后重试')
  } finally {
    analyzingId.value = null
    load()
  }
}
async function onDeleteTemplate(t) { await deleteTemplate(t.id); load() }
async function onDeleteMaterial(m) { await deleteMaterial(m.id); load() }

onMounted(load)
</script>

<template>
  <el-row :gutter="24">
    <el-col :span="12">
      <h4>标书模板（全局库，导出时选用）</h4>
      <el-upload ref="templateUploadRef" :show-file-list="false" accept=".docx" multiple
                 :auto-upload="false" :on-change="onTemplateChange">
        <el-button :loading="uploading">上传模板 (.docx，可多选)</el-button>
      </el-upload>
      <el-table :data="templates" style="margin-top: 12px">
        <el-table-column prop="name" label="名称" />
        <el-table-column label="风格画像" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.style_profile" type="success">已分析</el-tag>
            <el-button v-else size="small" :loading="analyzingId === row.id"
                       @click="onAnalyze(row)">分析/重试</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="onDeleteTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-col>
    <el-col :span="12">
      <h4>项目资料（PDF/Word/Excel/图片）</h4>
      <el-upload ref="materialUploadRef" :show-file-list="false" multiple
                 :auto-upload="false" :on-change="onMaterialChange">
        <el-button :loading="uploading">上传资料（可多选）</el-button>
      </el-upload>
      <el-table :data="materials" style="margin-top: 12px">
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column label="文件" show-overflow-tooltip>
          <template #default="{ row }">{{ row.file_path.split(/[\\/]/).pop() }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="onDeleteMaterial(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-col>
  </el-row>
</template>
