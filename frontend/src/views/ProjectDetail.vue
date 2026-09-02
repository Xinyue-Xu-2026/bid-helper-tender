<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteRequirement, exportUrl, getProject, getRequirements,
  updateRequirement, uploadTender,
} from '../api'
import BidPanel from '../components/BidPanel.vue'
import CompliancePanel from '../components/CompliancePanel.vue'
import MaterialsPanel from '../components/MaterialsPanel.vue'

const route = useRoute()
const pid = Number(route.params.id)
const project = ref({})
const requirements = ref([])
const filter = ref({ category: '', status: '', q: '' })
const parsing = ref(false)
const parseLogs = ref([])
let es = null

const CATEGORIES = ['资质门槛', '评分项', '废标项', '格式要求', '时间节点', '其他']
const STATUSES = ['待响应', '已响应', '需关注']

const stats = computed(() => {
  const s = { total: requirements.value.length }
  for (const c of CATEGORIES) s[c] = requirements.value.filter(r => r.category === c).length
  return s
})

async function load() {
  project.value = await getProject(pid)
  requirements.value = await getRequirements(pid, {
    category: filter.value.category || undefined,
    status: filter.value.status || undefined,
    q: filter.value.q || undefined,
  })
}

async function onUploadTender(options) {
  await uploadTender(pid, options.file)
  ElMessage.success('招标文件已上传')
  load()
}

function startParse() {
  parsing.value = true
  parseLogs.value = []
  es = new EventSource(`/api/projects/${pid}/parse`)
  es.addEventListener('progress', e => parseLogs.value.push(e.data))
  es.addEventListener('done', e => {
    const d = JSON.parse(e.data)
    parseLogs.value.push(`完成：共 ${d.count} 条（${d.engine === 'ai' ? 'AI 解析' : '规则解析'}）`)
    if (d.warning) ElMessage.warning(d.warning)
    es.close(); parsing.value = false; load()
  })
  es.addEventListener('error', e => {
    parseLogs.value.push(`失败：${e.data || '连接中断'}`)
    es.close(); parsing.value = false
  })
}

async function onStatusChange(row, val) { row.status = val; await updateRequirement(row.id, { status: val }) }
async function onCategoryChange(row, val) { row.category = val; await updateRequirement(row.id, { category: val }) }
async function onDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该要求？', '提示', { type: 'warning' })
  } catch { return }
  await deleteRequirement(row.id); load()
}

onMounted(load)

onBeforeUnmount(() => { if (es) es.close() })
</script>

<template>
  <h2>{{ project.name }}</h2>
  <p v-if="project.client">招标单位：{{ project.client }}　投标日期：{{ project.bid_date }}</p>

  <el-tabs>
    <el-tab-pane label="要求清单">
      <el-space style="margin-bottom: 12px">
        <el-upload :show-file-list="false" accept=".pdf,.docx,.doc" :http-request="onUploadTender">
          <el-button>{{ project.tender_file_path ? '重新上传招标文件' : '上传招标文件' }}</el-button>
        </el-upload>
        <el-button type="primary" :disabled="!project.tender_file_path || parsing"
                   :loading="parsing" @click="startParse">
          {{ parsing ? '解析中…' : '开始解析' }}
        </el-button>
        <el-button :disabled="!requirements.length" tag="a" :href="exportUrl(pid)">导出 Excel</el-button>
      </el-space>

      <el-alert v-if="parseLogs.length" :title="parseLogs[parseLogs.length - 1]" type="info"
                :closable="false" style="margin-bottom: 12px" />

      <el-space style="margin-bottom: 12px">
        <el-select v-model="filter.category" placeholder="全部分类" clearable style="width: 130px" @change="load">
          <el-option v-for="c in CATEGORIES" :key="c" :label="`${c} (${stats[c] || 0})`" :value="c" />
        </el-select>
        <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 120px" @change="load">
          <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
        </el-select>
        <el-input v-model="filter.q" placeholder="搜索内容" clearable style="width: 220px" @change="load" />
        <span>共 {{ stats.total }} 条</span>
      </el-space>

      <el-table :data="requirements" max-height="60vh">
        <el-table-column type="index" width="50" />
        <el-table-column label="分类" width="130">
          <template #default="{ row }">
            <el-select :model-value="row.category" size="small" @change="v => onCategoryChange(row, v)">
              <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="110" />
        <el-table-column prop="confidence" label="置信度" width="80" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-select :model-value="row.status" size="small" @change="v => onStatusChange(row, v)">
              <el-option v-for="s in STATUSES" :key="s" :label="s" :value="s" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>

    <el-tab-pane label="废标核对">
      <CompliancePanel :project-id="pid" />
    </el-tab-pane>
    <el-tab-pane label="资料与模板">
      <MaterialsPanel :project-id="pid" />
    </el-tab-pane>
    <el-tab-pane label="商务标">
      <BidPanel :project-id="pid" :bid-date="project.bid_date" />
    </el-tab-pane>
  </el-tabs>
</template>
