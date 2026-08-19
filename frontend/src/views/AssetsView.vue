<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createAsset, deleteAsset, importAssets, listAssets, updateAsset, uploadAssetFile,
} from '../api'

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
  { key: 'info', label: '企业信息', nameLabel: '项目',
    fieldDefs: ['值'], hasExpiry: false, hasImport: false },
  { key: 'material', label: '素材库', nameLabel: '素材名称',
    fieldDefs: ['备注'], hasExpiry: false, hasImport: false },
]

const currentTab = () => TABS.find(t => t.key === tab.value)

async function load() { assets.value = await listAssets(tab.value) }

function openDialog(row) {
  editing.value = row || null
  form.value = row
    ? { name: row.name, fields: { ...row.fields }, expiry_date: row.expiry_date }
    : { name: '', fields: {}, expiry_date: '' }
  dialogVisible.value = true
}

async function save() {
  const payload = { ...form.value, type: tab.value }
  if (editing.value) await updateAsset(editing.value.id, payload)
  else await createAsset(payload)
  dialogVisible.value = false
  load()
}

async function remove(row) { await deleteAsset(row.id); load() }

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
  </el-space>

  <el-table :data="assets" :row-class-name="({ row }) => isExpiringSoon(row) ? 'expiring-row' : ''">
    <el-table-column prop="name" :label="currentTab().nameLabel" width="180" />
    <el-table-column v-for="f in currentTab().fieldDefs" :key="f" :label="f">
      <template #default="{ row }">{{ row.fields[f] || '' }}</template>
    </el-table-column>
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

  <el-dialog v-model="dialogVisible" :title="editing ? '编辑' : '新增'" width="500px">
    <el-form label-width="110px">
      <el-form-item :label="currentTab().nameLabel" required>
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item v-for="f in currentTab().fieldDefs" :key="f" :label="f">
        <el-input v-model="form.fields[f]" />
      </el-form-item>
      <el-form-item v-if="currentTab().hasExpiry" label="有效期至">
        <el-date-picker v-model="form.expiry_date" value-format="YYYY-MM-DD" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="!form.name" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style>
.expiring-row { background: #fef0f0; }
</style>
