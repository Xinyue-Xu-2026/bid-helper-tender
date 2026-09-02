<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { createProject, deleteProject, getExpiringDetail, listProjects } from '../api'

const router = useRouter()
const projects = ref([])
const expiring = ref([])
const dialogVisible = ref(false)
const form = ref({ name: '', client: '', bid_date: '', project_type: '服务', notes: '' })

async function load() {
  projects.value = await listProjects()
  expiring.value = await getExpiringDetail(30)
}

async function create() {
  const { id } = await createProject(form.value)
  dialogVisible.value = false
  Object.assign(form.value, { name: '', client: '', bid_date: '', project_type: '服务', notes: '' })
  router.push(`/projects/${id}`)
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除项目「${row.name}」？`, '提示', { type: 'warning' })
  } catch { return }
  await deleteProject(row.id)
  load()
}

onMounted(load)
</script>

<template>
  <h2>我的项目</h2>
  <el-alert v-if="expiring.length" type="warning" :closable="false" style="margin-bottom: 16px">
    <template #title>
      以下证书/资质将在 30 天内到期：
      <span v-for="(a, i) in expiring" :key="i" style="margin-right: 12px">
        <template v-if="a.type === 'person'">【人员】{{ a.asset_name }} · {{ a.cert_type || a.cert_name }}</template>
        <template v-else>【资信】{{ a.cert_name }}</template>
        （剩 {{ a.days_left }} 天）
      </span>
    </template>
  </el-alert>

  <el-button type="primary" @click="dialogVisible = true" style="margin-bottom: 16px">新建项目</el-button>

  <el-table :data="projects" @row-click="row => router.push(`/projects/${row.id}`)" style="cursor: pointer">
    <el-table-column prop="name" label="项目名称" />
    <el-table-column prop="client" label="招标单位" />
    <el-table-column prop="bid_date" label="投标日期" width="120" />
    <el-table-column prop="project_type" label="类型" width="100" />
    <el-table-column label="创建时间" width="180">
      <template #default="{ row }">{{ (row.created_at || '').slice(0, 16).replace('T', ' ') }}</template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }">
        <el-button type="danger" size="small" @click.stop="remove(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" title="新建项目" width="500px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="项目名称" required><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="招标单位"><el-input v-model="form.client" /></el-form-item>
      <el-form-item label="投标日期"><el-date-picker v-model="form.bid_date" value-format="YYYY-MM-DD" /></el-form-item>
      <el-form-item label="项目类型">
        <el-select v-model="form.project_type">
          <el-option v-for="t in ['服务', '工程', '采购', '其他']" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="!form.name" @click="create">创建</el-button>
    </template>
  </el-dialog>
</template>
