<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  analyzeTemplate, deleteMaterial, deleteTemplate, listMaterials,
  listTemplates, uploadMaterial, uploadTemplate,
} from '../api'

const props = defineProps({ projectId: Number })
const templates = ref([])
const materials = ref([])
const analyzingId = ref(null)

async function load() {
  templates.value = await listTemplates()
  materials.value = await listMaterials(props.projectId)
}

async function onUploadTemplate({ file }) {
  const { id } = await uploadTemplate(file)
  load()
  analyzingId.value = id
  try {
    await analyzeTemplate(id)
    ElMessage.success('模板已上传，风格画像分析完成')
  } catch {
    ElMessage.warning('模板已上传，画像分析失败（可点击「分析/重试」）')
  } finally {
    analyzingId.value = null
    load()
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
async function onUploadMaterial({ file }) { await uploadMaterial(props.projectId, file); load() }
async function onDeleteMaterial(m) { await deleteMaterial(m.id); load() }

onMounted(load)
</script>

<template>
  <el-row :gutter="24">
    <el-col :span="12">
      <h4>标书模板（全局库，导出时选用）</h4>
      <el-upload :show-file-list="false" accept=".docx" :http-request="onUploadTemplate">
        <el-button>上传模板 (.docx)</el-button>
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
      <el-upload :show-file-list="false" :http-request="onUploadMaterial">
        <el-button>上传资料</el-button>
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
